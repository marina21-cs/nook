// Real localhost API and synthetic records. Only failure/timeout transport is injected.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||require('node:path').join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {spawn}=require('node:child_process'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),mode=process.argv[2],run=process.argv[3];
if(!['before','after'].includes(mode)||!run||!/^[a-z0-9-]+$/.test(run))throw Error('Supply before/after and fresh run name');
const OUT=path.join(ROOT,'deliverables/nook-chat-repair',run);fs.mkdirSync(OUT,{recursive:false});
const base='http://127.0.0.1:8768',temp=fs.mkdtempSync(path.join(os.tmpdir(),'nook-chat-')),log=fs.openSync(path.join(OUT,'server.log'),'w');
let server,browser,page;const result={mode,passed:false,checks:[],observations:[],errors:[],network:[],external:[],models:false};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function check(name,value){assert.ok(value,name);result.checks.push(name);console.log('PASS',name);}
async function answer(){return page.locator('#answer').innerText();}
async function send(text){await page.locator('#utterance').fill(text);await page.locator('#ask').click();await page.waitForFunction(()=>!document.querySelector('#ask').disabled&&!document.querySelector('#ask').hidden);return answer();}
(async()=>{try{
 server=spawn(process.env.APP_TEST_PYTHON||path.join(ROOT,'.venv/bin/python'),['-m','app'],{cwd:ROOT,env:{...process.env,APP_DATA_DIR:temp,APP_PORT:'8768',APP_VOICE_ENABLED:'0',APP_VISION_DISABLED:'1',APP_TEXT_MODEL:'',APP_POI_DOWNLOAD_ENABLED:'0'},stdio:['ignore',log,log]});result.server_pid=server.pid;
 let ready=false;for(let i=0;i<80;i++){if(server.exitCode!==null)throw Error('Owned server exited');if(fs.readFileSync(path.join(OUT,'server.log'),'utf8').includes('Uvicorn running on '+base)){try{if((await fetch(base+'/api/status')).ok){ready=true;break;}}catch{}}await sleep(100);}assert.ok(ready);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||path.join(os.homedir(),'.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'),args:['--disable-gpu','--renderer-process-limit=2']});
 const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});await context.route('**/*',r=>{if(!r.request().url().startsWith(base+'/')){result.external.push(r.request().url());return r.abort();}return r.continue();});page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>result.errors.push(e.message));page.on('response',r=>{if(r.url().includes('/api/'))result.network.push({path:new URL(r.url()).pathname,status:r.status()});});
 await page.goto(base);await page.locator('#onboard-next').click();await page.locator('#setup-skip').click();await page.locator('#onboarding').waitFor({state:'hidden'});await page.locator('#talk').waitFor({state:'visible'});
 check('Typed Send enabled with models off',await page.locator('#record').isDisabled()&&await page.locator('#ask').isEnabled());
 let text=await send('hey');result.observations.push({query:'hey',answer:text});await page.screenshot({path:path.join(OUT,'hey-mobile.png'),fullPage:true});
 if(mode==='after')check('Greeting receives bounded helpful reply',/Hi!|Hey/.test(text)&&text.includes('save')&&!text.includes('No matching memory'));
 text=await send('Tell me a joke about the weather');result.observations.push({query:'unsupported natural language',answer:text});
 if(mode==='after')check('Unsupported language gets capability clarification',/general|saved items|belongings/i.test(text));
 const previous=text;text=await send('   ');result.observations.push({query:'whitespace',answer:text,changed:text!==previous});
 if(mode==='after'){check('Whitespace gets visible input guidance',text!==previous&&/type|message|question/i.test(text));text=await send('');check('Empty Send gets visible input guidance',/type|message|question/i.test(text));}
 if(mode==='before'){result.passed=true;return;}
 text=await send('wallet');check('Unsaved item gives useful save guidance',/Remember/.test(text));
 await page.locator('nav a[data-page="capture"]').click();await page.locator('#memory-prompt').fill('My blue keys are in the desk drawer');await page.locator('#send-memory').click();await page.locator('#remember-success').waitFor({state:'visible'});await page.locator('nav a[data-page="talk"]').click();
 text=await send('Where are my blue keys?');check('Saved memory recall still works',/desk drawer/i.test(text)&&/last record/i.test(text));await page.screenshot({path:path.join(OUT,'recall-mobile.png'),fullPage:true});
 await page.route('**/api/chat',r=>r.abort('failed'));text=await send('hey');check('Failed backend gives visible retryable error',/unavailable|couldn.t|could not/i.test(text));await page.unroute('**/api/chat');
 text=await send('hey');check('Typing recovers after network failure',/Hi!|Hey/.test(text));
 await page.route('**/api/chat',async r=>{await sleep(12000);await r.fulfill({json:{kind:'greeting',reply_text:'LATE REPLY SHOULD NOT APPEAR'}}).catch(()=>{});});const start=Date.now();text=await send('hey');result.timeout_ms=Date.now()-start;check('Hung request terminates with timeout guidance',/too long|timed out/i.test(text)&&result.timeout_ms<14500);await sleep(2500);check('Late response cannot replace timeout',(await answer())===text);await page.unroute('**/api/chat');
 text=await send('hey');check('Typing recovers after timeout',/Hi!|Hey/.test(text));
 await page.route('**/api/chat',async r=>{await sleep(500);await r.fulfill({json:{kind:'greeting',reply_text:'LATE CANCELLED REPLY'}}).catch(()=>{});});await page.locator('#utterance').fill('hey');await page.locator('#ask').click();await page.locator('#cancel-talk').click();await sleep(750);check('Cancel leaves visible terminal message',(await answer()).includes('Stopped.'));await page.unroute('**/api/chat');
 check('No page errors',result.errors.length===0);check('No browser external requests',result.external.length===0);result.passed=true;
 }catch(e){result.error=String(e);console.error(e);if(page)await page.screenshot({path:path.join(OUT,'failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1;}
 finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}result.server_stopped=!server||server.exitCode!==null||server.signalCode!==null;fs.closeSync(log);fs.rmSync(temp,{recursive:true,force:true});fs.writeFileSync(path.join(OUT,'result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:result.passed,checks:result.checks.length,error:result.error,server_stopped:result.server_stopped}));}
})();
