# 🐭 ちいかわ情報まとめアプリ

Twitter、ちいかわマーケット、ちいかわインフォから情報を自動収集して表示するWebアプリです。

## 📋 機能

- 🐦 **Twitter公式アカウント**（@ngnchiikawa）から最新ツイートを取得
- 🎁 **ちいかわマーケット**から新商品情報を取得
- 📰 **ちいかわインフォ**からイベント情報を取得
- 📸 **画像表示対応**（ツイート画像、商品画像など）
- 🔍 **検索・フィルター機能**（カテゴリ、期間、キーワード）
- ⏰ **自動収集**（3時間ごとにGitHub Actionsで実行）

## 🚀 セットアップ手順

### 1. Supabaseのセットアップ

1. [Supabase](https://supabase.com)にアクセス
2. 無料アカウント作成
3. 新しいプロジェクト作成
4. SQL Editorで`create_table.sql`を実行してテーブル作成

```sql
-- create_table.sql の内容をコピペして実行
```

5. Settings > API から以下を取得：
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`

### 2. GitHubリポジトリ作成

1. GitHubで新しいリポジトリを作成
2. このプロジェクトをpush

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/chiikawa-info-app.git
git push -u origin main
```

3. Settings > Secrets and variables > Actions で以下を設定：
   - `SUPABASE_URL`: SupabaseのProject URL
   - `SUPABASE_KEY`: Supabaseのanon public key

### 3. Streamlit Community Cloudにデプロイ

1. [Streamlit Community Cloud](https://streamlit.io/cloud)にアクセス
2. GitHubアカウントでログイン
3. 「New app」をクリック
4. リポジトリを選択：
   - Repository: `あなたのユーザー名/chiikawa-info-app`
   - Branch: `main`
   - Main file path: `app.py`
5. Advanced settingsで Secrets を設定：

```toml
supabase_url = "あなたのSupabase Project URL"
supabase_key = "あなたのSupabase anon public key"
```

6. 「Deploy!」をクリック

### 4. 初回データ収集

GitHub Actionsを手動実行：
1. GitHubリポジトリの「Actions」タブ
2. 「Collect Chiikawa Information」ワークフロー
3. 「Run workflow」をクリック

## 📁 ファイル構成

```
chiikawa-info-app/
├── app.py                    # Streamlitアプリ本体
├── collect.py            # データ収集スクリプト
├── requirements.txt          # 必要なPythonパッケージ
├── create_table.sql          # データベーステーブル定義
├── .github/
│   └── workflows/
│       └── collect.yml       # GitHub Actions設定
└── README.md                 # このファイル
```

## 🎯 使い方

### ローカル開発

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
export SUPABASE_URL="your_url"
export SUPABASE_KEY="your_key"

# データ収集テスト
python collect.py

# アプリ起動
streamlit run app.py
```

### Streamlit Secrets（ローカル）

`.streamlit/secrets.toml`を作成：

```toml
supabase_url = "your_url"
supabase_key = "your_key"
```

## 🔧 カスタマイズ

### 収集頻度の変更

`.github/workflows/collect.yml`の`cron`を編集：

```yaml
# 1時間ごとに変更する場合
- cron: '0 * * * *'

# 6時間ごとに変更する場合
- cron: '0 */6 * * *'
```

### カテゴリ判定の調整

`collect.py`の`classify_content`関数を編集：

```python
def classify_content(text: str) -> str:
    keywords = {
        "グッズ": ["グッズ", "発売", "予約", ...],
        # 新しいカテゴリを追加
        "新カテゴリ": ["キーワード1", "キーワード2", ...],
    }
```

## 📊 データベーススキーマ

```sql
information テーブル:
- id: シリアルID
- source: 情報源 (twitter/chiikawa_market/chiikawa_info)
- source_id: ユニークID（重複チェック用）
- title: タイトル
- content: 本文
- url: 元記事URL
- images: 画像URL配列（JSON）
- category: カテゴリ
- published_at: 投稿日時
- created_at: データ作成日時
```

## 🐛 トラブルシューティング

### データが取得できない

1. GitHub Actionsのログを確認
2. Supabaseの接続情報が正しいか確認
3. Nitterインスタンスが落ちている可能性（collect.py参照）

### 画像が表示されない

- 画像URLが正しいか確認
- CORSの問題の可能性あり

### アプリが起動しない

- Streamlit Secretsが正しく設定されているか確認
- requirements.txtのパッケージがすべてインストールされているか確認

## 🙏 クレジット

- ちいかわ: ©nagano / chiikawa committee
- データソース: Twitter、ちいかわマーケット、ちいかわインフォ

## 🔗 リンク

- [ちいかわ公式Twitter](https://twitter.com/ngnchiikawa)
- [ちいかわマーケット](https://chiikawamarket.jp/)
- [ちいかわインフォ](https://chiikawa-info.jp/)