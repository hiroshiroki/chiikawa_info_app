"""
ちいかわ情報収集スクリプト
Twitter(Nitter), ちいかわマーケット, ちいかわインフォから情報を自動収集
"""
import os
import sys
import time
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import re
import pytz

# 必要なライブラリのインポート
try:
    import requests
    from bs4 import BeautifulSoup
    import snscrape.modules.twitter as sntwitter
    from supabase import create_client, Client
except ImportError as e:
    print(f"必要なライブラリがインストールされていません: {e}")
    sys.exit(1)

# 環境変数から設定を取得
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("環境変数 SUPABASE_URL と SUPABASE_KEY を設定してください")
    sys.exit(1)

# Supabase接続
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================================
# ユーティリティ関数
# ========================================

def generate_source_id(text: str) -> str:
    """文字列からユニークIDを生成"""
    return hashlib.md5(text.encode()).hexdigest()

def classify_content(text: str) -> str:
    """テキストからカテゴリを自動判定"""
    keywords = {
        "グッズ": ["グッズ", "発売", "予約", "販売", "限定", "ぬいぐるみ", "フィギュア", "マスコット", "アクスタ"],
        "くじ": ["一番くじ", "くじ", "ロット", "景品"],
        "イベント": ["イベント", "開催", "コラボ", "カフェ", "ポップアップ", "展示", "らんど"],
        "漫画": ["更新", "掲載", "連載", "エピソード", "話"],
        "アニメ": ["放送", "配信", "声優", "OP", "ED"],
    }
    
    for category, words in keywords.items():
        if any(word in text for word in words):
            return category
    
    return "その他"

def save_to_db(items: List[Dict], source: str) -> int:
    """情報をデータベースに保存"""
    saved_count = 0
    
    for item in items:
        try:
            # 重複チェック (source_idを使用)
            existing = supabase.table("information").select("id").eq("source_id", item['source_id']).execute()
            
            if not existing.data:
                category = "グッズ" if source == "chiikawa_market" else classify_content(item['title'])

                data = {
                    "source": source,
                    "source_id": item['source_id'],
                    "title": item['title'],
                    "content": item.get('content', item['title']),
                    "url": item['url'],
                    "images": item.get('images', []),
                    "price": item.get('price'),
                    "category": category,
                    "published_at": item.get('published_at', datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()),
                    "status": item.get('status', 'new'),
                    "event_date": item.get('event_date') # ここで追加
                }
                
                supabase.table("information").insert(data).execute()
                saved_count += 1
                img_count = len(item.get('images', []))
                print(f"  ✅ 保存: {item['title'][:30]}... (画像{img_count}枚)")
            
        except Exception as e:
            print(f"  ⚠️ 保存エラー: {e}")
        time.sleep(0.1) 
    return saved_count

# ========================================
# 1. Twitter収集（Nitter RSS）
# ========================================

def collect_twitter() -> List[Dict]:
    print("\n🐦 Twitter収集開始 (snscrape使用)...")
    results = []
    account = "chiikawasan"
    max_tweets = 20 # 収集するツイートの最大数

    try:
        # snscrapeを使ってユーザーのタイムラインからツイートを取得
        scraper = sntwitter.TwitterUserScraper(account)
        
        for i, tweet in enumerate(scraper.get_items()):
            if i >= max_tweets:
                break

            images = []
            if tweet.media:
                for medium in tweet.media:
                    if isinstance(medium, sntwitter.Photo):
                        # 'orig' or 'large' サイズのURLを取得
                        images.append(medium.fullUrl.replace('name=large', 'name=orig'))
                    elif isinstance(medium, sntwitter.Video):
                        # ビデオのサムネイルURLを取得
                        images.append(medium.thumbnailUrl)

            # 本文が長すぎる場合は切り詰める
            title = tweet.rawContent
            if len(title) > 100:
                title = title[:97] + "..."

            results.append({
                'source_id': f"twitter_{tweet.id}",
                'title': title,
                'content': tweet.rawContent,
                'url': tweet.url,
                'images': images,
                'published_at': tweet.date.astimezone(pytz.timezone('Asia/Tokyo')).isoformat(),
            })
        
        print(f"  ✅ {len(results)}件のツイートを解析")
        return results

    except Exception as e:
        print(f"  ❌ snscrapeでの収集エラー: {e}")
        # snscrapeが失敗した場合、収集を中止
        return []

