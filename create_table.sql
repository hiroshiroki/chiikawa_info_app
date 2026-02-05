-- ちいかわ情報を保存するテーブル
CREATE TABLE IF NOT EXISTS information (
  id SERIAL PRIMARY KEY,
  source TEXT NOT NULL,  -- 'twitter', 'chiikawa_market', 'chiikawa_info'
  source_id TEXT UNIQUE NOT NULL,  -- 重複チェック用のユニークID
  title TEXT NOT NULL,
  content TEXT,
  url TEXT NOT NULL,
  images JSONB,  -- 複数画像対応 ['url1', 'url2', ...]
  price INTEGER, -- 商品の価格（円）
  status TEXT DEFAULT 'new', -- 'new' or 'restock'
  category TEXT,  -- 'グッズ', 'イベント', '漫画', 'くじ', 'その他'
  published_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- インデックス作成（検索高速化）
CREATE INDEX IF NOT EXISTS idx_source ON information(source);
CREATE INDEX IF NOT EXISTS idx_category ON information(category);
CREATE INDEX IF NOT EXISTS idx_published_at ON information(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_created_at ON information(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_status ON information(status);