const fs=require('node:fs'); const assert=require('node:assert/strict');
(async()=>{
 const {wav16}=await import('data:text/javascript;base64,'+fs.readFileSync('app/static/media.js').toString('base64'));
 for(const rate of [16000,44100,48000]){
  const raw=Float32Array.from({length:rate*11},(_,i)=>Math.sin(i*2*Math.PI*440/rate)*.5);
  const bytes=wav16([raw.subarray(0,999),raw.subarray(999)],rate), data=new DataView(bytes.buffer);
  assert.equal(bytes.length,320044); assert.equal(data.getUint32(24,true),16000); assert.equal(data.getUint32(40,true),320000);
  assert.equal(data.getUint16(22,true),1); assert.equal(data.getUint16(34,true),16);
  assert.equal(Buffer.from(bytes).toString('ascii',0,4),'RIFF');
  let peak=0;for(let i=44;i<bytes.length;i+=2)peak=Math.max(peak,Math.abs(data.getInt16(i,true)));assert.ok(peak>15000&&peak<=16384);
 }
 assert.throws(()=>wav16([],16000)); assert.throws(()=>wav16([new Float32Array(3)],0));
 console.log('PASS canonical mono PCM16 WAV, 16/44.1/48kHz, 10-second cap, amplitude, empty/rate rejection');
})().catch(e=>{console.error(e);process.exitCode=1;});
