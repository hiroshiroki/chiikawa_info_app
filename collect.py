"""
ちいかわ情報収集スクリプト
Twitter、ちいかわマーケット、ちいかわインフォから情報を自動収集
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
    print("以下を実行してください:")
    print("pip install requests beautifulsoup4 feedparser supabase")
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

def generate_source_id(url: str) -> str:
    """URLからユニークIDを生成"""
    return hashlib.md5(url.encode()).hexdigest()

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
            # 重複チェック
            existing = supabase.table("information").select("id").eq("source_id", item['source_id']).execute()
            
            if not existing.data:
                data = {
                    "source": source,
                    "source_id": item['source_id'],
                    "title": item['title'],
                    "content": item.get('content', item['title']),
                    "url": item['url'],
                    "images": json.dumps(item.get('images', [])),
                    "category": classify_content(item['title']),
                    "published_at": item.get('published_at', datetime.now().isoformat())
                }
                
                supabase.table("information").insert(data).execute()
                saved_count += 1
                print(f"  ✅ 保存: {item['title'][:50]}... (画像{len(item.get('images', []))}枚)")
            
        except Exception as e:
            print(f"  ⚠️ 保存エラー: {e}")
        
        time.sleep(0.3)  # レート制限対策
    
    return saved_count

# ========================================
# 1. Twitter収集（Nitter RSS）
# ========================================

def collect_twitter() -> List[Dict]:
    """Twitterから情報を取得"""
    print("\n🐦 Twitter収集開始...")
    
    nitter_instances = [
        "https://nitter.poast.org",
        "https://nitter.net",
        "https://nitter.privacydev.net",
    ]
    
    account = "ngnchiikawa"
    
    for instance in nitter_instances:
        try:
            rss_url = f"{instance}/{account}/rss"
            print(f"  試行中: {instance}")
            
            feed = feedparser.parse(rss_url)
            
            if feed.entries:
                results = []
                for entry in feed.entries[:20]:  # 最新20件
                    # 画像を取得
                    images = []
                    
                    # media_contentから画像取得
                    if hasattr(entry, 'media_content'):
                        for media in entry.media_content:
                            if 'url' in media:
                                images.append(media['url'])
                    
                    # summaryから画像URL抽出
                    if hasattr(entry, 'summary'):
                        soup = BeautifulSoup(entry.summary, 'html.parser')
                        img_tags = soup.find_all('img')
                        for img in img_tags:
                            if img.get('src') and img['src'] not in images:
                                images.append(img['src'])
                    
                    # ツイートID取得
                    tweet_id = entry.link.split("/")[-1].split("#")[0]
                    
                    results.append({
                        'source_id': f"twitter_{tweet_id}",
                        'title': entry.title,
                        'content': entry.get('summary', entry.title),
                        'url': entry.link.replace(instance, "https://twitter.com"),  # 本家URLに変換
                        'images': images,
                        'published_at': entry.get('published', '')
                    })
                
                print(f"  ✅ {len(results)}件取得成功")
                return results
                
        except Exception as e:
            print(f"  ❌ {instance}: {e}")
            continue
    
    print("  ❌ すべてのインスタンスで失敗")
    return []

# ========================================
# 2. ちいかわマーケット収集
# ========================================

def collect_chiikawa_market() -> List[Dict]:
    """ちいかわマーケットから新商品情報を取得"""
    print("\n🎁 ちいかわマーケット収集開始...")
    
    # 新着商品ページ
    url = "https://chiikawamarket.jp/collections/newitems"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 商品アイテムを取得（実際のHTML構造に応じて調整）
        # ちいかわマーケットの商品カード
        items = soup.select('.product-item')[:20]  # 最新20件
        
        if not items:
            # 別のセレクタを試す
            items = soup.select('a[href*="/products/"]')[:20]
        
        results = []
        for item in items:
            try:
                # タイトル取得
                title_elem = item.select_one('.product-item__title, h3, .product-title')
                if not title_elem:
                    title_elem = item
                
                title = title_elem.get_text(strip=True) if title_elem else "商品"
                
                # URL取得
                link = item.get('href') if item.name == 'a' else item.select_one('a')
                if not link:
                    continue
                
                product_url = link if isinstance(link, str) else link.get('href')
                if not product_url.startswith('http'):
                    product_url = f"https://chiikawamarket.jp{product_url}"
                
                # 画像取得
                images = []
                img_elem = item.select_one('img')
                if img_elem:
                    img_url = img_elem.get('src') or img_elem.get('data-src')
                    if img_url:
                        if not img_url.startswith('http'):
                            img_url = f"https:{img_url}" if img_url.startswith('//') else f"https://chiikawamarket.jp{img_url}"
                        images.append(img_url)
                
                results.append({
                    'source_id': generate_source_id(product_url),
                    'title': title,
                    'content': title,
                    'url': product_url,
                    'images': images,
                    'published_at': datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"  ⚠️ 項目スキップ: {e}")
                continue
        
        print(f"  ✅ {len(results)}件取得")
        return results
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return []

# ========================================
# 3. ちいかわインフォ収集
# ========================================

def collect_chiikawa_info() -> List[Dict]:
    """ちいかわインフォからイベント情報を取得"""
    print("\n📰 ちいかわインフォ収集開始...")
    
    url = "https://chiikawa-info.jp/"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # イベント情報を取得（実際のHTML構造に応じて調整）
        items = soup.select('.news-item, .event-item, article')[:20]
        
        if not items:
            # 別のセレクタを試す
            items = soup.select('a[href*="chiikawa-info.jp"]')[:20]
        
        results = []
        for item in items:
            try:
                # タイトル取得
                title_elem = item.select_one('h2, h3, .title, .event-title')
                if not title_elem:
                    title_elem = item
                
                title = title_elem.get_text(strip=True) if title_elem else "イベント情報"
                
                if not title or len(title) < 5:
                    continue
                
                # URL取得
                link = item.get('href') if item.name == 'a' else item.select_one('a')
                if not link:
                    continue
                
                event_url = link if isinstance(link, str) else link.get('href')
                if not event_url.startswith('http'):
                    event_url = f"https://chiikawa-info.jp{event_url}"
                
                # 画像取得
                images = []
                img_elems = item.select('img')
                for img in img_elems[:3]:  # 最大3枚
                    img_url = img.get('src') or img.get('data-src')
                    if img_url:
                        if not img_url.startswith('http'):
                            img_url = f"https:{img_url}" if img_url.startswith('//') else f"https://chiikawa-info.jp{img_url}"
                        images.append(img_url)
                
                # 日付取得
                date_elem = item.select_one('time, .date, .published')
                published = date_elem.get_text(strip=True) if date_elem else datetime.now().isoformat()
                
                results.append({
                    'source_id': generate_source_id(event_url),
                    'title': title,
                    'content': title,
                    'url': event_url,
                    'images': images,
                    'published_at': published
                })
                
            except Exception as e:
                print(f"  ⚠️ 項目スキップ: {e}")
                continue
        
        print(f"  ✅ {len(results)}件取得")
        return results
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return []

# ========================================
# メイン実行
# ========================================

def main():
    """メイン処理"""
    print("=" * 60)
    print("🐭 ちいかわ情報収集開始")
    print("=" * 60)
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_saved = 0
    
    # 1. Twitter
    twitter_items = collect_twitter()
    if twitter_items:
        saved = save_to_db(twitter_items, "twitter")
        print(f"  📊 Twitter: {saved}件を新規保存")
        total_saved += saved
    time.sleep(2)
    
    # 2. ちいかわマーケット
    market_items = collect_chiikawa_market()
    if market_items:
        saved = save_to_db(market_items, "chiikawa_market")
        print(f"  📊 ちいかわマーケット: {saved}件を新規保存")
        total_saved += saved
    time.sleep(2)
    
    # 3. ちいかわインフォ
    info_items = collect_chiikawa_info()
    if info_items:
        saved = save_to_db(info_items, "chiikawa_info")
        print(f"  📊 ちいかわインフォ: {saved}件を新規保存")
        total_saved += saved
    
    print("\n" + "=" * 60)
    print(f"✨ 収集完了！合計 {total_saved} 件の新規情報を保存しました")
    print("=" * 60)

if __name__ == "__main__":
    main()