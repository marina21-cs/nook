import { VaultError } from './memory.ts';

export type ReminderDraft = Readonly<{
  title: string;
  dueAt: string;
  channel: 'local' | 'email';
}>;
export type Reminder = ReminderDraft & Readonly<{
  id: string;
  createdAt: string;
  revision: number;
  status: 'stored_not_scheduled' | 'queued_email' | 'cancelled';
}>;

export function normalizeReminder(input: ReminderDraft, now: Date): ReminderDraft {
  if (!input || typeof input.title !== 'string' || !['local', 'email'].includes(input.channel)) {
    throw new VaultError('invalid_reminder', 'Choose a reminder title and delivery method.');
  }
  const title = input.title.trim();
  if (!title || title.length > 200 || /[\u0000-\u001f\u007f]/u.test(title)) {
    throw new VaultError('invalid_reminder', 'Use a reminder title of 1–200 characters.');
  }
  const timestamp = Date.parse(input.dueAt);
  const zone = input.dueAt?.match(/([+-])(\d\d):(\d\d)$/u);
  const offset = zone ? (Number(zone[2]) * 60 + Number(zone[3])) * (zone[1] === '+' ? 1 : -1) : 0;
  if (typeof input.dueAt !== 'string'
    || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/u.test(input.dueAt)
    || !Number.isFinite(timestamp)
    || new Date(timestamp + offset * 60_000).toISOString().slice(0, 19) !== input.dueAt.slice(0, 19)
    || timestamp <= now.getTime()) {
    throw new VaultError('invalid_reminder_time', 'Choose a future date and time with an explicit timezone.');
  }
  return Object.freeze({ title, dueAt: new Date(timestamp).toISOString(), channel: input.channel });
}

export function reminderStatus(reminder: Reminder, now: Date): string {
  if (reminder.status === 'cancelled') return 'Cancelled · no delivery will be attempted';
  if (reminder.channel === 'email') return 'Email queued locally · account not connected · not sent';
  return Date.parse(reminder.dueAt) <= now.getTime()
    ? 'Due · visible in Nook · device notification not scheduled'
    : 'Saved locally · device notification not scheduled';
}
