export type RecordedLocation =
  | Readonly<{ state: 'known'; text: string }>
  | Readonly<{ state: 'unknown' }>;

export type MemoryDraft = Readonly<{
  kind: 'object';
  name: string;
  location: RecordedLocation;
  notes: string;
  observedAt: string;
}>;

export type Memory = MemoryDraft & Readonly<{
  id: string;
  revision: number;
  savedAt: string;
  source: 'typed_by_user';
}>;

export type Recall =
  | Readonly<{ kind: 'not_found'; query: string }>
  | Readonly<{ kind: 'ambiguous'; query: string; matches: Memory[] }>
  | Readonly<{ kind: 'known' | 'unknown'; memory: Memory }>;

export class VaultError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'VaultError';
    this.code = code;
  }
}

function text(value: unknown, field: string, maximum: number, required = true): string {
  if (typeof value !== 'string') throw new VaultError('invalid_draft', `${field} must be text.`);
  const clean = value.trim();
  if ((required && !clean) || clean.length > maximum || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(clean)) {
    throw new VaultError('invalid_draft', `${field} is empty, too long, or contains control characters.`);
  }
  return clean;
}

export function nameKey(name: string): string {
  return text(name, 'Name', 120).normalize('NFKC').replace(/\s+/gu, ' ').toLowerCase();
}

export function normalizeDraft(input: MemoryDraft, now: Date): MemoryDraft {
  if (!input || input.kind !== 'object') throw new VaultError('invalid_draft', 'Choose an object memory.');
  const name = text(input.name, 'Name', 120);
  // Name normalization is for exact retrieval only; preserve the reviewed spelling.
  nameKey(name);
  const notes = text(input.notes, 'Notes', 1500, false);
  if (!input.location || !['known', 'unknown'].includes(input.location.state)) {
    throw new VaultError('invalid_draft', 'Choose a recorded location or unknown.');
  }
  const location: RecordedLocation = input.location.state === 'known'
    ? Object.freeze({ state: 'known', text: text(input.location.text, 'Location', 200) })
    : Object.freeze({ state: 'unknown' });
  // Require a timestamp with a timezone. Date-only or locale guesses are rejected.
  if (typeof input.observedAt !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/u.test(input.observedAt)) {
    throw new VaultError('invalid_date', 'Use an ISO date and time with a timezone.');
  }
  const timestamp = Date.parse(input.observedAt);
  const zone = input.observedAt.match(/([+-])(\d\d):(\d\d)$/u);
  const offset = zone ? (Number(zone[2]) * 60 + Number(zone[3])) * (zone[1] === '+' ? 1 : -1) : 0;
  const calendarMatches = Number.isFinite(timestamp)
    && new Date(timestamp + offset * 60_000).toISOString().slice(0, 19) === input.observedAt.slice(0, 19);
  if (!calendarMatches || timestamp > now.getTime()) {
    throw new VaultError('invalid_date', 'The observation date must be valid and cannot be in the future.');
  }
  return Object.freeze({ kind: 'object', name, location, notes, observedAt: new Date(timestamp).toISOString() });
}
