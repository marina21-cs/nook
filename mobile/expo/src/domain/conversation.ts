import { normalizeDraft } from './memory.ts';
import type { MemoryDraft } from './memory.ts';
import { normalizeReminder } from './reminder.ts';
import type { ReminderDraft } from './reminder.ts';

export type ConversationContext = Readonly<{ memoryId: string; name: string }> | null;
export type Intent =
  | { kind: 'memory'; draft: MemoryDraft }
  | { kind: 'recall'; query: string; memoryId?: string; focus: 'place' | 'time' }
  | { kind: 'reminder'; draft: ReminderDraft }
  | { kind: 'show_reminders' }
  | { kind: 'capability'; capability: 'camera' | 'voice' | 'model' | 'nearby' | 'cloud' }
  | { kind: 'clarify' | 'help'; text: string };

const withoutArticle = (value: string) => value.trim().replace(/^(?:my|the)\s+/iu,'').trim();
export const ADAPTER_LABEL = 'Prototype command interpreter · no generative model';
export const WELCOME = 'Tell me what you want to remember, ask about a saved record, or draft a reminder. I’ll ask you to review every change.';
const HELP = 'This prototype understands a few memory and reminder phrases. Try “Remember my keys are in the hall drawer”, “Where are my keys?” or “Remind me to water plants in 10 minutes”. General AI conversation is not connected yet.';

// A deliberately narrow, deterministic prototype. A later model may propose
// intents through this typed boundary; it never receives approval/write authority.
export function interpret(input: string, context: ConversationContext, now: Date): Intent {
  const text = input.trim();
  if (!text || text.length > 2000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text)) {
    return { kind: 'clarify', text: 'Use a message of 1–2,000 characters.' };
  }
  if (/^(?:yes|yeah|ok|okay|confirm|save that|do it)[.!]?$/iu.test(text)) {
    return { kind: 'clarify', text: 'Use the confirmation button on the exact preview. A chat reply cannot approve a change.' };
  }
  if (/^(?:show|list|what are) (?:my )?reminders[?.!]?$/iu.test(text)) return { kind: 'show_reminders' };
  if (/^(?:can you )?(?:see|look around|use the camera|take a photo|remember this photo|what do you see)[?.!]?$/iu.test(text)) {
    return { kind: 'capability', capability: 'camera' };
  }
  if (/^(?:use )?(?:voice|microphone|mic|listen)[?.!]?$/iu.test(text)) return { kind: 'capability', capability: 'voice' };
  if (/^(?:set up |download )?(?:offline ai|model|local ai)[?.!]?$/iu.test(text)) return { kind: 'capability', capability: 'model' };
  if (/\b(?:nearby|near me)\b/iu.test(text)) return { kind: 'capability', capability: 'nearby' };
  if (/^(?:use |connect )?cloud(?: ai)?[?.!]?$/iu.test(text)) return { kind: 'capability', capability: 'cloud' };

  const reminder = text.match(/^(email me|remind me)(?: to)? (.+?) (?:in (\d+) (minutes?|hours?|days?)|at (\S+))[.!]?$/iu);
  if (reminder) {
    const [,prefix,title,amount,unit,absolute] = reminder;
    const multiple = unit?.toLowerCase().startsWith('minute') ? 60_000
      : unit?.toLowerCase().startsWith('hour') ? 3_600_000 : 86_400_000;
    const delay = Number(amount) * multiple;
    if (!absolute && (!Number.isSafeInteger(delay) || delay <= 0 || delay > 366 * 86_400_000)) {
      return { kind: 'clarify', text: 'Choose a delay between one minute and 366 days, or a future ISO time with a timezone.' };
    }
    try {
      return { kind: 'reminder', draft: normalizeReminder({ title: title!,
        dueAt: absolute ?? new Date(now.getTime() + delay).toISOString(),
        channel: prefix!.toLowerCase() === 'email me' ? 'email' : 'local' },now) };
    } catch { return { kind: 'clarify', text: 'I need a future, unambiguous time. Try “in 10 minutes” or “at 2026-11-01T09:00:00+08:00”.' }; }
  }
  if (/\b(?:remind|email|tomorrow|tonight|every day)\b/iu.test(text)) {
    return { kind: 'clarify', text: 'Choose the exact reminder and time. Use “Remind me to … in 10 minutes” or “… at an ISO time with timezone”. Recurring reminders and email recipients are not configured.' };
  }

  const recall = text.match(/^(?:where (?:is|are)|where did i put|recall|find|what about) (.+?)[?.!]?$/iu);
  const when = text.match(/^when did (?:i|you) (?:see|record) (.+?)[?.!]?$/iu)
    ?? text.match(/^when was (.+?) (?:last )?(?:seen|recorded)[?.!]?$/iu);
  if (recall || when) {
    const raw = withoutArticle(recall?.[1] ?? when?.[1] ?? 'it').replace(/[?.!]$/u,'');
    const pronoun = !raw || /^(?:it|them|they|that)$/iu.test(raw);
    if (pronoun && !context) return { kind: 'clarify', text: 'Which saved item do you mean? Ask by name or choose a dated source card first.' };
    return { kind: 'recall', query: pronoun ? context!.name : raw,
      ...(pronoun ? { memoryId: context!.memoryId } : {}), focus: recall ? 'place' : 'time' };
  }

  const statement = text.match(/^remember(?: that)? (.+)$/iu)?.[1]
    ?? text.match(/^i (?:put|left) (.+)$/iu)?.[1];
  if (statement) {
    const dateParts = statement.split(/\s*;\s*seen\s+/iu);
    if (dateParts.length > 2) return { kind: 'clarify', text: 'Use one observation time after “; seen”, or leave it out.' };
    const facts = dateParts[0]!;
    const unknown = facts.match(/^(.+?)(?:'s)? (?:location (?:is )?|is |are )?unknown[.!]?$/iu);
    const known = facts.match(/^(.+?)\s+(?:(?:is|are)\s+)?((?:in|on|at|under|inside|near|beside)\s+.+?)[.!]?$/iu);
    if (!known && !unknown) return { kind: 'clarify', text: 'Tell me an item and its last place, or say its location is unknown. I won’t fill in a missing fact.' };
    const name = withoutArticle((known ?? unknown)![1]!);
    if (/\b(?:not|maybe|might|will|would|could)\b/iu.test(facts)) {
      return { kind: 'clarify', text: 'Please state what you observed, or use “location unknown”. I won’t turn a guess or a future plan into an observation.' };
    }
    try {
      return { kind: 'memory', draft: normalizeDraft({ kind: 'object',name,
        location: known ? { state: 'known',text: known[2]! } : { state: 'unknown' },
        notes: '',observedAt: dateParts[1]?.trim() ?? now.toISOString() },now) };
    } catch { return { kind: 'clarify', text: 'Those details need review. Use a short item/place and a valid past ISO observation time with timezone.' }; }
  }
  return { kind: 'help', text: HELP };
}
