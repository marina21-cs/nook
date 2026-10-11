import { appendPair, generatedReply, prepareTurns } from './laptopContract.ts';
import type { ChatTurn } from './laptopContract.ts';

export class LaptopClient {
  private token = '';
  private history:ChatTurn[] = [];
  private active:{id:string; controller:AbortController} | null = null;
  async enable():Promise<string> {
    const response = await fetch('/api/laptop/status',{ signal:AbortSignal.timeout(4000), cache:'no-store' });
    const value = await response.json();
    if (!response.ok || value.state !== 'ready' || typeof value.token !== 'string') throw new Error('unavailable');
    this.token=value.token; this.history=[];
    return 'Ready: Qwen 2.5 0.5B · laptop-local only. Session opt-in enabled.';
  }
  clear() { this.history=[]; }
  disable() { this.cancel(); this.token=''; this.clear(); }
  cancel() {
    const active=this.active;
    if (!active) return;
    active.controller.abort(new Error('cancelled'));
    void fetch('/api/laptop/cancel',{ method:'POST',headers:{ 'Content-Type':'application/json','X-Nook-Session':this.token },
      body:JSON.stringify({id:active.id}),signal:AbortSignal.timeout(3000) }).catch(()=>undefined);
  }
  async chat(user:string,id:string):Promise<string> {
    if (!this.token) throw new Error('unavailable');
    if (this.active) throw new Error('busy');
    const turns=prepareTurns(this.history,user);
    const controller=new AbortController(); this.active={id,controller};
    const timer=setTimeout(()=>controller.abort(new Error('timeout')),22_000);
    try {
      const response=await fetch('/api/laptop/chat',{ method:'POST', headers:{'Content-Type':'application/json','X-Nook-Session':this.token},
        body:JSON.stringify({id,turns}),signal:controller.signal });
      const value=await response.json();
      if (controller.signal.aborted) throw controller.signal.reason;
      if (!response.ok) throw new Error(typeof value.error === 'string' ? value.error : 'unavailable');
      const reply=generatedReply(value); this.history=appendPair(this.history,user,reply); return reply;
    } catch(failure) {
      if (controller.signal.aborted) throw controller.signal.reason;
      throw failure;
    } finally { clearTimeout(timer); this.active=null; }
  }
}
