"""
ちいかわ情報収集スクリプト
ちいかわマーケットから情報を自動収集
"""
import os
import sys
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import re
import pytz

# 必要なライブラリのインポート
try:
    import requests
    from bs4 import BeautifulSoup
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

def save_to_db(items: List[Dict], source: str) -> int:
    """情報をデータベースに保存"""
    saved_count = 0
    
    # 新しいアイテムが先に来るように逆順で処理
    for item in reversed(items):
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
                    "images": item.get('images', []),
                    "price": item.get('price'),
                    "category": "グッズ",
                    "published_at": item.get('published_at', datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()),
                    "status": item.get('status', 'new'),
                    "event_date": item.get('event_date')
                }
                
                supabase.table("information").insert(data).execute()
                saved_count += 1
                img_count = len(item.get('images', []))
                print(f"  ✅ 保存: {item['title'][:30]}... (画像{img_count}枚)")
            
        except Exception as e:
            print(f"  ⚠️ 保存エラー: {item.get('title', '不明なアイテム')} - {e}")
        time.sleep(0.1) 
    return saved_count

# ========================================
# ちいかわマーケット収集
# ========================================

def get_latest_market_urls() -> Dict[str, Optional[str]]:
    """ちいかわマーケットの最新の新商品・再入荷ページのURLを取得"""
    print("  🔗 最新のマーケットURLを取得中...")
    base_url = "https://chiikawamarket.jp"
    urls = {"new": None, "restock": None}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(base_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        link_selectors = [
            'a[href*="/collections/newitems"]', 
            'a[href*="/collections/restock"]',
            'a:contains("新商品")',
            'a:contains("再入荷")'
        ]
        
        for selector in link_selectors:
            for link in soup.select(selector):
                href = link.get('href')
                if not href: continue
                
                full_url = f"{base_url}{href}" if not href.startswith('http') else href
                
                if "newitems" in href or "新商品" in link.get_text(strip=True):
                    urls["new"] = full_url
                elif "restock" in href or "再入荷" in link.get_text(strip=True):
                    urls["restock"] = full_url
        
        # もし見つからなければフォールバック
        if not urls["new"]:
            urls["new"] = "https://chiikawamarket.jp/collections/newitems"
        if not urls["restock"]:
            urls["restock"] = "https://chiikawamarket.jp/collections/restock"

        print(f"  👍 取得成功: NEW -> {urls['new']}, RESTOCK -> {urls['restock']}")
        return urls
    except Exception as e:
        print(f"  ❌ 最新マーケットURLの取得に失敗: {e}")
        return {
            "new": "https://chiikawamarket.jp/collections/newitems",
            "restock": "https://chiikawamarket.jp/collections/restock"
        }

def collect_chiikawa_market(url: str, status: str) -> List[Dict]:
    if not url:
        print(f"{(f' ({status})')} のURLがありません。スキップします。")
        return []
    print(f"{(f' ({status})')} 収集開始: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        event_date_str = None
        date_header = soup.select_one('.collection__title, .section-header__title, h1')
        if date_header:
            text = date_header.get_text(strip=True)
            match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                now = datetime.now(pytz.timezone('Asia/Tokyo'))
                year = now.year if now.month >= month else now.year -1
                try:
                    event_date_str = datetime(year, month, day).strftime('%Y-%m-%d')
                    print(f"  📅 イベント日を抽出: {event_date_str} (from: {text})")
                except ValueError:
                    event_date_str = None
        
        results = []
        # 商品カードのセレクタをより堅牢に
        items = soup.select('.card-wrapper, .product-grid .grid__item')

        for item in items:
            title_elem = item.select_one('.card__heading, .card-information__text')
            if not title_elem: continue
            title = title_elem.get_text(strip=True)
            
            link_elem = item.select_one('a[href*="/products/"]')
            if not link_elem: continue
            product_url = link_elem.get('href')
            if not product_url.startswith('http'):
                product_url = f"https://chiikawamarket.jp{product_url.split('?')[0]}"

            source_id = generate_source_id(f"{product_url}_{title}")

            images = []
            img_tag = item.select_one('.card__media img, .media img')
            if img_tag:
                img_url = img_tag.get('src') or img_tag.get('data-src')
                if not img_url and img_tag.get('srcset'):
                    img_url = re.split(r'\s*,\s*', img_tag.get('srcset'))[0].split(' ')[0]
                
                if img_url:
                    if img_url.startswith('//'): img_url = f"https:{img_url}"
                    images.append(img_url.split('?')[0])

            price = None
            price_elem = item.select_one('.price__regular .price-item, .price-item--regular')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                match = re.search(r'(\d[\d,.]*)', price_text)
                if match:
                    try:
                        price = int(float(match.group(1).replace(',', '')))
                    except ValueError:
                        price = None
            
            # 新しい商品がリストの上部にあると仮定し、順に取得
            results.append({
                'source_id': source_id,
                'title': title,
                'url': product_url,
                'images': images,
                'price': price,
                'published_at': datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
                'status': status,
                'event_date': event_date_str
            })
            if len(results) >= 50: break # 収集数の上限

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
    
    market_urls = get_latest_market_urls()

    all_items = []
    if market_urls.get("new"):
        print("\n--- chiikawa_market (new) 収集 ---")
        all_items.extend(collect_chiikawa_market(market_urls["new"], "new"))
        time.sleep(1)

    if market_urls.get("restock"):
        print("\n--- chiikawa_market (restock) 収集 ---")
        all_items.extend(collect_chiikawa_market(market_urls["restock"], "restock"))
        time.sleep(1)

    if all_items:
        # サイト上で新しいものが上にあるため、取得したリストの逆順（古いもの）からDBに保存していく
        # これにより、Webサイトでの表示順（新しいものが上）とDBの保存順が一致しやすくなる
        print("\n--- データベース保存 ---")
        saved = save_to_db(all_items, "chiikawa_market")
        print(f"  📊 chiikawa_market: {saved}件を新規保存")
        total_saved += saved
    else:
        print("  ⚠️ chiikawa_marketからの新規情報はありませんでした。")

    print(f"\n✨ 完了！合計 {total_saved} 件の新規情報を保存しました")

if __name__ == "__main__":
    main()
