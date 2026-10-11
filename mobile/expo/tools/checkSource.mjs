import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const project = resolve(dirname(fileURLToPath(import.meta.url)),'..');
const scripts = ['metro.config.cjs',...['tools','tests','plugins'].flatMap((directory) =>
  readdirSync(resolve(project,directory)).filter((name)=>/\.(?:mjs|cjs)$/u.test(name)).map((name)=>directory+'/'+name))];
const commands = [['node_modules/typescript/bin/tsc','--noEmit'],
  ...scripts.map((script)=>['--check',script]),['node_modules/expo/bin/cli','install','--check']];
for (const args of commands) {
  console.log('CHECK '+args.join(' '));
  const result = spawnSync(process.execPath,args,{ cwd:project,stdio:'inherit',timeout:45_000,
    env:{ ...process.env,PATH:dirname(process.execPath)+':'+process.env.PATH,CI:'1',EXPO_OFFLINE:'1',EXPO_NO_TELEMETRY:'1' } });
  if (result.error || result.status !== 0) { console.error(result.error?.message ?? 'Check failed'); process.exit(result.status ?? 1); }
}
