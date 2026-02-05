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

# 必要なライブラリのインポート
try:
    import requests
    from bs4 import BeautifulSoup
    import feedparser
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
                    "published_at": item.get('published_at', datetime.now().isoformat()),
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
    print("\n🐦 Twitter収集開始...")
    nitter_instances = [
        "https://nitter.mint.lgbt", 
        "https://nitter.io", 
        "https://nitter.namazso.eu",
        "https://nitter.bus-hit.me"
    ]
    account = "chiikawasan"
    
    for instance in nitter_instances:
        try:
            rss_url = f"{instance}/{account}/rss"
            print(f"  試行: {rss_url}")
            # User-Agentを設定してブロックを回避
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            feed_content = requests.get(rss_url, headers=headers, timeout=10).content
            feed = feedparser.parse(feed_content)

            if feed.entries:
                results = []
                for entry in feed.entries[:20]:
                    images = []
                    if hasattr(entry, 'summary'):
                        soup = BeautifulSoup(entry.summary, 'html.parser')
                        # /pic/media%2F... のような形式の画像を抽出
                        for a_tag in soup.find_all('a', href=lambda href: href and '/pic/media' in href):
                            img_path = a_tag['href']
                            # URLを再構築
                            img_url = f"{instance}{img_path}"
                            images.append(img_url)

                        # 従来のimgタグも一応チェック
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            if src:
                                if src.startswith('//'): src = f"https:{src}"
                                # ドメインがなければ付与
                                if not src.startswith('http'):
                                     src = f"{instance}{src}"
                                if src not in images: # 重複を避ける
                                    images.append(src)
                    
                    # NitterのURLをTwitterのURLに変換
                    tweet_link = entry.link
                    if "nitter" in tweet_link:
                         tweet_link = tweet_link.replace(instance, "https://twitter.com")

                    tweet_id = tweet_link.split("/")[-1].split("#")[0]
                    
                    results.append({
                        'source_id': f"twitter_{tweet_id}",
                        'title': entry.title[:100],
                        'content': entry.get('summary', entry.title),
                        'url': tweet_link,
                        'images': images,
                        'published_at': datetime.now().isoformat()
                    })
                print(f"  ✅ {len(results)}件のツイートを解析")
                return results
        except Exception as e:
            print(f"  ❌ インスタンスエラー ({instance}): {e}")
            continue
    print("  ⚠️ 全てのNitterインスタンスで収集に失敗しました。")
    return []

# ========================================
# 2. ちいかわマーケット収集（強化版）
# ========================================

def collect_chiikawa_market(url: str, status: str) -> List[Dict]:
    print(f"\n🎁 ちいかわマーケット ({status}) 収集開始...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ページタイトルから日付を抽出 (例: "1月30日発売商品"、"1月23日再入荷商品")
        event_date_str = None
        date_header = soup.select_one('h1.page-title, h2.section-header__title')
        if date_header:
            match = re.search(r'(\d{1,2})月(\d{1,2})日', date_header.get_text())
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                # 今年または来年の日付としてパースを試みる
                now = datetime.now()
                try:
                    # 今年の日付としてパース
                    event_date_candidate = datetime(now.year, month, day)
                    if event_date_candidate <= now: # 今日以前ならこの日付を採用
                        event_date_str = event_date_candidate.strftime('%Y-%m-%d')
                    else: # 未来の日付なら去年の日付を試す
                        event_date_candidate = datetime(now.year - 1, month, day)
                        if event_date_candidate <= now:
                            event_date_str = event_date_candidate.strftime('%Y-%m-%d')
                except ValueError:
                    # 無効な日付（例: 2月30日）の場合はスキップ
                    pass
                
        items = soup.select('.product-item, .card')
        results = []
        seen_ids = set()

        for item in items:
            title_elem = item.select_one('.product-item__title, .card__title, h3')
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
            img_tag = item.select_one('img')
            if img_tag:
                img_url = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src')
                if not img_url and img_tag.get('srcset'):
                    img_url = img_tag.get('srcset').split(',')[0].split(' ')[0]
                
                if img_url:
                    if img_url.startswith('//'): img_url = f"https:{img_url}"
                    elif not img_url.startswith('http'): img_url = f"https://chiikawamarket.jp{img_url}"
                    images.append(img_url.split('?')[0])

            price = None
            price_elem = item.select_one('.price, .price-item')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                try:
                    match = re.search(r'(\d{1,3}(,\d{3})*|\d+)', price_text)
                    if match:
                        price = int(match.group(1).replace(',', ''))
                    else:
                        price = None
                except ValueError:
                    price = None

            results.append({
                'source_id': source_id,
                'title': title,
                'url': product_url,
                'images': images,
                'price': price,
                'published_at': datetime.now().isoformat(),
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
        
        items = soup.select('.news-item, article, li')
        results = []
        for item in items:
            title_elem = item.select_one('h2, h3, .title')
            link_elem = item.select_one('a')
            if not title_elem or not link_elem: continue
            
            title = title_elem.get_text(strip=True)
            info_url = link_elem.get('href')
            if not info_url or len(title) < 5: continue
            if not info_url.startswith('http'):
                info_url = f"https://chiikawa-info.jp{info_url}"

            images = []
            img_tag = item.select_one('img')
            if img_tag:
                src = img_tag.get('src')
                if src:
                    if src.startswith('//'): src = f"https:{src}"
                    elif not src.startswith('http'): src = f"https://chiikawa-info.jp{src}"
                    images.append(src)

            results.append({
                'source_id': generate_source_id(info_url),
                'title': title,
                'url': info_url,
                'images': images,
                'published_at': datetime.now().isoformat()
            })
            if len(results) >= 20: break
        return results
    except Exception as e:
        return []

# ========================================
# メイン実行
# ========================================

def main():
    print(f"🚀 実行開始: {datetime.now()}")
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

    # ちいかわマーケット（新商品）
    print("\n--- chiikawa_market (new) 収集 ---")
    market_new_items = collect_chiikawa_market("https://chiikawamarket.jp/collections/newitems", "new")
    if market_new_items:
        saved = save_to_db(market_new_items, "chiikawa_market")
        print(f"  📊 chiikawa_market (new): {saved}件を新規保存")
        total_saved += saved
    else:
        print(f"  ⚠️ chiikawa_market (new) からの新規情報はありませんでした。")
    time.sleep(1)

    # ちいかわマーケット（再入荷）
    print("\n--- chiikawa_market (restock) 収集 ---")
    market_restock_items = collect_chiikawa_market("https://chiikawamarket.jp/collections/restock", "restock")
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