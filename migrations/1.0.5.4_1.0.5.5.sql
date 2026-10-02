BEGIN TRANSACTION;

-- Items are now tracked per query with their last seen price, so a listing whose
-- price drops into a query's range can be noticed. in_range defaults to 1 so rows
-- recorded before this migration are not announced again.
ALTER TABLE items ADD COLUMN in_range INTEGER NOT NULL DEFAULT 1;

DELETE FROM items
WHERE rowid NOT IN (SELECT MIN(rowid) FROM items GROUP BY item, query_id);

CREATE UNIQUE INDEX IF NOT EXISTS items_item_query ON items (item, query_id);

-- Price filters are applied locally now, so fetch as many listings per call as the
-- API allows to keep older listings in view for price drops.
UPDATE parameters
SET value = '96'
WHERE key = 'items_per_query'
  AND CAST(value AS INTEGER) < 96;

UPDATE parameters
SET value = '1.0.5.5'
WHERE key = 'version';

COMMIT;
