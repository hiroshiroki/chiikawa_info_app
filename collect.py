"""
ちいかわ情報収集スクリプト
ちいかわマーケットから新商品・再入荷情報を自動収集
"""
import os
import sys
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import re
import pytz

try:
    import requests
    from bs4 import BeautifulSoup
    from supabase import create_client, Client
    from notifier import DiscordNotifier
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

# 定数
BASE_URL = "https://chiikawamarket.jp"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
TOKYO_TZ = pytz.timezone('Asia/Tokyo')


def generate_source_id(text: str) -> str:
    """文字列からユニークIDを生成"""
    return hashlib.md5(text.encode()).hexdigest()


def check_restock(item: Dict) -> None:
    """
    再入荷をチェックして履歴に記録

    Args:
        item: チェックする商品アイテム
    """
    try:
        # status='restock'でない場合は何もしない
        if item.get('status') != 'restock':
            return

        # 同じURLの既存商品を検索
        existing = supabase.table("information").select("*").eq("url", item['url']).execute()

        # 再入荷履歴データを準備
        previous_event_date = None
        if existing.data:
            existing_item = existing.data[0]
            previous_event_date = existing_item.get('event_date')

        new_event_date = item.get('event_date')

        # 同じURLの未通知の再入荷履歴があるかチェック（重複防止）
        existing_restock = supabase.table("restock_history")\
            .select("*")\
            .eq("product_url", item['url'])\
            .eq("notified", False)\
            .execute()

        if existing_restock.data:
            # 既に未通知の再入荷履歴がある場合はスキップ
            print(f"  ℹ️ 既に未通知の再入荷履歴あり: {item['title'][:30]}...")
            return

        # 再入荷履歴に記録（初回収集でも既存商品があっても記録する）
        restock_data = {
            "product_url": item['url'],
            "product_title": item['title'],
            "previous_event_date": previous_event_date,
            "new_event_date": new_event_date,
            "detected_at": datetime.now(TOKYO_TZ).isoformat()
        }

        supabase.table("restock_history").insert(restock_data).execute()
        is_new = not existing.data
        print(f"  🔔 再入荷検出: {item['title'][:30]}... (初回収集: {is_new})")

        # 既存商品のstatusとevent_dateをrestockに更新
        if existing.data:
            supabase.table("information")\
                .update({"status": "restock", "event_date": new_event_date})\
                .eq("id", existing.data[0]['id'])\
                .execute()
            print(f"  ✅ ステータス更新: {existing.data[0]['id']}")

    except Exception as e:
        print(f"  ⚠️ 再入荷チェックエラー: {item.get('title', '不明なアイテム')} - {e}")


def save_to_db(items: List[Dict], source: str) -> int:
    """
    情報をデータベースに保存

    Args:
        items: 保存するアイテムのリスト
        source: 情報源（'chiikawa_market'等）

    Returns:
        保存件数
    """
    saved_count = 0

    # 新しいアイテムが先に来るように逆順で処理
    for item in reversed(items):
        try:
            # 再入荷チェック（保存前に実行）
            check_restock(item)

            # 重複チェック
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
                    "published_at": item.get('published_at', datetime.now(TOKYO_TZ).isoformat()),
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


def extract_event_date(date_text: Optional[str], url: str) -> Optional[str]:
    """
    日付テキストまたはURLから発売日・再入荷日を抽出

    Args:
        date_text: 日付を含むテキスト（例: "2月6日発売商品"）
        url: URL（例: /collections/20260206）

    Returns:
        日付文字列（YYYY-MM-DD形式）またはNone
    """
    # 1. date_textから日付を抽出
    if date_text:
        match = re.search(r'(\d{1,2})月(\d{1,2})日', date_text)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            now = datetime.now(TOKYO_TZ)
            year = now.year if month <= now.month + 1 else now.year - 1
            try:
                event_date_str = datetime(year, month, day).strftime('%Y-%m-%d')
                print(f"  📅 イベント日を抽出: {event_date_str} (from: {date_text})")
                return event_date_str
            except ValueError:
                pass

    # 2. URLから日付を抽出
    url_date_match = re.search(r'/collections/(?:re)?(\d{8})', url)
    if url_date_match:
        date_str = url_date_match.group(1)
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            event_date_str = date_obj.strftime('%Y-%m-%d')
            print(f"  📅 イベント日を抽出: {event_date_str} (from URL: {url})")
            return event_date_str
        except ValueError:
            pass

    return None


