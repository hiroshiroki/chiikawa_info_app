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
- 🔔 **再入荷通知機能**
  - 同じ商品が異なる日付で再入荷された場合に履歴を記録
  - Discord Webhookでリアルタイム通知（オプション）
  - 最近7日間の再入荷をアプリ上で確認可能
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
   - `DISCORD_WEBHOOK_URL`: Discord Webhook URL（オプション、再入荷通知用）
   - `DISCORD_SEND_SUMMARY`: `true` または `false`（オプション、収集サマリー通知用）

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

### 4. Discord通知の設定（オプション）

再入荷を検出した際にDiscordで通知を受け取りたい場合：

#### 4-1. Discord Webhook URLの取得

1. Discordサーバー（または個人チャンネル）を開く
2. 通知を受け取りたいチャンネルの設定⚙️を開く
3. 「連携サービス」→「ウェブフック」→「新しいウェブフック」をクリック
4. 名前を「ちいかわ通知」などに変更（任意）
5. 「ウェブフックURLをコピー」をクリック

#### 4-2. GitHub Secretsに登録

1. GitHubリポジトリの `Settings` → `Secrets and variables` → `Actions`
2. 「New repository secret」をクリック
3. Name: `DISCORD_WEBHOOK_URL`、Secret: コピーしたURL を入力
4. 「Add secret」をクリック

#### 4-3. サマリー通知を有効化（オプション）

収集完了時に「新規◯件、再入荷◯件」というサマリーも送信したい場合：

1. 上記と同じ手順で新しいSecretを追加
2. Name: `DISCORD_SEND_SUMMARY`、Secret: `true`

### 5. 再入荷履歴テーブルの作成

SQL Editorで`create_restock_history.sql`を実行：

```sql
-- create_restock_history.sql の内容をコピペして実行
```

### 6. 初回データ収集

GitHub Actionsを手動実行：
1. GitHubリポジトリの「Actions」タブ
2. 「Collect Chiikawa Information」ワークフロー
3. 「Run workflow」をクリック

## 📁 ファイル構成

```
chiikawa-info-app/
├── app.py                         # Streamlitアプリ本体
├── collect.py                     # データ収集スクリプト
├── notifier.py                    # Discord通知モジュール
├── requirements.txt               # 必要なPythonパッケージ
├── create_table.sql               # データベーステーブル定義
├── create_restock_history.sql     # 再入荷履歴テーブル定義
├── CLAUDE.md                      # Claude Code設定ファイル
├── .github/
│   └── workflows/
│       └── collect.yml            # GitHub Actions設定（3時間ごと実行）
└── README.md                      # このファイル
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

restock_history テーブル:
- id: シリアルID
- product_url: 商品URL
- product_title: 商品タイトル
- previous_event_date: 以前の発売日・再入荷日
- new_event_date: 新しい再入荷日
- detected_at: 検出日時
- notified: 通知済みフラグ
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
