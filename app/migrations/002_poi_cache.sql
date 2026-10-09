-- Explicitly imported offline map cache; never location history or live business data.
CREATE TABLE poi_cache_meta (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    dataset_label TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    imported_epoch REAL NOT NULL,
    source_observed_at TEXT,
    coverage_bounds TEXT NOT NULL
);
CREATE TABLE poi_cache_entries (
    namespace TEXT NOT NULL CHECK (namespace IN ('node', 'way', 'relation')),
    osm_id INTEGER NOT NULL CHECK (osm_id > 0),
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    tags TEXT NOT NULL CHECK (json_valid(tags) AND length(tags) <= 8192),
    lat REAL NOT NULL CHECK (lat >= -90 AND lat <= 90),
    lon REAL NOT NULL CHECK (lon >= -180 AND lon <= 180),
    PRIMARY KEY (namespace, osm_id)
);
CREATE INDEX poi_category ON poi_cache_entries(category);
