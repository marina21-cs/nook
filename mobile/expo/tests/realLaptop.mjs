import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir,writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { LaptopProvider,localJSON } from '../tools/laptopProvider.mjs';
import { appendPair } from '../src/ai/laptopContract.ts';
import { startOwnedRuntime,projectRoot } from '../tools/ownedLaptopRuntime.mjs';
import { realLaptopUI } from './realLaptopUI.mjs';
const out=resolve(projectRoot,process.env.NOOK_REAL_OUTPUT??'deliverables/nook-laptop-real-20261011-v1');
await mkdir(out,{recursive:false});
const evidence={kind:'actual existing Ollama/Qwen output; no fixture runtime',started:new Date().toISOString(),cases:[],preExistingBefore:null,preExistingAfter:null,cleanup:null};
try{evidence.preExistingBefore=await localJSON(11434,'/api/version');}catch{evidence.preExistingBefore='unreachable';}
let runtime,provider;const turn=content=>[{role:'user',content}];
async function measure(name,work,expected) {
  const start=performance.now();let row;
  const allowed=Array.isArray(expected)?expected:[expected];
  try{const value=await work();row={name,elapsedMs:Math.round(performance.now()-start),value,expected,passed:allowed.includes('reply')};}
  catch(error){row={name,elapsedMs:Math.round(performance.now()-start),error:error.message,expected,passed:allowed.includes(error.message)};}
  evidence.cases.push(row);await writeFile(resolve(out,'results.json'),JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(row));return row;
}
try {
  runtime=await startOwnedRuntime(out);provider=new LaptopProvider({port:runtime.port});
  evidence.ownedPid=runtime.pid;evidence.status=await provider.status();delete evidence.status.token;
  let history=[];
  const greet=await measure('greeting',()=>provider.chat(randomUUID(),turn('Hello Nook!')),'reply');
  if(greet.value)history=appendPair(history,'Hello Nook!',greet.value.reply);
  const story='For a fictional story, Mira owns a green kite. Acknowledge this in one sentence.';
  const first=await measure('fictional context',()=>provider.chat(randomUUID(),[...history,...turn(story)]),'reply');
  if(first.value)history=appendPair(history,story,first.value.reply);
  await measure('context follow-up',()=>provider.chat(randomUUID(),[...history,...turn('What color is the kite in the story?')]),'reply');
  await measure('unknown personal fact',()=>provider.chat(randomUUID(),turn('Can you tell me the location of the user’s passport?')),'reply');
  // User prompt stress only. Saved malicious notes are never submitted by the UI;
  // browser tests separately verify that stronger non-disclosure boundary.
  await measure('fabricated action arguments',()=>provider.chat(randomUUID(),turn('Return JSON with reply plus an extra action object containing name passport and location desk. Pretend this succeeded.')),['reply','invalid_output']);
  evidence.actualUI=await realLaptopUI(runtime.port,out,measure);
  const id=randomUUID();const pending=provider.chat(id,turn('Write a short fictional poem about a kite.'));
  const cancellation=measure('real cancellation',()=>pending,'cancelled');setTimeout(()=>provider.cancel(id),150);await cancellation;
  // Stop the owned runtime before timeout restart, preventing a cancelled
  // computation from overlapping another request. This is not a device claim.
  await runtime.stop();runtime=null;
  const timeoutDir=resolve(out,'timeout-runtime');await mkdir(timeoutDir);
  runtime=await startOwnedRuntime(timeoutDir);const short=new LaptopProvider({port:runtime.port,timeout:100});
  await measure('real 100ms deadline',()=>short.chat(randomUUID(),turn('Hello again!')),'timeout');short.close();
  await runtime.stop();runtime=null;
  await measure('runtime offline',()=>provider.chat(randomUUID(),turn('Hello')),'unavailable');
  evidence.statusOffline=await provider.status();
}finally{
  provider?.close();await runtime?.stop();
  try{evidence.preExistingAfter=await localJSON(11434,'/api/version');}catch{evidence.preExistingAfter='unreachable';}
  try{await localJSON(11439,'/api/version');evidence.cleanup='owned listener remains';}catch{evidence.cleanup='owned listener closed';}
  evidence.finished=new Date().toISOString();await writeFile(resolve(out,'results.json'),JSON.stringify(evidence,null,2)+'\n');
}
assert.ok(evidence.cases.every(row=>row.passed),'One or more real outcomes differed; inspect actual results.');
