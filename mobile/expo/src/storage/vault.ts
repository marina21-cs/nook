import { nameKey, normalizeDraft, VaultError } from '../domain/memory.ts';
import type { Memory, MemoryDraft, Recall } from '../domain/memory.ts';
import { initializeDatabase } from './database.ts';
import type { Database, SqlConnection } from './database.ts';

export type Preview = Readonly<{
  id: string;
  memoryId: string;
  draft: MemoryDraft;
  expectedVaultRevision: number;
  expiresAt: string;
  payloadJson: string;
}>;
export type SaveResult = Readonly<{ memory: Memory; replayed: boolean }>;
type Row = {
  id: string; kind: 'object'; name: string; location_state: 'known' | 'unknown';
  location_text: string | null; notes: string; observed_at: string; saved_at: string;
  source: 'typed_by_user'; revision: number;
};
type Receipt = { payload_json: string; memory_id: string };
const MAX_PREVIEWS = 20;
const PREVIEW_LIFETIME_MS = 5 * 60 * 1000;

function memory(row: Row): Memory {
  if (row.kind !== 'object' || row.source !== 'typed_by_user' || row.revision !== 1
    || !['known', 'unknown'].includes(row.location_state)
    || (row.location_state === 'known' && !row.location_text)
    || !Number.isFinite(Date.parse(row.observed_at)) || !Number.isFinite(Date.parse(row.saved_at))) {
    throw new VaultError('invalid_record', 'This record needs review. No data was changed.');
  }
  return Object.freeze({
    id: row.id, kind: row.kind, name: row.name,
    location: row.location_state === 'known'
      ? Object.freeze({ state: 'known', text: row.location_text! })
      : Object.freeze({ state: 'unknown' }),
    notes: row.notes, observedAt: row.observed_at, savedAt: row.saved_at,
    source: row.source, revision: row.revision,
  });
}

export class MemoryVault {
  private readonly database: Database;
  private readonly clock: () => Date;
  private readonly uuid: () => string;
  private readonly pending = new Map<string, Preview>();

  private constructor(database: Database, clock: () => Date, uuid: () => string) {
    this.database = database;
    this.clock = clock;
    this.uuid = uuid;
  }
  static async open(database: Database, clock: () => Date, uuid: () => string): Promise<MemoryVault> {
    await initializeDatabase(database);
    return new MemoryVault(database, clock, uuid);
  }
  async preview(input: MemoryDraft): Promise<Preview> {
    const now = this.clock();
    const draft = normalizeDraft(input, now);
    const state = await this.database.one<{ revision: number }>('SELECT revision FROM vault_state WHERE singleton = 1');
    if (!state) throw new VaultError('invalid_vault', 'The vault is unavailable. No data was changed.');
    const id = this.uuid(), memoryId = this.uuid();
    const payloadJson = JSON.stringify({
      schemaVersion: 1, operation: 'create_memory', memoryId,
      expectedVaultRevision: state.revision, draft,
    });
    const result = Object.freeze({ id, memoryId, draft, expectedVaultRevision: state.revision,
      expiresAt: new Date(now.getTime() + PREVIEW_LIFETIME_MS).toISOString(), payloadJson });
    for (const [key, prior] of this.pending) if (Date.parse(prior.expiresAt) <= now.getTime()) this.pending.delete(key);
    if (this.pending.size >= MAX_PREVIEWS) throw new VaultError('preview_limit', 'Cancel an earlier preview before continuing.');
    this.pending.set(id, result);
    return result;
  }
  cancel(previewId: string): void { this.pending.delete(previewId); }

  async approve(previewId: string, reviewedPayloadJson: string, approved: boolean): Promise<SaveResult> {
    if (approved !== true) throw new VaultError('approval_required', 'Choose Save this exact memory to confirm.');
    const result = await this.database.transaction(async (connection) => {
      const receipt = await connection.one<Receipt>('SELECT payload_json, memory_id FROM approval_receipts WHERE operation_key = ?', [previewId]);
      if (receipt) {
        if (receipt.payload_json !== reviewedPayloadJson) throw new VaultError('payload_changed', 'This approval belongs to different details.');
        const saved = await connection.one<Row>('SELECT * FROM memories WHERE id = ?', [receipt.memory_id]);
        if (!saved) throw new VaultError('receipt_missing_record', 'The saved record is unavailable. No replacement was created.');
        return Object.freeze({ memory: memory(saved), replayed: true });
      }
      const preview = this.pending.get(previewId);
      if (!preview) throw new VaultError('preview_missing', 'Review a fresh preview before saving.');
      if (preview.payloadJson !== reviewedPayloadJson) throw new VaultError('payload_changed', 'Details changed. Review a fresh preview.');
      const now = this.clock();
      if (Date.parse(preview.expiresAt) <= now.getTime()) throw new VaultError('preview_expired', 'This preview expired. Review it again.');
      const state = await connection.one<{ revision: number }>('SELECT revision FROM vault_state WHERE singleton = 1');
      if (state?.revision !== preview.expectedVaultRevision) throw new VaultError('stale_preview', 'The vault changed. Review these details again.');
      const draft = preview.draft, savedAt = now.toISOString();
      await connection.run(`INSERT INTO memories
        (id, kind, name, name_key, location_state, location_text, notes, observed_at, saved_at, source, revision)
        VALUES (?, 'object', ?, ?, ?, ?, ?, ?, ?, 'typed_by_user', 1)`,
      [preview.memoryId, draft.name, nameKey(draft.name), draft.location.state,
        draft.location.state === 'known' ? draft.location.text : null, draft.notes, draft.observedAt, savedAt]);
      await connection.run('INSERT INTO approval_receipts (operation_key, payload_json, memory_id, committed_at) VALUES (?, ?, ?, ?)',
        [previewId, reviewedPayloadJson, preview.memoryId, savedAt]);
      await connection.run('UPDATE vault_state SET revision = revision + 1 WHERE singleton = 1');
      const saved = await connection.one<Row>('SELECT * FROM memories WHERE id = ?', [preview.memoryId]);
      if (!saved) throw new VaultError('write_incomplete', 'Save did not complete. Retry this exact preview.');
      return Object.freeze({ memory: memory(saved), replayed: false });
    });
    this.pending.delete(previewId);
    return result;
  }
  async recall(query: string): Promise<Recall> {
    const key = nameKey(query);
    const rows = await this.database.all<Row>('SELECT * FROM memories WHERE name_key = ? ORDER BY observed_at DESC, saved_at DESC, id', [key]);
    if (rows.length === 0) return Object.freeze({ kind: 'not_found', query: query.trim() });
    const matches = rows.map(memory);
    if (matches.length > 1) return Object.freeze({ kind: 'ambiguous', query: query.trim(), matches });
    const found = matches[0]!;
    return Object.freeze({ kind: found.location.state === 'known' ? 'known' : 'unknown', memory: found });
  }
  async recent(): Promise<Memory[]> {
    return (await this.database.all<Row>('SELECT * FROM memories ORDER BY saved_at DESC, id LIMIT 100')).map(memory);
  }
  async byId(id: string): Promise<Memory | null> {
    const row = await this.database.one<Row>('SELECT * FROM memories WHERE id = ?', [id]);
    return row ? memory(row) : null;
  }
  async close(): Promise<void> { this.pending.clear(); await this.database.close(); }
}
