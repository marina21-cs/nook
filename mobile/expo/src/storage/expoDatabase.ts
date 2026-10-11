import * as SQLite from 'expo-sqlite';
import { DATABASE_NAME } from './database';
import type { Database, SqlConnection, SqlValue } from './database';

function connection(native: SQLite.SQLiteDatabase): SqlConnection {
  return {
    exec: (sql) => native.execAsync(sql),
    run: async (sql, parameters: SqlValue[] = []) => {
      const result = await native.runAsync(sql, parameters);
      return { changes: result.changes };
    },
    one: <T>(sql: string, parameters: SqlValue[] = []) => native.getFirstAsync<T>(sql, parameters),
    all: <T>(sql: string, parameters: SqlValue[] = []) => native.getAllAsync<T>(sql, parameters),
  };
}

export async function openExpoDatabase(): Promise<Database> {
  const native = await SQLite.openDatabaseAsync(DATABASE_NAME);
  return {
    ...connection(native),
    transaction: async <T>(body: (transaction: SqlConnection) => Promise<T>): Promise<T> => {
      let result!: T;
      // Only this transaction connection performs approved writes; unrelated async
      // queries cannot accidentally join the approval commit.
      await native.withExclusiveTransactionAsync(async (transaction) => {
        result = await body(connection(transaction));
      });
      return result;
    },
    close: () => native.closeAsync(),
  };
}