# ========================================
# 2. ちいかわマーケット収集（強化版）
# ========================================

def get_latest_market_urls() -> Dict[str, Optional[str]]:
    """ちいかわマーケットの最新の新商品・再入荷ページのURLを取得"""
    print("  🔗 最新のマーケットURLを取得中...")
    base_url = "https://chiikawamarket.jp"
    urls = {"new": None, "restock": None}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ナビゲーションメニューからリンクを探す
        nav_links = soup.select('a.nav-link, .header__menu-item')
        for link in nav_links:
            text = link.get_text(strip=True)
            href = link.get('href')
            if not href: continue

            if "新商品" in text or "NEW" in text:
                urls["new"] = f"{base_url}{href}" if not href.startswith('http') else href
            elif "再入荷" in text or "RESTOCK" in text:
                urls["restock"] = f"{base_url}{href}" if not href.startswith('http') else href
        
        print(f"  👍 取得成功: NEW -> {urls['new']}, RESTOCK -> {urls['restock']}")
        return urls
    except Exception as e:
        print(f"  ❌ 最新マーケットURLの取得に失敗: {e}")
        # フォールバックとして以前のURLを返す
        return {
            "new": "https://chiikawamarket.jp/collections/newitems",
            "restock": "https://chiikawamarket.jp/collections/restock"
        }

