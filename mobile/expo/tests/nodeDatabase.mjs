// Real on-disk SQLite for portable persistence/atomicity tests, not an in-memory
// repository double. expo-sqlite's installed-device adapter is qualified separately.
import { DatabaseSync } from 'node:sqlite';

export function openNodeDatabase(filename, fault = null) {
  const native = new DatabaseSync(filename);
  let queue = Promise.resolve();
  const connection = {
    exec: async (sql) => { native.exec(sql); },
    run: async (sql, parameters = []) => {
      const result = native.prepare(sql).run(...parameters);
      fault?.('statement', sql);
      return { changes: Number(result.changes) };
    },
    one: async (sql, parameters = []) => native.prepare(sql).get(...parameters) ?? null,
    all: async (sql, parameters = []) => native.prepare(sql).all(...parameters),
  };
  return {
    ...connection,
    transaction(body) {
      const operation = queue.then(async () => {
        native.exec('BEGIN IMMEDIATE');
        try {
          const result = await body(connection);
          native.exec('COMMIT');
          fault?.('committed', 'COMMIT');
          return result;
        } catch (error) {
          native.exec('ROLLBACK');
          throw error;
        }
      });
      queue = operation.then(() => undefined, () => undefined);
      return operation;
    },
    close: async () => { await queue; native.close(); },
  };
}
