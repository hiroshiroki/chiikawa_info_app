"""
ちいかわ情報まとめアプリ
ちいかわマーケットから情報を表示
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
st.caption("ちいかわマーケットから自動収集")

# ========================================
# サイドバー：フィルター
# ========================================

with st.sidebar:
    st.header("🔍 フィルター")
    
    # カテゴリ
    category = st.selectbox(
        "カテゴリ",
        ["すべて", "グッズ"],
        help="カテゴリで絞り込み"
    )
    
    market_status = st.selectbox(
        "商品区分",
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
def fetch_data(category, period, search, only_images, market_status):
    """データベースから情報を取得し、件数とデータリストを返す"""
    
    def build_query():
        query = supabase.table("information").select("*", count='exact')
        
        # ソースはちいかわマーケットのみ
        query = query.eq("source", "chiikawa_market")

        if category != "すべて":
            query = query.eq("category", category)
        
        if period != "すべて":
            days_map = {"24時間以内": 1, "3日以内": 3, "1週間以内": 7, "1ヶ月以内": 30}
            date_from = (datetime.now() - timedelta(days=days_map[period])).isoformat()
            query = query.gte("published_at", date_from)
        
        if search:
            query = query.or_(f"title.ilike.%{search}%,content.ilike.%{search}%")

        if only_images:
            query = query.not_.is_("images", "null")
            query = query.not_.eq("images", '[]')

        if market_status != "すべて":
            status_value = "new" if market_status == "新商品" else "restock"
            query = query.eq("status", status_value)
            
        return query

    try:
        query = build_query()
        # event_dateを優先してソート、NULLの場合はpublished_atでソート
        result = query.order("event_date", desc=True, nullsfirst=False).order("published_at", desc=True).limit(200).execute()
        
        total_count = result.count if result.count is not None else 0
        
        return total_count, result.data

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return 0, []

# データ取得実行
total_count, info_list = fetch_data(
    category,
    period,
    search_text,
    only_with_images,
    market_status
)

# ========================================
# 統計表示
# ========================================

st.subheader(f"📊 {total_count}件の商品が見つかりました")
st.divider()

# ========================================
# 情報一覧表示
# ========================================

if not info_list:
    st.info("📭 該当する情報がありません")
else:
    st.subheader(f"🎁 最新グッズ情報 ({len(info_list)}件)")
    
    # 3アイテムごとに新しい行を作成
    for i in range(0, len(info_list), 3):
        cols = st.columns(3)
        row_items = info_list[i:i+3]
        
        for j, item in enumerate(row_items):
            with cols[j]:
                with st.container(border=True):
                    # 画像表示
                    if item.get('images'):
                        try:
                            images = item['images'] if isinstance(item['images'], list) else json.loads(item['images'])
                            if images:
                                st.image(images[0], use_column_width=True)
                        except:
                            pass
                    
                    # タイトルとステータスバッジ
                    title_html = f"**{item['title']}**"
                    if item.get('status'):
                        status_text = "新商品" if item['status'] == 'new' else "再入荷"
                        status_class = "status-new" if item['status'] == 'new' else "status-restock"
                        title_html += f' <span class="status-badge {status_class}">{status_text}</span>'
                    st.markdown(title_html, unsafe_allow_html=True)
                    
                    # 日付表示 (event_dateを優先)
                    display_date = ""
                    date_prefix = ""

                    if item.get('event_date'):
                        try:
                            date_obj = datetime.strptime(item['event_date'], '%Y-%m-%d')
                            display_date = date_obj.strftime('%m月%d日')
                            if item['status'] == 'new':
                                date_prefix = "発売"
                            elif item['status'] == 'restock':
                                date_prefix = "再入荷"
                        except (ValueError, TypeError):
                             display_date = ""
                    
                    if not display_date and item.get('published_at'):
                        try:
                            published_dt = datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
                            display_date = published_dt.strftime('%Y年%m月%d日')
                            date_prefix = "収集"
                        except (ValueError, TypeError):
                            display_date = ""
                    
                    if display_date:
                        st.caption(f"🗓️ {date_prefix}: {display_date}")

                    # 価格表示
                    if item.get('price'):
                        st.caption(f"💰 {item['price']:,}円")
                    
                    st.link_button("🔗 詳細を見る", item['url'], use_container_width=True)