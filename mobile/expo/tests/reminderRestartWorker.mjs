import { randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { MemoryVault } from '../src/storage/vault.ts';
import { ReminderBook } from '../src/storage/reminders.ts';
import { openNodeDatabase } from './nodeDatabase.mjs';
const [mode,filename,previewFile] = process.argv.slice(2);
const clock = () => new Date('2026-10-11T04:00:00.000Z');
let active = false;
const database = openNodeDatabase(filename,(stage,sql) => {
  if (!active) return;
  if ((mode === 'crash-after-reminder' && /INSERT INTO reminders\(/u.test(sql))
    || (mode === 'cancel-crash-after-update' && /UPDATE reminders SET/u.test(sql))
    || (['crash-after-receipt','cancel-crash-after-receipt'].includes(mode) && /INSERT INTO reminder_receipts/u.test(sql))) process.exit(23);
  if (['crash-after-commit','cancel-crash-after-commit'].includes(mode) && stage === 'committed') process.exit(24);
});
const vault = await MemoryVault.open(database,clock,randomUUID);
const book = await ReminderBook.open(database,clock,randomUUID);
if (mode === 'read') console.log(JSON.stringify(await book.recent()));
else if (mode === 'replay') {
  const preview = JSON.parse(readFileSync(previewFile,'utf8'));
  console.log(JSON.stringify(await book.approve(preview.id,preview.payloadJson,true)));
} else {
  let preview = book.preview({ title:'Synthetic queued email',dueAt:'2026-11-01T09:00:00.000Z',channel:'email' });
  if (mode.startsWith('cancel-')) {
    const initial = await book.approve(preview.id,preview.payloadJson,true);
    preview = await book.previewCancel(initial.reminder.id);
  }
  writeFileSync(previewFile,JSON.stringify(preview)); active = true;
  console.log(JSON.stringify(await book.approve(preview.id,preview.payloadJson,true)));
}
await vault.close();