def collect_chiikawa_market(url: str, status: str) -> List[Dict]:
    if not url:
        print(f"\n🎁 ちいかわマーケット ({status}) のURLがありません。スキップします。")
        return []
    print(f"\n🎁 ちいかわマーケット ({status}) 収集開始: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ページタイトルから日付を抽出 (例: "1月30日発売商品"、"1月23日再入荷商品")
        event_date_str = None
        date_header = soup.select_one('h1.page-title, .collection__title')
        if date_header:
            match = re.search(r'(\d{1,2})月(\d{1,2})日', date_header.get_text())
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                now = datetime.now(pytz.timezone('Asia/Tokyo'))
                # 年のハンドリング: 抽出した月が未来の月なら去年、そうでなければ今年
                year = now.year - 1 if now.month < month else now.year
                try:
                    event_date_str = datetime(year, month, day).strftime('%Y-%m-%d')
                    print(f"  📅 イベント日を抽出: {event_date_str}")
                except ValueError:
                    event_date_str = None # 2/30のような不正な日付はNoneに
                
        items = soup.select('.product-item, .card-wrapper')
        results = []
        seen_ids = set()

        for item in items:
            title_elem = item.select_one('.product-item__title, .card__heading, h3.card-information__text')
            if not title_elem: continue
            title = title_elem.get_text(strip=True)
            
            link_elem = item.select_one('a[href*="/products/"]')
            if not link_elem: continue
            product_url = link_elem.get('href')
            if not product_url.startswith('http'):
                product_url = f"https://chiikawamarket.jp{product_url}"

            source_id = generate_source_id(f"{product_url}_{title}")
            if source_id in seen_ids: continue
            seen_ids.add(source_id)

            images = []
            img_tag = item.select_one('img.media')
            if img_tag:
                # data-src, src, srcset の順で試す
                img_url = img_tag.get('src') or img_tag.get('data-src')
                if not img_url and img_tag.get('srcset'):
                    # srcsetから最初のURLを取得
                    img_url = re.split(r'\s*,\s*', img_tag.get('srcset'))[0].split(' ')[0]
                
                if img_url:
                    if img_url.startswith('//'): img_url = f"https:{img_url}"
                    # ドメイン相対パスの場合、完全なURLに変換
                    elif not img_url.startswith('http'):
                        img_url = f"https:{img_url}" if img_url.startswith('//') else f"https://chiikawamarket.jp{img_url}"

                    images.append(img_url.split('?')[0])


            price = None
            price_elem = item.select_one('.price, .price-item')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                try:
                    # "¥1,100" や "1100" のような形式から数字のみを抽出
                    match = re.search(r'(\d[\d,.]*)', price_text)
                    if match:
                        price = int(float(match.group(1).replace(',', '')))
                except (ValueError, IndexError):
                    price = None

            results.append({
                'source_id': source_id,
                'title': title,
                'url': product_url,
                'images': images,
                'price': price,
                'published_at': datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
                'status': status,
                'event_date': event_date_str # ここで追加
            })
            if len(results) >= 50: break

        print(f"  ✅ {len(results)}件解析完了")
        return results
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return []

# ========================================
# 3. ちいかわインフォ収集
# ========================================

def collect_chiikawa_info() -> List[Dict]:
    print("\n📰 ちいかわインフォ収集開始...")
    url = "https://chiikawa-info.jp/"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.select('article.post-item')
        results = []
        for item in items:
            title_elem = item.select_one('h2.post-title')
            link_elem = item.select_one('a.post-link')
            if not title_elem or not link_elem: continue
            
            title = title_elem.get_text(strip=True)
            info_url = link_elem.get('href')
            if not info_url or len(title) < 5: continue
            if not info_url.startswith('http'):
                info_url = f"https://chiikawa-info.jp{info_url}"

            images = []
            img_tag = item.select_one('img.post-thumb-img')
            if img_tag:
                src = img_tag.get('src')
                if src:
                    if src.startswith('//'): src = f"https:{src}"
                    elif not src.startswith('http'): src = f"https://chiikawa-info.jp{src}"
                    images.append(src)

            # published_at を記事の日付から取得
            date_elem = item.select_one('time.post-date')
            published_at = datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()
            if date_elem and date_elem.get('datetime'):
                try:
                    published_at = datetime.fromisoformat(date_elem.get('datetime')).astimezone(pytz.timezone('Asia/Tokyo')).isoformat()
                except ValueError:
                    pass # パース失敗時は現在時刻のまま

            results.append({
                'source_id': generate_source_id(info_url),
                'title': title,
                'url': info_url,
                'images': images,
                'published_at': published_at,
            })
            if len(results) >= 20: break
        
        print(f"  ✅ {len(results)}件解析完了")
        return results
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return []

# ========================================
# メイン実行
# ========================================

def main():
    print(f"🚀 実行開始: {datetime.now(pytz.timezone('Asia/Tokyo'))}")
    total_saved = 0
    
    # Twitter
    print("\n--- twitter 収集 ---")
    items = collect_twitter()
    if items:
        saved = save_to_db(items, "twitter")
        print(f"  📊 twitter: {saved}件を新規保存")
        total_saved += saved
    else:
        print(f"  ⚠️ twitter からの新規情報はありませんでした。")
    time.sleep(1)

    # ちいかわマーケットのURLを動的に取得
    market_urls = get_latest_market_urls()

    # ちいかわマーケット（新商品）
    if market_urls.get("new"):
        print("\n--- chiikawa_market (new) 収集 ---")
        market_new_items = collect_chiikawa_market(market_urls["new"], "new")
        if market_new_items:
            saved = save_to_db(market_new_items, "chiikawa_market")
            print(f"  📊 chiikawa_market (new): {saved}件を新規保存")
            total_saved += saved
        else:
            print(f"  ⚠️ chiikawa_market (new) からの新規情報はありませんでした。")
        time.sleep(1)

    # ちいかわマーケット（再入荷）
    if market_urls.get("restock"):
        print("\n--- chiikawa_market (restock) 収集 ---")
        market_restock_items = collect_chiikawa_market(market_urls["restock"], "restock")
        if market_restock_items:
            saved = save_to_db(market_restock_items, "chiikawa_market")
            print(f"  📊 chiikawa_market (restock): {saved}件を新規保存")
            total_saved += saved
        else:
            print(f"  ⚠️ chiikawa_market (restock) からの新規情報はありませんでした。")
        time.sleep(1)

    # ちいかわインフォ
    print("\n--- chiikawa_info 収集 ---")
    info_items = collect_chiikawa_info()
    if info_items:
        saved = save_to_db(info_items, "chiikawa_info")
        print(f"  📊 chiikawa_info: {saved}件を新規保存")
        total_saved += saved
    else:
        print(f"  ⚠️ chiikawa_info からの新規情報はありませんでした。")
    time.sleep(1)

    print(f"\n✨ 完了！合計 {total_saved} 件の新規情報を保存しました")

if __name__ == "__main__":
    main()
