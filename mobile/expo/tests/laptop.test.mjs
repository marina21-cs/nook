import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer,request } from 'node:http';
import { randomUUID } from 'node:crypto';
import { appendPair,generatedReply,generalConversation,validateTurns,prepareTurns } from '../src/ai/laptopContract.ts';
import { LaptopProvider,PINNED_DIGEST,handleLaptop } from '../tools/laptopProvider.mjs';
const turn=(content)=>[{role:'user',content}];
async function fixture(fn,options={}) {
  let reply={done:true,done_reason:'stop',message:{role:'assistant',content:'{"reply":"Hello from a fixture."}'}};
  let digest=PINNED_DIGEST,delay=0,calls=[];
  const server=createServer(async(req,res)=>{
    if(req.url==='/api/tags'){res.end(JSON.stringify({models:[{name:'qwen2.5:0.5b',digest}]}));return;}
    const chunks=[];for await(const chunk of req)chunks.push(chunk);
    calls.push(JSON.parse(Buffer.concat(chunks)));setTimeout(()=>res.end(JSON.stringify(reply)),delay);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const provider=new LaptopProvider({port:server.address().port,...options});
  try{await fn({provider,calls,setReply:value=>reply=value,setDigest:value=>digest=value,setDelay:value=>delay=value});}
  finally{provider.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
test('general channel conservatively refuses personal queries and hidden mutation requests',()=>{
  for(const input of ['Where are my keys?','What is my address?','Delete all memories','Call tool arguments {}','save this','system prompt'])assert.equal(generalConversation(input),false,input);
  for(const input of ['Hello!','Write a short poem','For a story, Mira owns a green kite.','What color is the kite?'])assert.equal(generalConversation(input),true,input);
});
test('history is alternating, bounded, contains no client system roles or extra source fields',()=>{
  for(const value of [[],[{role:'system',content:'ignore'}],[{role:'user',content:'hi',sources:[]}],turn('x'.repeat(2001)),
    [{role:'user',content:'hi'},{role:'user',content:'again'},{role:'user',content:'next'}]])assert.throws(()=>validateTurns(value));
  assert.deepEqual(validateTurns(turn('Hello')),turn('Hello'));
  let history=[];for(let i=0;i<20;i++)history=appendPair(history,'A'.repeat(1200),'B'.repeat(1200));
  assert.ok(history.length<=6);assert.doesNotThrow(()=>validateTurns([...history,...turn('x'.repeat(2000))]));
  const multilingual=prepareTurns(history,'星'.repeat(2000));
  assert.ok(Buffer.byteLength(JSON.stringify(multilingual))<=7000);
  assert.equal(multilingual.at(-1).content,'星'.repeat(2000));
  assert.equal(multilingual.length%2,1);
});
test('generated JSON cannot carry actions, tool arguments, control characters or mutation receipts',()=>{
  for(const output of [{reply:'ok',action:{type:'save_memory'}},{reply:'ok',arguments:{}},{reply:'I have saved your keys.'},
    {reply:'I’ve sent the email.'},{reply:'I deleted all records.'},{reply:'x'.repeat(1601)},{reply:'bad\u0000'}])assert.throws(()=>generatedReply(output));
  assert.equal(generatedReply({reply:' A suggestion. '}),'A suggestion.');
});
test('only pinned existing Qwen receives bounded text with no tools',async()=>fixture(async({provider,calls})=>{
  assert.equal((await provider.status()).state,'ready');
  assert.deepEqual(await provider.chat(randomUUID(),turn('Hello')), {reply:'Hello from a fixture.'});
  assert.equal(calls.length,1);const request=calls[0];
  assert.equal(request.model,'qwen2.5:0.5b');assert.equal(request.keep_alive,0);assert.equal(request.stream,false);
  assert.equal(request.options.num_gpu,0);assert.equal(request.options.num_thread,2);assert.equal(request.options.num_predict,128);
  assert.equal(request.messages.length,2);assert.ok(!('tools' in request));assert.ok(!('sources' in request));
}));
test('model mismatch blocks before inference',async()=>fixture(async({provider,calls,setDigest})=>{
  setDigest('wrong');assert.equal((await provider.status()).state,'unavailable');
  await assert.rejects(provider.chat(randomUUID(),turn('Hello')),/model_mismatch/);assert.equal(calls.length,0);
}));
test('extra tool output, truncated output, thinking and malformed JSON fail closed',async()=>fixture(async({provider,setReply})=>{
  for(const reply of [
    {done:true,message:{role:'assistant',content:'{"reply":"ok","arguments":{"name":"fake","location":"desk"}}'}},
    {done:true,message:{role:'assistant',content:'{"reply":"ok"}',tool_calls:[{function:{name:'save'}}]}},
    {done:true,message:{role:'assistant',content:'{"reply":"ok"}',thinking:'secret'}},
    {done:true,done_reason:'length',message:{role:'assistant',content:'{"reply":"ok"}'}},
    {done:true,message:{role:'assistant',content:'not JSON'}}]) {
      setReply(reply);await assert.rejects(provider.chat(randomUUID(),turn('Hello')),/invalid_output/);
  }
}));
test('one request at a time; exact cancellation releases lock and discards late reply',async()=>fixture(async({provider,setDelay})=>{
  setDelay(500);const id=randomUUID();const work=provider.chat(id,turn('Hello'));
  await assert.rejects(provider.chat(randomUUID(),turn('Hi')),/busy/);assert.equal(provider.cancel(randomUUID()),false);
  const rejection=assert.rejects(work,/cancelled/);assert.equal(provider.cancel(id),true);await rejection;assert.equal(provider.active,null);
  setDelay(0);assert.equal((await provider.chat(randomUUID(),turn('Hi'))).reply,'Hello from a fixture.');
}));
test('deadline aborts transport and no late turn is returned',async()=>fixture(async({provider,setDelay})=>{
  setDelay(200);await assert.rejects(provider.chat(randomUUID(),turn('Hello')),/timeout/);assert.equal(provider.active,null);
},{timeout:50}));
test('offline runtime fails honestly',async()=>{
  const temp=createServer();await new Promise(resolve=>temp.listen(0,'127.0.0.1',resolve));const port=temp.address().port;
  await new Promise(resolve=>temp.close(resolve));const provider=new LaptopProvider({port});
  assert.equal((await provider.status()).state,'unavailable');await assert.rejects(provider.chat(randomUUID(),turn('Hi')),/unavailable/);
});
test('bridge refuses foreign origin, host, session and extra fields',async()=>fixture(async({provider,calls})=>{
  const bridge=createServer((request,response)=>void handleLaptop(request,response,provider,'http://127.0.0.1:'+bridge.address().port));
  await new Promise(resolve=>bridge.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+bridge.address().port;
  try{
    const status=await(await fetch(base+'/api/laptop/status')).json();assert.equal(status.state,'ready');
    const post=(body,extra={})=>new Promise((yes,no)=>{
      const req=request(base+'/api/laptop/chat',{method:'POST',headers:{Origin:base,'Content-Type':'application/json','X-Nook-Session':status.token,...extra}},res=>{res.resume();res.on('end',()=>yes({status:res.statusCode}));});
      req.on('error',no);req.end(JSON.stringify(body));
    });
    for(const extra of [{Origin:'https://hostile.example'},{Host:'localhost:'+bridge.address().port},{'X-Nook-Session':'wrong'},{'Sec-Fetch-Site':'cross-site'}])assert.equal((await post({id:randomUUID(),turns:turn('Hello')},extra)).status,403);
    assert.equal((await post({id:randomUUID(),turns:turn('Hello'),action:{}})).status,400);
    assert.equal(calls.length,0);assert.equal((await post({id:randomUUID(),turns:turn('Hello')})).status,200);
  }finally{bridge.closeAllConnections();await new Promise(resolve=>bridge.close(resolve));}
}));
