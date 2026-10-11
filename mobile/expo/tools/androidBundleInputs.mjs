import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const bundlePath = join(projectRoot, 'android/app/build/generated/assets/react/release/index.android.bundle');
export const resourcesPath = join(projectRoot, 'android/app/build/generated/res/react/release');
export const receiptPath = join(projectRoot, 'android/.nook-prebundled-release.json');
export const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

// Include application code, configuration and lockfile. A native-only build
// must refuse an old prebundle when any of these reviewed inputs change.
export function sourceHashes() {
  const files = ['App.tsx', 'index.ts', 'app.json', 'package.json', 'package-lock.json'];
  function walk(relative) {
    const directory = join(projectRoot, relative);
    if (!existsSync(directory)) return;
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = `${relative}/${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error(`Review symlinked build input: ${path}`);
      if (entry.isDirectory()) walk(path);
      else if (entry.isFile()) files.push(path);
    }
  }
  for (const directory of ['src', 'assets', 'plugins']) walk(directory);
  for (const filename of ['babel.config.js', 'babel.config.cjs', 'metro.config.js', 'metro.config.cjs']) {
    if (existsSync(join(projectRoot, filename))) files.push(filename);
  }
  return Object.fromEntries(files.sort().map((path) => [path, sha256(readFileSync(join(projectRoot, path)))]));
}

export function verifiedBundle() {
  if (!existsSync(receiptPath) || !existsSync(bundlePath)) throw new Error('Generate the guarded Android prebundle first.');
  const receipt = JSON.parse(readFileSync(receiptPath, 'utf8'));
  if (JSON.stringify(receipt.sourceHashes) !== JSON.stringify(sourceHashes())) throw new Error('Prebundle source changed. Rebuild it before native assembly.');
  if (receipt.bundleSha256 !== sha256(readFileSync(bundlePath))) throw new Error('Prebundle bytes changed. Rebuild it before native assembly.');
  return receipt;
}
