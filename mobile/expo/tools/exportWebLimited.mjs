import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const project = resolve(dirname(fileURLToPath(import.meta.url)),'..');
const child = spawn(process.execPath,['--max-old-space-size=384',resolve(project,'node_modules/expo/bin/cli'),
  'export','--platform','web','--max-workers','1','--output-dir','dist/chat-web'],{
  cwd:project,stdio:'inherit',env:{ ...process.env,
    PATH:dirname(process.execPath)+':'+process.env.PATH,CI:'1',EXPO_OFFLINE:'1',EXPO_NO_TELEMETRY:'1',NODE_ENV:'production' },
});
child.on('error',(failure) => { console.error(failure.message); process.exitCode=1; });
child.on('exit',(code,signal) => { process.exitCode=code ?? (signal ? 1 : 0); });
