import * as SQLite from 'expo-sqlite';
import { DATABASE_NAME } from './database';
import type { Database, SqlConnection, SqlValue } from './database';

// Expo SQLite's web adapter is alpha and does not implement exclusive native
// transactions. Serialize every operation on this owned handle, and use real
// SQLite BEGIN/COMMIT. This qualifies browser flows only, not the Android adapter.
export async function openExpoDatabase(): Promise<Database> {
  if (!globalThis.crossOriginIsolated) throw new Error('SQLite web requires an isolated local origin.');
  const native = await SQLite.openDatabaseAsync(DATABASE_NAME);
  let tail: Promise<unknown> = Promise.resolve();
  const enqueue = <T>(operation: () => Promise<T>): Promise<T> => {
    const result = tail.then(operation);
    tail = result.then(() => undefined, () => undefined); return result;
  };
  const connection: SqlConnection = {
    exec: (sql) => native.execAsync(sql),
    run: async (sql, parameters: SqlValue[] = []) => ({ changes: (await native.runAsync(sql,parameters)).changes }),
    one: <T>(sql: string, parameters: SqlValue[] = []) => native.getFirstAsync<T>(sql,parameters),
    all: <T>(sql: string, parameters: SqlValue[] = []) => native.getAllAsync<T>(sql,parameters),
  };
  return {
    exec: (sql) => enqueue(() => connection.exec(sql)),
    run: (sql, params) => enqueue(() => connection.run(sql,params)),
    one: <T>(sql: string, params?: SqlValue[]) => enqueue(() => connection.one<T>(sql,params)),
    all: <T>(sql: string, params?: SqlValue[]) => enqueue(() => connection.all<T>(sql,params)),
    transaction: <T>(body: (connection: SqlConnection) => Promise<T>) => enqueue(async () => {
      await native.execAsync('BEGIN IMMEDIATE');
      try { const result = await body(connection); await native.execAsync('COMMIT'); return result; }
      catch (failure) { await native.execAsync('ROLLBACK'); throw failure; }
    }),
    close: () => enqueue(() => native.closeAsync()),
  };
}
