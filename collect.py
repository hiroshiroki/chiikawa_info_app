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
                data = {
                    "source": source,
                    "source_id": item['source_id'],
                    "title": item['title'],
                    "content": item.get('content', item['title']),
                    "url": item['url'],
                    "images": item.get('images', []), # listのまま渡す（supabase-pyが自動でJSONBに変換）
                    "price": item.get('price'),
                    "category": classify_content(item['title']),
                    "published_at": item.get('published_at', datetime.now().isoformat())
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
    nitter_instances = ["https://nitter.poast.org", "https://nitter.privacydev.net"]
    account = "ngnchiikawa"
    
    for instance in nitter_instances:
        try:
            rss_url = f"{instance}/{account}/rss"
            feed = feedparser.parse(rss_url)
            if feed.entries:
                results = []
                for entry in feed.entries[:20]:
                    images = []
                    # summary内の画像タグを抽出
                    if hasattr(entry, 'summary'):
                        soup = BeautifulSoup(entry.summary, 'html.parser')
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            if src:
                                if src.startswith('//'): src = f"https:{src}"
                                images.append(src)
                    
                    tweet_id = entry.link.split("/")[-1].split("#")[0]
                    results.append({
                        'source_id': f"twitter_{tweet_id}",
                        'title': entry.title[:100],
                        'content': entry.get('summary', entry.title),
                        'url': entry.link.replace(instance, "https://twitter.com"),
                        'images': images,
                        'published_at': datetime.now().isoformat() # RSSの日付形式は多様なため簡易化
                    })
                return results
        except Exception as e:
            continue
    return []

# ========================================
# 2. ちいかわマーケット収集（強化版）
# ========================================

def collect_chiikawa_market() -> List[Dict]:
    print("\n🎁 ちいかわマーケット収集開始...")
    url = "https://chiikawamarket.jp/collections/newitems"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # セレクタの改善：商品カードを正確に取得
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

            # 重複防止ロジック：URLとタイトルを組み合わせて一意のIDを作る
            source_id = generate_source_id(f"{product_url}_{title}")
            if source_id in seen_ids: continue
            seen_ids.add(source_id)

            # 画像取得の強化 (Lazy Load対応)
            images = []
            img_tag = item.select_one('img')
            if img_tag:
                img_url = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src')
                if not img_url and img_tag.get('srcset'):
                    img_url = img_tag.get('srcset').split(',')[0].split(' ')[0]
                
                if img_url:
                    if img_url.startswith('//'): img_url = f"https:{img_url}"
                    elif not img_url.startswith('http'): img_url = f"https://chiikawamarket.jp{img_url}"
                    images.append(img_url.split('?')[0]) # クエリ削除

            # 金額取得
            price = None
            price_elem = item.select_one('.price, .price-item')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # "¥", "円", "," を除去して数値に変換
                try:
                    price = int("".join(filter(str.isdigit, price_text)))
                except ValueError:
                    price = None

            results.append({
                'source_id': source_id,
                'title': title,
                'url': product_url,
                'images': images,
                'price': price,
                'published_at': datetime.now().isoformat()
            })
            if len(results) >= 20: break

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
    
    # 順次実行
    for source_name, collector in [
        ("twitter", collect_twitter),
        ("chiikawa_market", collect_chiikawa_market),
        ("chiikawa_info", collect_chiikawa_info)
    ]:
        items = collector()
        if items:
            saved = save_to_db(items, source_name)
            print(f"  📊 {source_name}: {saved}件を新規保存")
            total_saved += saved
        time.sleep(1)

    print(f"\n✨ 完了！合計 {total_saved} 件の新規情報を保存しました")

if __name__ == "__main__":
    main()