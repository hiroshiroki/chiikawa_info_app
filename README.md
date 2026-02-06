# 🐭 ちいかわ情報まとめアプリ

ちいかわマーケットから新商品・再入荷情報を自動収集して表示するWebアプリです。

## 📋 機能

- 🎁 **ちいかわマーケット**から新商品・再入荷情報を自動収集
  - 日付別コレクションページに対応
  - 新商品/再入荷の区分表示
  - 発売日・再入荷日の自動抽出
- 📸 **画像表示対応**（商品画像を自動取得）
- 🔍 **多彩なフィルター機能**
  - 商品区分（新商品/再入荷）
  - 期間指定（24時間以内、3日以内、1週間以内、1ヶ月以内）
  - 特定日付指定（発売日・再入荷日で絞り込み）
  - キーワード検索
  - 画像ありのみ表示
- ⏰ **自動収集**（3時間ごとにGitHub Actionsで実行）
- 💰 **価格表示対応**

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
├── collect.py                # データ収集スクリプト
├── requirements.txt          # 必要なPythonパッケージ
├── create_table.sql          # データベーステーブル定義
├── CLAUDE.md                 # Claude Code設定ファイル
├── .github/
│   └── workflows/
│       └── collect.yml       # GitHub Actions設定（3時間ごと実行）
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

## 📊 データベーススキーマ

```sql
information テーブル:
- id: シリアルID
- source: 情報源（現在は 'chiikawa_market' のみ）
- source_id: ユニークID（重複チェック用）
- title: 商品名
- content: 説明文
- url: 商品ページURL
- images: 画像URL配列（JSONB）
- price: 価格（円）
- status: 商品区分（'new' or 'restock'）
- category: カテゴリ（現在は 'グッズ' のみ）
- published_at: 収集日時
- event_date: 発売日・再入荷日（YYYY-MM-DD形式）
- created_at: データ作成日時
```

## 🐛 トラブルシューティング

### データが取得できない

1. GitHub Actionsのログを確認
2. Supabaseの接続情報が正しいか確認
3. ちいかわマーケットのサイト構造が変わった可能性

### 画像が表示されない

- 画像URLが正しいか確認
- ちいかわマーケット側の画像URLが変更された可能性

### アプリが起動しない

- Streamlit Secretsが正しく設定されているか確認
- requirements.txtのパッケージがすべてインストールされているか確認

## 🙏 クレジット

- ちいかわ: ©nagano / chiikawa committee
- データソース: [ちいかわマーケット](https://chiikawamarket.jp/)

## 🔗 リンク

- [ちいかわ公式Twitter](https://twitter.com/ngnchiikawa)
- [ちいかわマーケット](https://chiikawamarket.jp/)
