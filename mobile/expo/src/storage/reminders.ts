import { VaultError } from '../domain/memory.ts';
import { normalizeReminder } from '../domain/reminder.ts';
import type { Reminder, ReminderDraft } from '../domain/reminder.ts';
import type { Database } from './database.ts';

export type ReminderPreview = Readonly<{
  id: string;
  action: 'create_reminder' | 'cancel_reminder';
  reminderId: string;
  draft: ReminderDraft;
  expectedRevision: number;
  expiresAt: string;
  payloadJson: string;
}>;
type Row = { id: string; title: string; due_at: string; channel: ReminderDraft['channel'];
  created_at: string; revision: number; status: Reminder['status'] };
const SCHEMA = `
CREATE TABLE assistant_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL);
INSERT INTO assistant_schema VALUES (1,1);
CREATE TABLE reminders (
  id TEXT PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
  due_at TEXT NOT NULL, channel TEXT NOT NULL CHECK(channel IN ('local','email')),
  created_at TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1),
  status TEXT NOT NULL CHECK(status IN ('stored_not_scheduled','queued_email','cancelled')),
  dedup_key TEXT NOT NULL UNIQUE,
  CHECK(status='cancelled' OR (channel='local' AND status='stored_not_scheduled') OR (channel='email' AND status='queued_email'))
);
CREATE TABLE reminder_receipts (
  operation_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
  reminder_id TEXT NOT NULL REFERENCES reminders(id), committed_at TEXT NOT NULL
);
`;
function fromRow(row: Row): Reminder {
  if (!['local','email'].includes(row.channel) || !['stored_not_scheduled','queued_email','cancelled'].includes(row.status)
    || !Number.isFinite(Date.parse(row.due_at)) || !Number.isFinite(Date.parse(row.created_at)) || row.revision < 1) {
    throw new VaultError('invalid_reminder_record', 'This reminder needs review. No data was changed.');
  }
  return Object.freeze({ id: row.id, title: row.title, dueAt: row.due_at,
    channel: row.channel, createdAt: row.created_at, revision: row.revision, status: row.status });
}