def get_latest_market_urls() -> List[Dict[str, str]]:
    """
    ちいかわマーケットの日付別コレクションページのURLを取得

    Returns:
        URLリスト（url, status, date_textを含む辞書のリスト）
    """
    print("  🔗 日付別マーケットURLを取得中...")
    collections = []
    seen_urls = set()

    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(BASE_URL, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # すべてのリンクを探索
        for link in soup.select('a[href*="/collections/"]'):
            href = link.get('href')
            text = link.get_text(strip=True)

            if not href:
                continue

            full_url = f"{BASE_URL}{href}" if not href.startswith('http') else href

            # 重複チェック
            if full_url in seen_urls:
                continue

            # 新商品リンク（例: "2月6日発売商品"）
            if '発売商品' in text:
                date_match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
                if date_match:
                    collections.append({
                        'url': full_url,
                        'status': 'new',
                        'date_text': text
                    })
                    seen_urls.add(full_url)

            # 再入荷リンク（例: "2月5日再入荷商品"）
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
    """
    ちいかわマーケットから商品情報を収集

    Args:
        url: 収集対象のURL
        status: 商品区分（'new' or 'restock'）
        date_text: 日付テキスト（オプション）

    Returns:
        商品情報のリスト
    """
    if not url:
        print(f"  ({status}) のURLがありません。スキップします。")
        return []

    print(f"  ({status}) 収集開始: {url}")

    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # イベント日の抽出
        event_date_str = extract_event_date(date_text, url)

        results = []
        items = soup.select('.card-wrapper, .product-grid .grid__item')

        for item in items:
            # タイトル取得
            title_elem = item.select_one('.card__heading, .card-information__text')
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)

            # URL取得
            link_elem = item.select_one('a[href*="/products/"]')
            if not link_elem:
                continue
            product_url = link_elem.get('href')
            if not product_url.startswith('http'):
                product_url = f"{BASE_URL}{product_url.split('?')[0]}"

            # ユニークID生成
            source_id = generate_source_id(f"{product_url}_{title}")

            # 画像取得
            images = []
            img_tag = item.select_one('.card__media img, .media img')
            if img_tag:
                img_url = img_tag.get('src') or img_tag.get('data-src')
                if not img_url and img_tag.get('srcset'):
                    img_url = re.split(r'\s*,\s*', img_tag.get('srcset'))[0].split(' ')[0]

                if img_url:
                    if img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    images.append(img_url.split('?')[0])

            # 価格取得
            price = None
            price_elem = item.select_one('.price__regular .price-item, .price-item--regular')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                match = re.search(r'(\d[\d,.]*)', price_text)
                if match:
                    try:
                        price = int(float(match.group(1).replace(',', '')))
                    except ValueError:
                        pass

            results.append({
                'source_id': source_id,
                'title': title,
                'url': product_url,
                'images': images,
                'price': price,
                'published_at': datetime.now(TOKYO_TZ).isoformat(),
                'status': status,
                'event_date': event_date_str
            })

        print(f"  ✅ {len(results)}件解析完了")
        return results

    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return []


def main():
    """メイン処理"""
    print(f"🚀 実行開始: {datetime.now(TOKYO_TZ)}")
    total_saved = 0

    # 通知モジュール初期化
    notifier = DiscordNotifier()

    # 日付別コレクションページを取得
    collections = get_latest_market_urls()

    if not collections:
        print("  ⚠️ 収集するページが見つかりませんでした")
        return

    # 各コレクションから情報を収集
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

    # データベースに保存
    if all_items:
        print("\n--- データベース保存 ---")
        saved = save_to_db(all_items, "chiikawa_market")
        print(f"  📊 chiikawa_market: {saved}件を新規保存")
        total_saved += saved
    else:
        print("  ⚠️ chiikawa_marketからの新規情報はありませんでした。")

    # 未通知の再入荷情報を取得して通知
    print("\n--- 再入荷通知 ---")
    try:
        unnotified = supabase.table("restock_history").select("*").eq("notified", False).execute()

        if unnotified.data:
            print(f"  📬 未通知の再入荷: {len(unnotified.data)}件")

            # Discord通知送信
            if notifier.send_restock_notification(unnotified.data):
                print(f"  ✅ Discord通知送信成功")

                # 通知済みフラグを更新
                for item in unnotified.data:
                    supabase.table("restock_history").update({"notified": True}).eq("id", item['id']).execute()
                print(f"  ✅ 通知フラグ更新完了")
            else:
                if notifier.enabled:
                    print(f"  ⚠️ Discord通知送信失敗（通知フラグは更新しません）")
                else:
                    print(f"  ℹ️ Discord通知は無効化されています")
        else:
            print(f"  ℹ️ 未通知の再入荷はありません")

    except Exception as e:
        print(f"  ⚠️ 再入荷通知処理エラー: {e}")

    # サマリー通知（オプション）
    if notifier.enabled and os.getenv("DISCORD_SEND_SUMMARY", "false").lower() == "true":
        restock_count = len(unnotified.data) if unnotified.data else 0
        notifier.send_summary(total_saved, restock_count)

    print(f"\n✨ 完了！合計 {total_saved} 件の新規情報を保存しました")


if __name__ == "__main__":
    main()
