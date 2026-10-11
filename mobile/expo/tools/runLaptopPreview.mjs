import { resolve } from 'node:path';
import { mkdir } from 'node:fs/promises';
import { startOwnedRuntime,projectRoot } from './ownedLaptopRuntime.mjs';
import { LaptopProvider } from './laptopProvider.mjs';
import { startPreview } from './serveWebPreview.mjs';
if(process.argv[2]!=='--existing-qwen-only')throw new Error('Explicit --existing-qwen-only is required. Run under the documented model resource guard.');
const out=resolve(projectRoot,'deliverables/nook-laptop-session-'+Date.now());await mkdir(out);
const runtime=await startOwnedRuntime(out);let server;
try {
  const preview=await startPreview(8081,new LaptopProvider({port:runtime.port}));server=preview.server;
  console.log('Guarded laptop conversation: '+preview.url+' · opt in via Setup. Logs: '+out);
  await new Promise(resolve=>{process.once('SIGINT',resolve);process.once('SIGTERM',resolve);setTimeout(resolve,170_000);});
}finally{if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}await runtime.stop();}
