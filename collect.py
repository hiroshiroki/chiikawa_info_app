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

def get_latest_market_urls() -> List[Dict[str, str]]:
    """ちいかわマーケットの日付別コレクションページのURLを取得"""
    print("  🔗 日付別マーケットURLを取得中...")
    base_url = "https://chiikawamarket.jp"
    collections = []
    seen_urls = set()  # 重複チェック用

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(base_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # すべてのリンクを探索
        for link in soup.select('a[href*="/collections/"]'):
            href = link.get('href')
            text = link.get_text(strip=True)

            if not href:
                continue

            full_url = f"{base_url}{href}" if not href.startswith('http') else href

            # 重複チェック
            if full_url in seen_urls:
                continue

            # 日付を含む新商品リンク (例: "2月6日発売商品" -> /collections/20260206)
            if '発売商品' in text:
                date_match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
                if date_match:
                    collections.append({
                        'url': full_url,
                        'status': 'new',
                        'date_text': text
                    })
                    seen_urls.add(full_url)

            # 日付を含む再入荷リンク (例: "2月5日再入荷商品" -> /collections/re20260205)
            elif '再入荷商品' in text and '再入荷商品一覧' not in text:
                date_match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
                if date_match:
                    collections.append({
                        'url': full_url,
                        'status': 'restock',
                        'date_text': text
                    })
                    seen_urls.add(full_url)

        if collections:
            print(f"  👍 取得成功: {len(collections)}個の日付別ページを発見")
            for col in collections:
                print(f"    - {col['date_text']}: {col['url']}")
        else:
            print("  ⚠️ 日付別ページが見つかりませんでした")

        return collections

    except Exception as e:
        print(f"  ❌ マーケットURLの取得に失敗: {e}")
        return []

def collect_chiikawa_market(url: str, status: str, date_text: Optional[str] = None) -> List[Dict]:
    if not url:
        print(f"{(f' ({status})')} のURLがありません。スキップします。")
        return []
    print(f"{(f' ({status})')} 収集開始: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 日付の抽出 (date_textまたはURLから)
        event_date_str = None

        # 1. date_textから日付を抽出 (例: "2月6日発売商品")
        if date_text:
            match = re.search(r'(\d{1,2})月(\d{1,2})日', date_text)
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                now = datetime.now(pytz.timezone('Asia/Tokyo'))
                year = now.year if month <= now.month + 1 else now.year - 1
                try:
                    event_date_str = datetime(year, month, day).strftime('%Y-%m-%d')
                    print(f"  📅 イベント日を抽出: {event_date_str} (from: {date_text})")
                except ValueError:
                    event_date_str = None

        # 2. URLから日付を抽出 (例: /collections/20260206 または /collections/re20260205)
        if not event_date_str:
            url_date_match = re.search(r'/collections/(?:re)?(\d{8})', url)
            if url_date_match:
                date_str = url_date_match.group(1)
                try:
                    date_obj = datetime.strptime(date_str, '%Y%m%d')
                    event_date_str = date_obj.strftime('%Y-%m-%d')
                    print(f"  📅 イベント日を抽出: {event_date_str} (from URL: {url})")
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

    # 日付別コレクションページを取得
    collections = get_latest_market_urls()

    if not collections:
        print("  ⚠️ 収集するページが見つかりませんでした")
        return

    all_items = []
    for collection in collections:
        status_label = "新商品" if collection['status'] == 'new' else "再入荷"
        print(f"\n--- chiikawa_market ({status_label}: {collection['date_text']}) 収集 ---")
        items = collect_chiikawa_market(
            collection['url'],
            collection['status'],
            collection['date_text']
        )
        all_items.extend(items)
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
