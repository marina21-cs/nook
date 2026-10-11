import { readFileSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { MemoryVault } from '../src/storage/vault.ts';
import { openNodeDatabase } from './nodeDatabase.mjs';

const [mode, filename, previewFile] = process.argv.slice(2);
const clock = () => new Date('2026-10-11T04:00:00.000Z');
const database = openNodeDatabase(filename, (stage, sql) => {
  if ((mode === 'crash-after-memory' && /INSERT INTO memories/u.test(sql))
    || (mode === 'crash-after-receipt' && /INSERT INTO approval_receipts/u.test(sql))) process.exit(23);
  if (mode === 'crash-after-commit' && stage === 'committed' && modeHasSavedPreview) process.exit(24);
});
let modeHasSavedPreview = false;
const vault = await MemoryVault.open(database, clock, randomUUID);
if (mode === 'recall') {
  console.log(JSON.stringify(await vault.recall('Keys')));
} else if (mode === 'replay') {
  const preview = JSON.parse(readFileSync(previewFile, 'utf8'));
  console.log(JSON.stringify(await vault.approve(preview.id, preview.payloadJson, true)));
} else {
  const preview = await vault.preview({ kind: 'object', name: 'Keys', location: { state: 'known', text: 'Hall drawer' },
    notes: 'Synthetic persistence fixture', observedAt: '2026-10-10T09:15:00.000Z' });
  writeFileSync(previewFile, JSON.stringify(preview));
  modeHasSavedPreview = true;
  console.log(JSON.stringify(await vault.approve(preview.id, preview.payloadJson, true)));
}
await vault.close();
