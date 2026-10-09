CREATE TABLE meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT INTO meta VALUES ('generation', 0);
CREATE TABLE photos (
  id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, width INTEGER NOT NULL,
  height INTEGER NOT NULL, source TEXT NOT NULL, captured_at TEXT,
  recorded_at TEXT NOT NULL, metadata_stripped INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE items (
  id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision >= 1),
  personal_name TEXT NOT NULL, aliases TEXT NOT NULL, distinguishing_note TEXT NOT NULL,
  category TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  current_observation_id TEXT REFERENCES observations(id) ON DELETE SET NULL
);
CREATE TABLE observations (
  id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  photo_id TEXT REFERENCES photos(id) ON DELETE SET NULL,
  region TEXT, candidate_provenance TEXT, location TEXT,
  location_state TEXT NOT NULL CHECK(location_state IN ('recorded', 'unknown')),
  confirmed_at TEXT NOT NULL, observed_at TEXT, provenance TEXT NOT NULL,
  review_after TEXT, evidence_status TEXT NOT NULL
);
CREATE INDEX observations_item ON observations(item_id, confirmed_at);
CREATE INDEX observations_photo ON observations(photo_id);
CREATE TABLE drafts (
  id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, width INTEGER NOT NULL,
  height INTEGER NOT NULL, source TEXT NOT NULL, captured_at TEXT,
  recorded_at TEXT NOT NULL, candidates TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE receipts (
  key TEXT PRIMARY KEY, operation TEXT NOT NULL, fingerprint TEXT NOT NULL,
  result TEXT NOT NULL
);
