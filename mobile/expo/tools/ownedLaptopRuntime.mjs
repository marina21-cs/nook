import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream,createWriteStream } from 'node:fs';
import { mkdir,readFile,stat,readdir,readlink } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname,resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:net';
import { localJSON,PINNED_DIGEST } from './laptopProvider.mjs';
export const projectRoot=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
export async function verifyCache() {
  const cache=resolve(projectRoot,'docs/candidates/local-chat-20261010/acquisition/artifacts');
  const manifestBytes=await readFile(resolve(cache,'manifests/registry.ollama.ai/library/qwen2.5/0.5b-instruct-q4_K_M'));
  if(createHash('sha256').update(manifestBytes).digest('hex')!==PINNED_DIGEST)throw new Error('Cache manifest mismatch; no downloads permitted.');
  const manifest=JSON.parse(manifestBytes);
  for(const item of [manifest.config,...manifest.layers]) {
    const path=resolve(cache,'blobs',item.digest.replace(':','-'));
    if((await stat(path)).size!==item.size)throw new Error('Cache blob size mismatch');
    const hash=createHash('sha256');for await(const chunk of createReadStream(path,{highWaterMark:1024*1024}))hash.update(chunk);
    if('sha256:'+hash.digest('hex')!==item.digest)throw new Error('Cache blob digest mismatch');
  }
  // Presence only. Ollama would create a key if this is absent, which is outside scope.
  if(!(await stat(resolve(homedir(),'.ollama/id_ed25519'))).isFile())throw new Error('Existing Ollama key absent; do not create credentials.');
  return cache;
}
export async function startOwnedRuntime(out,port=11439) {
  const cache=await verifyCache();
  const probe=createServer();await new Promise((yes,no)=>{probe.once('error',no);probe.listen(port,'127.0.0.1',yes);});
  await new Promise(resolve=>probe.close(resolve)); // serve rechecks; no existing listener is touched.
  await mkdir(out,{recursive:true});const log=createWriteStream(resolve(out,'owned-ollama.log'),{flags:'wx',mode:0o600});
  const child=spawn('/usr/local/bin/ollama',['serve'],{stdio:['ignore','pipe','pipe'],env:{...process.env,
    OLLAMA_MODELS:cache,OLLAMA_HOST:'127.0.0.1:'+port,OLLAMA_NO_CLOUD:'1',OLLAMA_NOPRUNE:'1',OLLAMA_NUM_PARALLEL:'1',
    OLLAMA_MAX_LOADED_MODELS:'1',OLLAMA_MAX_QUEUE:'1',OLLAMA_CONTEXT_LENGTH:'2048',OLLAMA_LLM_LIBRARY:'cpu_avx2',
    OLLAMA_VULKAN:'0',CUDA_VISIBLE_DEVICES:'',ROCR_VISIBLE_DEVICES:'-1',OMP_NUM_THREADS:'2',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'}});
  child.stdout.pipe(log,{end:false});child.stderr.pipe(log,{end:false});
  let stopped=false,spawnFailure;
  child.once('error',error=>spawnFailure=error);
  const stop=async()=>{
    if(stopped)return;stopped=true;
    if(child.exitCode===null&&child.signalCode===null){
      const ended=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');
      let timer;await Promise.race([ended,new Promise(resolve=>timer=setTimeout(resolve,4000))]);clearTimeout(timer);
      if(child.exitCode===null&&child.signalCode===null){child.kill('SIGKILL');await ended;}
    }
    log.end();
  };
  try {
    for(let i=0;i<60;i++) {
      if(spawnFailure||child.exitCode!==null)throw spawnFailure??new Error('Owned runtime exited');
      try {
        const value=await localJSON(port,'/api/version');if(value.version!=='0.30.6')throw new Error('Unexpected installed runtime version');
        const local='0100007F:'+port.toString(16).toUpperCase().padStart(4,'0');
        const socket=(await readFile('/proc/net/tcp','utf8')).split('\n').map(line=>line.trim().split(/\s+/u)).find(parts=>parts[1]===local&&parts[3]==='0A')?.[9];
        const fds=await readdir('/proc/'+child.pid+'/fd');
        const links=await Promise.all(fds.map(fd=>readlink('/proc/'+child.pid+'/fd/'+fd).catch(()=>'')));
        if(!socket||!links.includes('socket:['+socket+']'))throw new Error('Unexpected listener ownership');
        return {port,pid:child.pid,stop};
      }
      catch(error){if(error.message.startsWith('Unexpected'))throw error;}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw new Error('Owned runtime startup deadline');
  }catch(error){await stop();throw error;}
}