// A versioned, additive extension. The tested memory tables/schema and receipts
// retain their existing semantics; no OS scheduler or email transport exists here.
export class ReminderBook {
  private readonly database: Database;
  private readonly clock: () => Date;
  private readonly uuid: () => string;
  private readonly pending = new Map<string, ReminderPreview>();
  private constructor(database: Database, clock: () => Date, uuid: () => string) {
    this.database = database; this.clock = clock; this.uuid = uuid;
  }
  static async open(database: Database, clock: () => Date, uuid: () => string): Promise<ReminderBook> {
    await database.transaction(async (connection) => {
      const exists = await connection.one<{ name: string }>("SELECT name FROM sqlite_master WHERE type='table' AND name='assistant_schema'");
      if (!exists) await connection.exec(SCHEMA);
      const state = await connection.one<{ version: number }>('SELECT version FROM assistant_schema WHERE singleton=1');
      if (state?.version !== 1) throw new VaultError('unsupported_reminder_schema', 'Unsupported reminder schema. No data was reset.');
    });
    return new ReminderBook(database, clock, uuid);
  }
  private make(action: ReminderPreview['action'], reminderId: string, draft: ReminderDraft, expectedRevision: number): ReminderPreview {
    const now = this.clock();
    for (const [key, prior] of this.pending) if (Date.parse(prior.expiresAt) <= now.getTime()) this.pending.delete(key);
    if (this.pending.size >= 20) throw new VaultError('preview_limit', 'Cancel an earlier preview before continuing.');
    const id = this.uuid(), expiresAt = new Date(now.getTime() + 300_000).toISOString();
    const payloadJson = JSON.stringify({ schemaVersion: 1, action, reminderId, draft, expectedRevision, expiresAt });
    const result = Object.freeze({ id, action, reminderId, draft: Object.freeze({ ...draft }), expectedRevision, expiresAt, payloadJson });
    this.pending.set(id, result); return result;
  }
  preview(input: ReminderDraft): ReminderPreview {
    return this.make('create_reminder', this.uuid(), normalizeReminder(input, this.clock()), 0);
  }
  async previewCancel(id: string): Promise<ReminderPreview> {
    const row = await this.database.one<Row>('SELECT * FROM reminders WHERE id=?', [id]);
    if (!row) throw new VaultError('reminder_missing', 'This reminder is unavailable.');
    const reminder = fromRow(row);
    if (reminder.status === 'cancelled') throw new VaultError('already_cancelled', 'This reminder is already cancelled.');
    return this.make('cancel_reminder', id,
      { title: reminder.title, dueAt: reminder.dueAt, channel: reminder.channel }, reminder.revision);
  }
  cancelPreview(id: string): void { this.pending.delete(id); }
  discardPreviews(): void { this.pending.clear(); }
  async approve(id: string, payloadJson: string, approved: boolean): Promise<{ reminder: Reminder; replayed: boolean }> {
    if (approved !== true) throw new VaultError('approval_required', 'Use the button on the exact reminder preview to confirm.');
    const result = await this.database.transaction(async (connection) => {
      const receipt = await connection.one<{ payload_json: string; reminder_id: string }>('SELECT payload_json,reminder_id FROM reminder_receipts WHERE operation_key=?', [id]);
      if (receipt) {
        if (receipt.payload_json !== payloadJson) throw new VaultError('payload_changed', 'This approval belongs to different reminder details.');
        const row = await connection.one<Row>('SELECT * FROM reminders WHERE id=?', [receipt.reminder_id]);
        if (!row) throw new VaultError('receipt_missing_record', 'The reminder is unavailable. No replacement was created.');
        // Replays report current status, including cancellation; never resurrect a job.
        return { reminder: fromRow(row), replayed: true };
      }
      const preview = this.pending.get(id);
      if (!preview) throw new VaultError('preview_missing', 'Review a fresh reminder preview.');
      if (preview.payloadJson !== payloadJson) throw new VaultError('payload_changed', 'Reminder details changed. Review them again.');
      const now = this.clock();
      if (Date.parse(preview.expiresAt) <= now.getTime()) throw new VaultError('preview_expired', 'This reminder preview expired. Review it again.');
      if (preview.action === 'create_reminder') {
        const draft = normalizeReminder(preview.draft, now);
        const dedup = JSON.stringify({ ...draft, title: draft.title.normalize('NFKC').replace(/\s+/gu,' ').toLowerCase() });
        const duplicate = await connection.one<Row>('SELECT * FROM reminders WHERE dedup_key=?', [dedup]);
        if (duplicate) throw new VaultError('duplicate_reminder', 'A reminder with these exact details already exists. Check Reminders before creating another.');
        await connection.run('INSERT INTO reminders(id,title,due_at,channel,created_at,revision,status,dedup_key) VALUES(?,?,?,?,?,1,?,?)',
          [preview.reminderId,draft.title,draft.dueAt,draft.channel,now.toISOString(),
            draft.channel === 'email' ? 'queued_email' : 'stored_not_scheduled',dedup]);
      } else {
        const row = await connection.one<Row>('SELECT * FROM reminders WHERE id=?', [preview.reminderId]);
        if (!row || row.revision !== preview.expectedRevision || row.status === 'cancelled') {
          throw new VaultError('stale_preview', 'The reminder changed. Review its current status again.');
        }
        await connection.run("UPDATE reminders SET status='cancelled',revision=revision+1 WHERE id=? AND revision=?", [preview.reminderId,preview.expectedRevision]);
      }
      await connection.run('INSERT INTO reminder_receipts(operation_key,payload_json,reminder_id,committed_at) VALUES(?,?,?,?)',
        [id,payloadJson,preview.reminderId,now.toISOString()]);
      const row = await connection.one<Row>('SELECT * FROM reminders WHERE id=?', [preview.reminderId]);
      if (!row) throw new VaultError('write_incomplete', 'Could not confirm the reminder. Retry this exact preview.');
      return { reminder: fromRow(row), replayed: false };
    });
    this.pending.delete(id); return result;
  }
  async recent(): Promise<Reminder[]> {
    return (await this.database.all<Row>('SELECT * FROM reminders ORDER BY due_at,id LIMIT 100')).map(fromRow);
  }
}
