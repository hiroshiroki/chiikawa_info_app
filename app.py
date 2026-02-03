"""
ちいかわ情報まとめアプリ
Twitter、ちいかわマーケット、ちいかわインフォから情報を表示
"""
import streamlit as st
from supabase import create_client
import json
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(
    page_title="ちいかわ情報まとめ",
    page_icon="🐭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF69B4;
        text-align: center;
        padding: 1rem 0;
    }
    .source-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .badge-twitter {
        background-color: #1DA1F2;
        color: white;
    }
    .badge-market {
        background-color: #FFB6C1;
        color: white;
    }
    .badge-info {
        background-color: #98D8C8;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Supabase接続
@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["supabase_url"],
        st.secrets["supabase_key"]
    )

try:
    supabase = init_supabase()
except Exception as e:
    st.error("⚠️ データベース接続エラー")
    st.info("Streamlit Secretsに `supabase_url` と `supabase_key` を設定してください")
    st.error(f"⚠️ 詳細エラー: {e}")
    st.stop()

# ========================================
# タイトル
# ========================================

st.markdown('<h1 class="main-title">🐭 ちいかわ情報まとめ</h1>', unsafe_allow_html=True)
st.caption("公式Twitter、ちいかわマーケット、ちいかわインフォから自動収集")

# ========================================
# サイドバー：フィルター
# ========================================

