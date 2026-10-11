export type SqlValue = string | number | null;
export interface SqlConnection {
  exec(sql: string): Promise<void>;
  run(sql: string, parameters?: SqlValue[]): Promise<{ changes: number }>;
  one<T>(sql: string, parameters?: SqlValue[]): Promise<T | null>;
  all<T>(sql: string, parameters?: SqlValue[]): Promise<T[]>;
}
export interface Database extends SqlConnection {
  transaction<T>(body: (connection: SqlConnection) => Promise<T>): Promise<T>;
  close(): Promise<void>;
}

// Application-owned SQLite file; never opens the hackathon or an imported database.
export const DATABASE_NAME = 'nook-local-memory-v1.sqlite';
const SCHEMA = `
CREATE TABLE vault_state (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  revision INTEGER NOT NULL CHECK(revision >= 0)
);
INSERT INTO vault_state VALUES (1, 0);
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind = 'object'),
  name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
  name_key TEXT NOT NULL,
  location_state TEXT NOT NULL CHECK(location_state IN ('known', 'unknown')),
  location_text TEXT,
  notes TEXT NOT NULL CHECK(length(notes) <= 1500),
  observed_at TEXT NOT NULL,
  saved_at TEXT NOT NULL,
  source TEXT NOT NULL CHECK(source = 'typed_by_user'),
  revision INTEGER NOT NULL CHECK(revision = 1),
  CHECK((location_state = 'known' AND location_text IS NOT NULL AND length(location_text) BETWEEN 1 AND 200)
    OR (location_state = 'unknown' AND location_text IS NULL))
);
CREATE INDEX memories_name_key ON memories(name_key);
CREATE TABLE approval_receipts (
  operation_key TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  memory_id TEXT NOT NULL UNIQUE REFERENCES memories(id),
  committed_at TEXT NOT NULL
);
PRAGMA user_version = 1;
`;

export async function initializeDatabase(database: Database): Promise<void> {
  await database.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 3000;');
  await database.transaction(async (connection) => {
    const row = await connection.one<{ user_version: number }>('PRAGMA user_version');
    if (row?.user_version === 0) await connection.exec(SCHEMA);
    else if (row?.user_version !== 1) throw new Error('Unsupported vault schema. No data was reset.');
  });
}
