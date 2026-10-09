-- Download provenance is owned by the server, never accepted from imports.
ALTER TABLE poi_cache_meta ADD COLUMN provenance TEXT;
