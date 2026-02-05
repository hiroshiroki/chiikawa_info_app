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
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 10px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-left: 0.5rem;
        border: 1px solid;
    }
    .status-new {
        border-color: #4CAF50;
        color: #4CAF50;
    }
    .status-restock {
        border-color: #FF9800;
        color: #FF9800;
    }
    .uniform-item-container {
        min-height: 300px; /* Adjust as needed */
        overflow-y: auto;
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
        ["すべて", "グッズ", "くじ", "イベント", "食玩", "プライズ", "アニメ", "その他"],
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

    market_status = "すべて"
    if "chiikawa_market" in selected_sources:
        market_status = st.selectbox(
            "ちいかわマーケット商品区分",
            ["すべて", "新商品", "再入荷"],
            help="ちいかわマーケットの商品区分で絞り込み"
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

@st.cache_data(ttl=300)
def get_information(category, sources, period, search, only_images, market_status):
    """データベースから情報を取得"""
    query = supabase.table("information").select("*")
    
    if category != "すべて":
        query = query.eq("category", category)
    
    if sources:
        query = query.in_("source", sources)
    
    if period != "すべて":
        days_map = {"24時間以内": 1, "3日以内": 3, "1週間以内": 7, "1ヶ月以内": 30}
        date_from = (datetime.now() - timedelta(days=days_map[period])).isoformat()
        query = query.gte("published_at", date_from)
    
    if search:
        query = query.or_(f"title.ilike.%{search}%,content.ilike.%{search}%")

    if only_images:
        # 画像が空でない、かつNULLでないものをフィルタリング
        query = query.not_.is_("images", "null")
        query = query.not_.eq("images", '[]')

    if "chiikawa_market" in sources and market_status != "すべて":
        status_value = "new" if market_status == "新商品" else "restock"
        query = query.eq("status", status_value)
        
    data = query.order("published_at", desc=True).limit(200).execute()
    return data.data

# データ取得実行
try:
    info_list = get_information(
        category,
        selected_sources,
        period,
        search_text,
        only_with_images,
        market_status
    )
except Exception as e:
    st.error(f"データ取得エラー: {e}")
    info_list = []

# ========================================
# 統計表示
# ========================================

st.subheader("📊 統計情報")
col1, col2, col3, col4 = st.columns(4)
col1.metric("総件数", len(info_list))
col2.metric("🐦 Twitter", len([i for i in info_list if i['source'] == 'twitter']))
col3.metric("🎁 マーケット", len([i for i in info_list if i['source'] == 'chiikawa_market']))
col4.metric("📰 インフォ", len([i for i in info_list if i['source'] == 'chiikawa_info']))
st.divider()

# ========================================
# 情報一覧表示
# ========================================

if not info_list:
    st.info("📭 該当する情報がありません")
else:
    st.subheader(f"📰 最新情報 ({len(info_list)}件)")
    
    # 3列で表示
    cols = st.columns(3)
    
    for idx, item in enumerate(info_list):
        with cols[idx % 3]:
            with st.container(border=True, height=300):
                # 画像表示
                if item.get('images'):
                    try:
                        images = item['images'] if isinstance(item['images'], list) else json.loads(item['images'])
                        if images:
                            st.image(images[0], width=150) # 最初の画像のみを固定幅で表示
                    except:
                        pass
                
                # タイトルとステータスバッジ
                title_html = f"**{item['title']}**"
                if item['source'] == 'chiikawa_market' and item.get('status'):
                    status_text = "新商品" if item['status'] == 'new' else "再入荷"
                    status_class = "status-new" if item['status'] == 'new' else "status-restock"
                    title_html += f'<span class="status-badge {status_class}">{status_text}</span>'
                st.markdown(title_html, unsafe_allow_html=True)
                
                # メタ情報
                # pub_date = item['published_at']
                # date_str = pub_date.split('T')[0] if isinstance(pub_date, str) else str(pub_date).split(' ')[0]
                # st.caption(f"📅 {date_str}")
                
                category_emoji = {"グッズ": "🎁", "くじ": "🎲", "イベント": "🎪", "食玩": "🍬", "プライズ": "🏆", "アニメ": "📺", "その他": "📌"}
                emoji = category_emoji.get(item['category'], "📌")
                st.caption(f"{emoji} {item['category']}")
                
                source_names = {"twitter": "🐦 Twitter", "chiikawa_market": "🎁 ちいかわマーケット", "chiikawa_info": "📰 ちいかわインフォ"}
                st.caption(f"📍 {source_names.get(item['source'], item['source'])}")

                # 価格表示
                if item.get('price'):
                    st.caption(f"💰 {item['price']:,}円")
                
                st.link_button("🔗 詳細を見る", item['url'], use_container_width=True)


st.divider()
st.caption("💡 情報は自動収集されます。最新情報は各公式サイトをご確認ください。")
st.caption("©nagano / chiikawa committee")