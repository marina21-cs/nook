// Separate Metro/Hermes from the resident Gradle JVM to respect the existing
// 1.5 GiB owned-tree guard. Produces the actual release asset, never a stub.
import { spawn } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { createRequire } from 'node:module';
import { bundlePath, projectRoot, receiptPath, resourcesPath, sha256, sourceHashes } from './androidBundleInputs.mjs';

const require = createRequire(join(projectRoot, 'package.json'));
const cli = require.resolve('@expo/cli', { paths: [require.resolve('expo/package.json')] });
const before = sourceHashes();
mkdirSync(dirname(bundlePath), { recursive: true });
mkdirSync(resourcesPath, { recursive: true });
// Match the native Gradle task: run from the project directory, with no extra
// positional directory argument (the pinned CLI rejects that argument).
const args = [cli, 'export:embed', '--platform', 'android', '--dev', 'false',
  '--minify', 'true', '--bytecode', '--max-workers', '1', '--entry-file', join(projectRoot, 'index.ts'),
  '--bundle-output', bundlePath, '--assets-dest', resourcesPath];
console.log(JSON.stringify({ node: process.execPath, args, guardRequired: true }));
const child = spawn(process.execPath, args, { cwd: projectRoot, stdio: 'inherit', env: {
  ...process.env, CI: '1', EXPO_NO_TELEMETRY: '1', EXPO_OFFLINE: '1',
  NODE_OPTIONS: '--max-old-space-size=384',
} });
const code = await new Promise((resolve, reject) => {
  child.once('error', reject);
  child.once('exit', (code) => resolve(code ?? 1));
});
if (code !== 0) process.exit(code);
const after = sourceHashes();
if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Source changed during bundling. No native build may use it.');
const bytes = readFileSync(bundlePath);
if (bytes.subarray(0, 8).toString('hex') !== 'c61fbc03c103191f') throw new Error('Expected a real Hermes bytecode bundle.');
const receipt = { utc: new Date().toISOString(), node: process.version, command: [process.execPath, ...args],
  bundlePath, bundleBytes: bytes.length, bundleSha256: sha256(bytes), sourceHashes: after,
  scope: 'release diagnostic prebundle; no device or production qualification' };
writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
console.log(JSON.stringify(receipt));