with st.sidebar:
    st.header("🔍 フィルター")
    
    # カテゴリ
    category = st.selectbox(
        "カテゴリ",
        ["すべて", "グッズ", "くじ", "イベント", "漫画", "アニメ", "その他"],
        help="カテゴリで絞り込み"
    )
    
    # 情報源
    source_options = {
        "twitter": "🐦 Twitter",
        "chiikawa_market": "🎁 ちいかわマーケット",
        "chiikawa_info": "📰 ちいかわインフォ"
    }
    
    selected_sources = st.multiselect(
        "情報源",
        list(source_options.keys()),
        default=list(source_options.keys()),
        format_func=lambda x: source_options[x],
        help="表示する情報源を選択"
    )
    
    # 期間
    period = st.selectbox(
        "期間",
        ["すべて", "24時間以内", "3日以内", "1週間以内", "1ヶ月以内"],
        help="投稿日で絞り込み"
    )
    
    # 検索
    search_text = st.text_input(
        "🔎 キーワード検索",
        placeholder="例: ぬいぐるみ、イベント",
        help="タイトルや本文を検索"
    )
    
    # 画像フィルター
    only_with_images = st.checkbox(
        "📸 画像ありのみ表示",
        value=False,
        help="画像が含まれる投稿のみ表示"
    )
    
    st.divider()
    
    # リフレッシュボタン
    if st.button("🔄 更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ========================================
# データ取得
# ========================================

@st.cache_data(ttl=300)  # 5分間キャッシュ
def get_information(category, sources, period, search, only_images):
    """データベースから情報を取得"""
    query = supabase.table("information").select("*")
    
    # カテゴリフィルター
    if category != "すべて":
        query = query.eq("category", category)
    
    # 情報源フィルター
    if sources:
        query = query.in_("source", sources)
    
    # 期間フィルター
    if period != "すべて":
        days_map = {
            "24時間以内": 1,
            "3日以内": 3,
            "1週間以内": 7,
            "1ヶ月以内": 30
        }
        date_from = (datetime.now() - timedelta(days=days_map[period])).isoformat()
        query = query.gte("published_at", date_from)
    
    # キーワード検索
    if search:
        query = query.or_(f"title.ilike.%{search}%,content.ilike.%{search}%")
    
    # データ取得
    data = query.order("published_at", desc=True).limit(200).execute()
    
    results = data.data
    
    # 画像フィルター（クライアント側で実施）
    if only_images:
        results = [
            r for r in results
            if r.get('images') and json.loads(r['images'])
        ]
    
    return results

# データ取得実行
try:
    info_list = get_information(
        category,
        selected_sources,
        period,
        search_text,
        only_with_images
    )
except Exception as e:
    st.error(f"データ取得エラー: {e}")
    info_list = []

# ========================================
# 統計表示
# ========================================

st.subheader("📊 統計情報")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("総件数", len(info_list))

with col2:
    twitter_count = len([i for i in info_list if i['source'] == 'twitter'])
    st.metric("🐦 Twitter", twitter_count)

with col3:
    market_count = len([i for i in info_list if i['source'] == 'chiikawa_market'])
    st.metric("🎁 マーケット", market_count)

with col4:
    info_count = len([i for i in info_list if i['source'] == 'chiikawa_info'])
    st.metric("📰 インフォ", info_count)

st.divider()

# ========================================
# 情報一覧表示
# ========================================

if not info_list:
    st.info("📭 該当する情報がありません")
    st.write("フィルターを変更してみてください")
else:
    st.subheader(f"📰 最新情報 ({len(info_list)}件)")
    
    for idx, item in enumerate(info_list):
        with st.container():
            # アイコンとコンテンツを横並び
            col_icon, col_content = st.columns([1, 20])
            
            with col_icon:
                # 情報源別アイコン
                source_icons = {
                    "twitter": "🐦",
                    "chiikawa_market": "🎁",
                    "chiikawa_info": "📰"
                }
                st.markdown(f"### {source_icons.get(item['source'], '📌')}")
            
            with col_content:
                # タイトル
                st.markdown(f"### {item['title']}")
                
                # メタ情報（日付、カテゴリ、ソース）
                meta_col1, meta_col2, meta_col3 = st.columns([2, 1, 2])
                
                with meta_col1:
                    # 日付
                    try:
                        pub_date = item['published_at']
                        if isinstance(pub_date, str):
                            date_str = pub_date[:10] if len(pub_date) >= 10 else pub_date
                        else:
                            date_str = str(pub_date)[:10]
                        st.caption(f"📅 {date_str}")
                    except:
                        st.caption("📅 日付不明")
                
                with meta_col2:
                    # カテゴリ
                    category_emoji = {
                        "グッズ": "🎁",
                        "くじ": "🎲",
                        "イベント": "🎪",
                        "漫画": "📖",
                        "アニメ": "📺",
                        "その他": "📌"
                    }
                    emoji = category_emoji.get(item['category'], "📌")
                    st.caption(f"{emoji} {item['category']}")
                
                with meta_col3:
                    # 情報源
                    source_names = {
                        "twitter": "🐦 Twitter",
                        "chiikawa_market": "🎁 ちいかわマーケット",
                        "chiikawa_info": "📰 ちいかわインフォ"
                    }
                    st.caption(f"📍 {source_names.get(item['source'], item['source'])}")
                
                # 本文（タイトルと異なる場合のみ）
                if item.get('content') and item['content'] != item['title']:
                    content_text = item['content']
                    # HTMLタグを除去
                    from bs4 import BeautifulSoup
                    content_text = BeautifulSoup(content_text, 'html.parser').get_text()
                    
                    # 長すぎる場合は省略
                    if len(content_text) > 300:
                        content_text = content_text[:300] + "..."
                    
                    if content_text.strip():
                        st.write(content_text)
                
                # 画像表示
                if item.get('images'):
                    try:
                        images = json.loads(item['images']) if isinstance(item['images'], str) else item['images']
                        
                        if images and len(images) > 0:
                            st.caption(f"📸 画像 ({len(images)}枚)")
                            
                            # 画像を横並びで表示
                            if len(images) == 1:
                                st.image(images[0], width=400)
                            elif len(images) == 2:
                                img_cols = st.columns(2)
                                for i, img_url in enumerate(images):
                                    with img_cols[i]:
                                        st.image(img_url, use_container_width=True)
                            else:
                                # 3枚以上は3列で表示
                                img_cols = st.columns(3)
                                for i, img_url in enumerate(images[:6]):  # 最大6枚
                                    with img_cols[i % 3]:
                                        st.image(img_url, use_container_width=True)
                    except Exception as e:
                        st.caption(f"⚠️ 画像読み込みエラー")
                
                # リンクボタン
                st.link_button(
                    "🔗 元記事を見る",
                    item['url'],
                    use_container_width=False
                )
            
            # 区切り線
            if idx < len(info_list) - 1:
                st.divider()

# ========================================
# フッター
# ========================================

st.divider()
st.caption("💡 情報は自動収集されます。最新情報は各公式サイトをご確認ください。")
st.caption("©nagano / chiikawa committee")