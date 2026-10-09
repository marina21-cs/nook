-- A compact replay barrier survives receipt pruning and whole-collection resets.
INSERT OR IGNORE INTO meta(key,value) VALUES ('write_epoch',0);
