/* Persistent Node VM regressions. Fake DOM/fetch; no browser or account calls. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const a = 'a'.repeat(32), b = 'b'.repeat(32);
const respond = data => ({ok:true,json:async()=>data});
function snapshot(id, text) {
  return {success:true,paused:false,storage_fault:false,provider:{installed:true},jobs:[],
    conversations:[{id:a,title:'A',message_count:1},{id:b,title:'B',message_count:1}],
    ...(id ? {conversation:{id,messages:[{role:'user',text,created_at:1,context:[]}]}} : {})};
}
function fixture() {
  const elements = new Map(), requests = [], pending = [], intervals = new Map(), registrations = new Map();
  let nextTimer=1;
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector,{innerHTML:'',textContent:'',value:'',checked:false,disabled:false,setAttribute(){},addEventListener(){}});
    return elements.get(selector);
  }
  const host={isConnected:true,querySelector:element,getClientRects:()=>[{}]};
  const state={host,conversation:a,context:[],messages:[],view:'ai',active:true,generation:0,refreshSerial:0,refreshing:null,review:null};
  const fetch=async(url,options)=>{
    assert(url.startsWith('/api/'));
    requests.push({url,body:options.body ? JSON.parse(options.body) : null});
    if (url==='/api/integrations') return respond({success:true,csrf_token:'fixture'});
    if (options.method==='POST') return respond({success:true,conversation_id:state.conversation||a,job:{id:'fixture'}});
    return new Promise(resolve=>pending.push({url,resolve}));
  };
  const window={U1Safety:{isLocked:()=>false},U1CoreViews:{register:(id,render,hooks)=>registrations.set(id,{render,hooks})},addEventListener(){}};
  const document={readyState:'complete',documentElement:{dataset:{}},hidden:false,addEventListener(){}};
  const context=vm.createContext({window,document,fetch,TextEncoder,AbortController,crypto:require('node:crypto').webcrypto,
    setTimeout:()=>1,clearTimeout(){},setInterval:fn=>{const id=nextTimer++;intervals.set(id,fn);return id;},clearInterval:id=>intervals.delete(id),MutationObserver:class{observe(){}},console});
  const file=path.join(root,'static/js/u1-assistant-workspace.js');
  const source=fs.readFileSync(file,'utf8').replace('  window.U1Assistant = Object.freeze(',
    '  window.__audit={refresh:refresh,send:send,instances:instances,selectConversation:selectConversation};\n  window.U1Assistant = Object.freeze(');
  vm.runInContext(source,context,{filename:file});
  window.__audit.instances.set(host,state);
  return {host,state,window,document,context,element,requests,pending,intervals,registrations,audit:window.__audit};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function form(f) {
  const allowance=f.element('[name=allowance]');allowance.checked=true;
  const prompt=f.element('[name=prompt]');prompt.value='Unsent reviewed draft';
  return {elements:{prompt,role:{value:'Creator'},allowance},querySelector:()=>f.element('form [type=submit]')};
}
async function reviewed(f,id=a,text='Reviewed A') {
  f.audit.selectConversation(f.state,id);
  const work=f.audit.refresh(f.state), pending=f.pending.at(-1);
  pending.resolve(respond(snapshot(id,text)));await work;
}
async function testOutOfOrder() {
  const f=fixture();
  const first=f.audit.refresh(f.state);
  f.audit.selectConversation(f.state,b);
  const second=f.audit.refresh(f.state);
  assert.equal(f.pending.length,2);
  f.pending[1].resolve(respond(snapshot(b,'CURRENT-B')));await second;
  f.element('[name=allowance]').checked=true;
  f.pending[0].resolve(respond(snapshot(a,'STALE-A')));await first;
  assert.equal(f.element('[name=conversation]').value,b);
  assert(f.element('[data-ai-transcript]').innerHTML.includes('CURRENT-B'));
  assert(!f.element('[data-ai-transcript]').innerHTML.includes('STALE-A'));
  assert.equal(f.state.review.conversation,b);
  assert.equal(f.element('[name=allowance]').checked,true);
}
async function testSendBlockedDuringReviewLoad() {
  const f=fixture();await reviewed(f);
  f.audit.selectConversation(f.state,b);const read=f.audit.refresh(f.state);
  const draft=form(f);await f.audit.send(f.state,draft);
  assert(!f.requests.some(request=>request.body));
  assert.equal(draft.elements.allowance.checked,false);
  f.pending.at(-1).resolve(respond(snapshot(b,'B')));await read;
}
async function testCurrentReviewIsSent() {
  const f=fixture();await reviewed(f,b,'REVIEWED-B');
  f.state.context=[{label:'Chosen context',text:'Explicit fixture text'}];
  const previousReads=f.pending.length;
  const draft=form(f), sending=f.audit.send(f.state,draft);await flush();
  const sent=f.requests.find(request=>request.body);
  assert(sent);assert.equal(sent.body.conversation_id,b);assert.equal(sent.body.confirmed,true);
  assert.equal(sent.body.context[0].text,'Explicit fixture text');
  assert.equal(f.pending.length,previousReads+1,'Accepted send must fetch the current conversation before the test resolves it');
  f.pending.at(-1).resolve(respond(snapshot(b,'REVIEWED-B')));await sending;
}
async function testSelectionChangeDuringCsrfPreventsPost() {
  const f=fixture();await reviewed(f);
  let release;
  const normal=f.context.fetch;
  f.context.fetch=async(url,options)=>url==='/api/integrations' ? new Promise(resolve=>{release=resolve;}) : normal(url,options);
  const sending=f.audit.send(f.state,form(f));await flush();
  assert.equal(typeof release,'function');
  f.audit.selectConversation(f.state,b);
  release(respond({success:true,csrf_token:'fixture'}));await sending;
  assert(!f.requests.some(request=>request.body));
}
async function testHistoryChangeInvalidatesConsent() {
  const f=fixture();await reviewed(f,a,'Original review');f.element('[name=allowance]').checked=true;
  const read=f.audit.refresh(f.state);f.pending.at(-1).resolve(respond(snapshot(a,'Changed history')));await read;
  assert.equal(f.element('[name=allowance]').checked,false);
}
async function testIdentityMismatchIsRejected() {
  const f=fixture(),read=f.audit.refresh(f.state);
  f.pending.at(-1).resolve(respond(snapshot(b,'Wrong identity')));await read;
  assert.equal(f.state.review,null);assert.equal(f.element('form [type=submit]').disabled,true);
}
async function testLifecyclePreservesDraftAndOnlyReads() {
  const f=fixture();await reviewed(f,b,'History B');const draft=form(f);
  f.state.context=[{label:'Selected',text:'Keep this context'}];
  const hooks=f.registrations.get('ai').hooks;
  assert.equal(typeof hooks.activate,'function');assert.equal(typeof hooks.deactivate,'function');
  hooks.deactivate(f.host);
  assert.equal(f.state.active,false);assert.equal(f.state.conversation,b);
  assert.equal(draft.elements.prompt.value,'Unsent reviewed draft');assert.equal(f.state.context[0].text,'Keep this context');
  assert.equal(draft.elements.allowance.checked,false);
  hooks.activate(f.host);await flush();
  assert.equal(f.state.active,true);assert.equal(f.state.conversation,b);
  assert.equal(draft.elements.prompt.value,'Unsent reviewed draft');assert.equal(f.intervals.size,1);
  assert(!f.requests.some(request=>request.body));
  f.pending.at(-1).resolve(respond(snapshot(b,'History B')));await flush();
  hooks.deactivate(f.host);assert.equal(f.intervals.size,0);
}
async function main() {
  const tests=[testOutOfOrder,testSendBlockedDuringReviewLoad,testCurrentReviewIsSent,testSelectionChangeDuringCsrfPreventsPost,testHistoryChangeInvalidatesConsent,testIdentityMismatchIsRejected,testLifecyclePreservesDraftAndOnlyReads];
  for(const test of tests){await test();console.log('PASS '+test.name);}
  console.log(tests.length+' assistant consent/lifecycle tests passed; all I/O mocked.');
}
const watchdog=setTimeout(()=>{console.error('FAIL: assistant regression run stalled on an unresolved fixture');process.exit(1);},5000);
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>clearTimeout(watchdog));
