// One real STT and one real TTS through the browser UI. Device acquisition alone
// is replaced with cached synthetic PCM; no endpoint/model output is mocked.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || require('node:path').join(require('node:os').homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {spawn} = require('node:child_process');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const crypto = require('node:crypto'), assert = require('node:assert/strict');
const ROOT = path.resolve(__dirname, '..'), OUT = path.join(ROOT, 'voice/evidence');
const name = process.argv[2];
if (!name || !/^[a-z0-9-]+$/.test(name)) throw Error('Supply a fresh evidence name');
const evidencePath=path.join(OUT,`${name}.json`);
if(fs.existsSync(evidencePath))throw Error('Preserve existing evidence');
const input=fs.readFileSync(path.join(OUT,'kokoro-readback-16k.wav'));
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(sha(input),'76da9b0d60504ee41e7c1aa00cbeb0756ec6885961dce94075e2b63021b087d2');
const base='http://127.0.0.1:8765', temp=fs.mkdtempSync(path.join(os.tmpdir(),'frontend-real-voice-'));
const result={passed:false,fixture_sha256:sha(input),scope:'Cached synthetic memory-description input; scripted explicit transcript review/edit; no human accuracy acceptance',device_scope:'Microphone/AudioContext acquisition replaced with cached PCM; real application WAV encoder, HTTP endpoints, Whisper tiny and Kokoro inference',stt_requests:0,tts_requests:0,external_requests:[],page_errors:[],server_stopped:false,worker_stopped:false,worker_guard_dimm_c:52};
let server,browser,worker; const log=fs.openSync(path.join(OUT,`${name}-server.log`),'w');
const save=()=>fs.writeFileSync(evidencePath,JSON.stringify(result,null,2)+'\n');
function workerIdentity(){const children=fs.readFileSync(`/proc/${server.pid}/task/${server.pid}/children`,'utf8').trim().split(/\s+/).filter(Boolean);const found=children.filter(pid=>fs.readFileSync(`/proc/${pid}/cmdline`,'utf8').includes('scripts/voice_worker.py'));assert.equal(found.length,1);const pid=Number(found[0]);return {pid,start_ticks:fs.readFileSync(`/proc/${pid}/stat`,'utf8').split(')')[1].trim().split(/\s+/)[19]};}
async function snapshot(page){return page.evaluate(async()=>{const s=await(await fetch('/api/status')).json();const items=await(await fetch('/api/items')).json();return {generation:s.generation,item_count:s.item_count,items:items.items};});}
(async()=>{save();try{
 const env={...process.env,APP_DATA_DIR:temp,APP_PORT:'8765',APP_VISION_DISABLED:'1',APP_VOICE_ENABLED:'1',APP_VOICE_TEST_GUARD_54:'0',APP_TEXT_MODEL:''};
 server=spawn(process.env.APP_TEST_PYTHON || path.join(ROOT,'.venv/bin/python'),['-m','app'],{cwd:ROOT,env,stdio:['ignore',log,log]});result.server_pid=server.pid;
 let ready=false;const started=Date.now();
 for(let i=0;i<80;i++){if(server.exitCode!==null)throw Error('Owned server exited before readiness; port may be occupied');try{if(!fs.readFileSync(path.join(OUT,`${name}-server.log`),'utf8').includes(`Uvicorn running on ${base}`)){await new Promise(r=>setTimeout(r,100));continue;}const r=await fetch(base+'/api/status');if(r.ok){result.status=await r.json();ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
 assert.ok(ready);assert.ok(result.status.speech.provider_enabled&&result.status.speech.artifacts_present);result.readiness_ms=Date.now()-started;
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE || path.join(os.homedir(),'.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'),args:['--disable-gpu','--renderer-process-limit=2']});
 const context=await browser.newContext({viewport:{width:1100,height:1000}});
 await context.route('**/*',route=>{if(!route.request().url().startsWith(base+'/')){result.external_requests.push(route.request().url());return route.abort();}return route.continue();});
 await context.addInitScript(b64=>{
  const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),view=new DataView(bytes.buffer),samples=new Float32Array((bytes.length-44)/2);
  for(let i=0;i<samples.length;i++){const value=view.getInt16(44+2*i,true);samples[i]=value/(value<0?32768:32767);}
  window.fixtureTracksStopped=0;
  Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks:()=>[{stop:()=>window.fixtureTracksStopped++}]})});
  window.AudioContext=class{constructor(){this.sampleRate=16000;this.state='running';this.audioWorklet={addModule:async()=>{}};this.destination={};}createMediaStreamSource(){return{connect(){},disconnect(){}};}resume(){return Promise.resolve();}close(){this.state='closed';return Promise.resolve();}};
  window.AudioWorkletNode=class{constructor(){this.port={onmessage:null};}connect(){setTimeout(()=>{this.port.onmessage?.({data:samples});window.fixturePCMDelivered=true;},20);}disconnect(){}};
 },input.toString('base64'));
 const page=await context.newPage();page.setDefaultTimeout(35000);page.on('pageerror',e=>result.page_errors.push(e.message));
 page.on('request',r=>{if(r.url().endsWith('/api/speech/transcribe'))result.stt_requests++;if(r.url().endsWith('/api/speech/turns'))result.tts_requests++;});
 await page.goto(base);await page.locator('#onboard-next').click();await page.locator('#onboarding').waitFor({state:'hidden'});await page.waitForFunction(()=>!document.querySelector('#record').disabled);result.browser_speech_ready=true;
 result.seed=await page.evaluate(async()=>{const session=await(await fetch('/api/session')).json();const status=await(await fetch('/api/status')).json();const r=await fetch('/api/items',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token},body:JSON.stringify({confirmed:true,write_epoch:status.write_epoch,idempotency_key:crypto.randomUUID(),personal_name:'blue keys',location:'Desk drawer'})});if(!r.ok)throw Error('Fixture seed failed');return await r.json();});
 // Reload so the application obtains the cookie/CSRF pair issued for its own session.
 await page.reload();await page.waitForFunction(()=>!document.querySelector('#record').disabled);const before=await snapshot(page);result.before=before;
 await page.locator('#record').click();await page.waitForFunction(()=>window.fixturePCMDelivered===true);const sttStart=Date.now();
 const sttResponse=page.waitForResponse(r=>r.url().endsWith('/api/speech/transcribe'));
 await page.locator('#stop-record').click();const transcribed=await sttResponse;result.transcription_status=transcribed.status();result.transcription=await transcribed.json();result.stt_http_ms=Date.now()-sttStart;save();assert.equal(result.transcription_status,200,JSON.stringify(result.transcription));
 await page.waitForFunction(()=>document.querySelector('#utterance').value.trim().length>0);
 result.ui_transcript=await page.locator('#utterance').inputValue();assert.equal(result.ui_transcript,result.transcription.transcript);assert.equal(result.transcription.transcript_confirmed,false);assert.equal(result.tts_requests,0);assert.deepEqual(await snapshot(page),before);result.review_before_recall_verified=true;
 worker=workerIdentity();result.worker_after_stt=worker;
 result.explicit_review={original:result.ui_transcript,operator_edited_to:'blue keys',reason:'Synthetic input is a memory description. Scripted operator explicitly edits it to the saved lookup label; not unchanged question recognition.'};
 await page.locator('#utterance').fill('blue keys');await page.locator('#open-settings').click();await page.locator('#speak-reply').check();await page.locator('#close-settings').click();const ttsStart=Date.now();const ttsResponse=page.waitForResponse(r=>r.url().endsWith('/api/speech/turns'));
 await page.locator('#ask').click();const rendered=await ttsResponse;result.turn_status=rendered.status();const turn=await rendered.json();result.tts_http_ms=Date.now()-ttsStart;assert.equal(result.turn_status,200,JSON.stringify(turn));
 const audio=Buffer.from(turn.speech.audio_base64||'','base64');delete turn.speech.audio_base64;result.turn=turn;save();assert.equal(turn.speech.status,'rendered');assert.equal(turn.recall.kind,'found');assert.equal(turn.recall.items[0].personal_name,'blue keys');assert.equal(turn.recall.items[0].location,'Desk drawer');
 assert.equal(audio.toString('ascii',0,4),'RIFF');assert.equal(audio.readUInt32LE(24),24000);assert.ok(audio.length>44);fs.writeFileSync(path.join(OUT,`${name}-reply.wav`),audio);result.reply_audio={sha256:sha(audio),bytes:audio.length,duration_seconds:(audio.length-44)/48000};
 await page.locator('#answer audio').waitFor();await page.waitForFunction(()=>document.querySelector('#answer audio').readyState>=1);result.audio_controls=await page.locator('#answer audio').evaluate(a=>({controls:a.controls,autoplay:a.autoplay,paused:a.paused,duration:a.duration}));assert.ok(result.audio_controls.controls&&!result.audio_controls.autoplay&&result.audio_controls.paused);
 result.worker_after_tts=workerIdentity();assert.deepEqual(result.worker_after_tts,worker);assert.deepEqual(await snapshot(page),before);result.memory_unchanged=true;result.same_single_worker=true;assert.equal(result.stt_requests,1);assert.equal(result.tts_requests,1);assert.deepEqual(result.page_errors,[]);assert.deepEqual(result.external_requests,[]);
 await page.screenshot({path:path.join(OUT,`${name}-browser.png`),fullPage:true});result.passed=true;
 }catch(e){result.error=String(e);throw e;}finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}result.server_stopped=!server||server.exitCode!==null||server.signalCode!==null;result.worker_stopped=!worker||!fs.existsSync(`/proc/${worker.pid}`);fs.closeSync(log);fs.rmSync(temp,{recursive:true,force:true});save();console.log(JSON.stringify({passed:result.passed,stt_requests:result.stt_requests,tts_requests:result.tts_requests,stt_ms:result.stt_http_ms,tts_ms:result.tts_http_ms,server_stopped:result.server_stopped,worker_stopped:result.worker_stopped,error:result.error}));}
})().catch(e=>{console.error(e);process.exitCode=1;});
