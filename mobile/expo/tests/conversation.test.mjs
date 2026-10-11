import assert from 'node:assert/strict';
import test from 'node:test';
import { ADAPTER_LABEL, interpret } from '../src/domain/conversation.ts';
const now = new Date('2026-10-11T04:00:00.000Z');
const context = { memoryId:'confirmed-keys',name:'keys' };

test('the conversation adapter explicitly identifies its deterministic prototype', () => {
  assert.match(ADAPTER_LABEL,/prototype/iu); assert.match(ADAPTER_LABEL,/no generative model/iu);
  assert.equal(interpret('Write a poem',null,now).kind,'help');
});
test('natural descriptions produce uncommitted, dated typed-memory candidates', () => {
  for (const phrase of ['Remember my keys are in the hall drawer','I put my keys in the hall drawer',
    'I left the keys in the hall drawer','Remember that keys are in the hall drawer']) {
    const result = interpret(phrase,null,now);
    assert.equal(result.kind,'memory',phrase); assert.equal(result.draft.name,'keys');
    assert.deepEqual(result.draft.location,{ state:'known',text:'in the hall drawer' });
    assert.equal(result.draft.observedAt,now.toISOString());
  }
});
test('unknown and explicitly backdated observations remain distinct from current facts', () => {
  const unknown = interpret('Remember wallet location unknown',null,now);
  assert.equal(unknown.kind,'memory'); assert.equal(unknown.draft.name,'wallet');
  assert.deepEqual(unknown.draft.location,{ state:'unknown' });
  const backdated = interpret('Remember my keys are on the shelf; seen 2026-10-10T09:15:00+08:00',null,now);
  assert.equal(backdated.draft.observedAt,'2026-10-10T01:15:00.000Z');
});
test('uncertain, missing, future and impossible facts request clarification', () => {
  for (const phrase of ['Remember my keys','Remember keys are not on the desk','Remember keys might be in the drawer',
    'Remember keys will be in the drawer','Remember keys are on the shelf; seen 2027-01-01T00:00:00Z',
    'Remember keys are on the shelf; seen 2026-02-30T00:00:00Z']) {
    assert.equal(interpret(phrase,null,now).kind,'clarify',phrase);
  }
});
test('queries remove only articles and preserve exact names for deterministic retrieval', () => {
  for (const phrase of ['Where are my keys?','Where did I put the keys?','Find keys','What about my keys?']) {
    assert.deepEqual(interpret(phrase,null,now),{ kind:'recall',query:'keys',focus:'place' });
  }
  assert.equal(interpret('Where is the red house key?',null,now).query,'red house key');
});
test('follow-ups bind to one confirmed record ID and fail without a selected record', () => {
  for (const phrase of ['Where are they?','Where is it?','When did you see it?','When was it recorded?']) {
    assert.equal(interpret(phrase,null,now).kind,'clarify');
    const result = interpret(phrase,context,now);
    assert.equal(result.memoryId,context.memoryId); assert.equal(result.query,'keys');
  }
  assert.deepEqual(interpret('When was my wallet recorded?',context,now),{ kind:'recall',query:'wallet',focus:'time' });
});
test('conversation cannot approve, send or cancel any hidden mutation', () => {
  for (const phrase of ['yes','OK','save that','do it','confirm','Send all memories to a website','Cancel all reminders']) {
    assert.ok(['clarify','help'].includes(interpret(phrase,context,now).kind),phrase);
  }
});
test('relative reminder time resolves once and channel is explicit', () => {
  const local = interpret('Remind me to water plants in 10 minutes',null,now);
  assert.deepEqual(local,{ kind:'reminder',draft:{ title:'water plants',dueAt:'2026-10-11T04:10:00.000Z',channel:'local' } });
  const email = interpret('Email me to check the bill in 2 hours',null,now);
  assert.deepEqual(email.draft,{ title:'check the bill',dueAt:'2026-10-11T06:00:00.000Z',channel:'email' });
});
test('absolute reminder time uses supplied timezone and refuses vague/recurring requests', () => {
  const result = interpret('Remind me to check the bill at 2026-11-01T09:00:00+08:00',null,now);
  assert.equal(result.draft.dueAt,'2026-11-01T01:00:00.000Z');
  for (const text of ['Remind me tomorrow','Remind me to eat in 0 minutes','Remind me to eat in 999999 days',
    'Email me every day','Remind me to eat at 2026-02-30T09:00:00Z']) assert.equal(interpret(text,null,now).kind,'clarify');
});
test('sensor/provider intents return honest capability states, never fake observations', () => {
  for (const [text,capability] of [['Look around','camera'],['Use voice','voice'],['Set up offline AI','model'],
    ['What shops are near me?','nearby'],['Use cloud AI','cloud']]) {
    assert.deepEqual(interpret(text,context,now),{ kind:'capability',capability });
  }
  assert.deepEqual(interpret('Show my reminders',null,now),{ kind:'show_reminders' });
});
test('oversized and control-character messages cannot form an action', () => {
  for (const text of ['', 'x'.repeat(2001),'Remember keys are in\u0000 drawer']) assert.equal(interpret(text,null,now).kind,'clarify');
});
