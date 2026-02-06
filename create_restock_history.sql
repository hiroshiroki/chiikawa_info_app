-- 再入荷履歴テーブル
CREATE TABLE IF NOT EXISTS restock_history (
  id SERIAL PRIMARY KEY,
  product_url TEXT NOT NULL,  -- 商品URL
  product_title TEXT NOT NULL,  -- 商品タイトル
  previous_event_date TEXT,  -- 以前の発売日・再入荷日
  new_event_date TEXT NOT NULL,  -- 新しい再入荷日
  detected_at TIMESTAMP DEFAULT NOW(),  -- 検出日時
  notified BOOLEAN DEFAULT FALSE  -- 通知済みフラグ
);

-- インデックス作成（検索高速化）
CREATE INDEX IF NOT EXISTS idx_restock_product_url ON restock_history(product_url);
CREATE INDEX IF NOT EXISTS idx_restock_detected_at ON restock_history(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_restock_notified ON restock_history(notified);
