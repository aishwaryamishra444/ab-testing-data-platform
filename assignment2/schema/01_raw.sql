-- ============================================================
-- RAW LAYER
-- Landing zone: mirrors the source event schema exactly, no
-- transformation, no type casting beyond what SQLite infers.
-- Everything is loaded as-is (including duplicates/bad rows) so
-- the raw layer is always a faithful copy of what ingestion saw.
-- ============================================================

DROP TABLE IF EXISTS raw_events;

CREATE TABLE raw_events (
    event_id        TEXT,
    user_id         TEXT,
    event_name      TEXT,
    event_timestamp TEXT,   -- kept as raw ISO-8601 text on purpose
    test_group      TEXT,
    platform        TEXT,
    session_id      TEXT,
    properties      TEXT,   -- raw JSON blob, untouched
    _ingested_at    TEXT DEFAULT (datetime('now')),
    _source_file    TEXT
);

CREATE INDEX idx_raw_events_event_id ON raw_events(event_id);
CREATE INDEX idx_raw_events_user_id ON raw_events(user_id);
