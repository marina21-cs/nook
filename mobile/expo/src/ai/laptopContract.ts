export type ChatTurn = Readonly<{ role:'user' | 'assistant'; content:string }>;
export const GENERATED_LABEL = 'NOOK · GENERATED · LAPTOP-LOCAL';
export const PERSONAL_CAUTION = 'I can’t confirm personal facts from generated conversation. Ask for a saved item by name, or enter memory details and review the exact preview.';
export function generalConversation(text:string): boolean {
  // Conservative routing, not a semantic security classifier. No vault content
  // ever enters this channel, even if a novel phrasing passes this filter.
  return text.length > 0 && text.length <= 2000 && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text)
    && !/\b(?:remember|recall|save|delete|cancel|schedule|send|email|remind|approve|confirm|tool|function|arguments|memory|memories|vault|system prompt)\b/iu.test(text)
    && !/\b(?:where|when|what|who|how)\b.*\b(?:my|our|mine|i live|i put|i left|i was)\b/iu.test(text);
}
export function validateTurns(value:unknown): ChatTurn[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 7 || value.length % 2 !== 1) throw new Error('invalid_request');
  const turns = value.map((entry,index) => {
    if (!entry || typeof entry !== 'object' || Object.keys(entry).sort().join(',') !== 'content,role'
      || entry.role !== (index % 2 === 0 ? 'user' : 'assistant') || typeof entry.content !== 'string'
      || entry.content.length < 1 || entry.content.length > 2000
      || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(entry.content)) throw new Error('invalid_request');
    if (entry.role === 'user' && !generalConversation(entry.content)) throw new Error('personal_or_action');
    return { role:entry.role, content:entry.content } as ChatTurn;
  });
  if (new TextEncoder().encode(JSON.stringify(turns)).length > 7000) throw new Error('context_limit');
  return turns;
}
export function appendPair(history:ChatTurn[], user:string, reply:string): ChatTurn[] {
  const next:ChatTurn[] = [...history,{ role:'user' as const,content:user },{ role:'assistant' as const,content:reply }].slice(-6);
  while (new TextEncoder().encode(JSON.stringify([...next,{role:'user',content:'x'.repeat(2000)}])).length > 7000) next.splice(0,2);
  return next;
}
export function prepareTurns(history:ChatTurn[],user:string): ChatTurn[] {
  const turns:ChatTurn[]=[...history,{role:'user',content:user}];
  // Budget the actual UTF-8 input, discarding complete old pairs first.
  // Character limits alone do not bound multilingual text bytes.
  while(turns.length>1&&new TextEncoder().encode(JSON.stringify(turns)).length>7000)turns.splice(0,2);
  return validateTurns(turns);
}
export function generatedReply(value:unknown): string {
  if (!value || typeof value !== 'object' || Object.keys(value).join(',') !== 'reply') throw new Error('invalid_output');
  const reply = (value as {reply:unknown}).reply;
  if (typeof reply !== 'string' || !reply.trim() || reply.length > 1600 || new TextEncoder().encode(reply).length > 4096
    || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(reply)
    || /\bI(?:['’]ve| have)?\s+(?:saved|deleted|cancelled|canceled|scheduled|sent|emailed|approved|confirmed|updated|remembered)\b/iu.test(reply)) throw new Error('invalid_output');
  return reply.trim();
}
