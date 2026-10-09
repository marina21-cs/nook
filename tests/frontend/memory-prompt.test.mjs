import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
const source = await readFile(new URL('../../app/static/memory-prompt.js',import.meta.url),'utf8');
const {parseMemoryPrompt} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('complete messages keep the literal item and place', () => {
  for (const [message,name,location] of [
    ['My keys are in the kitchen drawer.','My keys','in the kitchen drawer'],
    ['Remember my passport is inside the blue folder.','my passport','inside the blue folder'],
    ['I left my wallet on the desk','my wallet','on the desk'],
    ['Please save that the charger is next to the bed','the charger','next to the bed'],
    ['  Red scissors\nunder the sink!  ','Red scissors','under the sink'],
  ]) assert.deepEqual(parseMemoryPrompt(message),{name,location});
});

test('uncertain, multiple, unnamed, or incomplete messages require details', () => {
  for (const message of ['', 'My keys', 'Where are my keys?', 'Maybe my keys are in the drawer',
    'My keys are not in the drawer', 'It is on the desk', 'Keys and wallet in the drawer',
    'Keys in the drawer or on the table', 'Keys in the drawer. Wallet on the table',
    'Keys in the drawer and wallet is on the table', `${'x'.repeat(81)} in the drawer`]) {
    assert.deepEqual(parseMemoryPrompt(message),{name:'',location:''},message);
  }
});
