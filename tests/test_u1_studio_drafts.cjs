/* Isolated DOM/storage fixtures. No server, real browser, account or user data. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/js/u1-studio-pro.js'),'utf8');
const KEY='u1.studio.pro.draft.v1';
function baseline(){return {format:'u1-studio-pro',schema:1,document:{title:'Baseline title',subtitle:'',audience:'',template:'course',version:'1.0',source:'',brand:{name:'',accent:'#176B64',font:'serif'},sections:[{title:'Lesson',content:'Baseline lesson',activity:'',quizzes:[],answer_notes:'Private fixture answer'}],fillable:true,include_answer_notes:false,instructions:'',licence:''}};}
class Element{
 constructor(dataset={}){this.dataset=dataset;this.style={setProperty(){}};this.classList={add(){},remove(){}};this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.type='text';}
 insertAdjacentHTML(){} removeAttribute(){} hasAttribute(n){return n==='data-handoff-approved'&&this.dataset.handoffApproved!==undefined;} closest(){return this;}
}
class Host extends Element{
 constructor(){super();this.nodes=new Map();this.paints=0;this.docs=['title','subtitle','version','template','audience','source','instructions','licence','fillable','include_answer_notes'].map(k=>{const n=new Element({doc:k});if(k==='fillable'||k==='include_answer_notes')n.type='checkbox';return n;});this.brands=['name','accent','font'].map(k=>new Element({brand:k}));}
 set innerHTML(value){this.html=value;this.paints++;} get innerHTML(){return this.html;}
 querySelector(s){if(!this.nodes.has(s))this.nodes.set(s,new Element());return this.nodes.get(s);}
 querySelectorAll(s){return s==='[data-doc]'?this.docs:s==='[data-brand]'?this.brands:[];} contains(){return true;}
}
function fixture(shared=new Map([[KEY,JSON.stringify(baseline())]]),options={}){
 const timers=new Map(),events=new Map(),writes=[];let serial=0,getCalls=0;
 const storage={getItem:k=>shared.get(k)||null,setItem:(k,v)=>{if(options.quota)throw Error('Quota exceeded');writes.push(k);shared.set(k,v);},get length(){return shared.size;},key:i=>[...shared.keys()][i]||null};
 const window={confirm:()=>true,addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:(name,fn)=>{if(events.get(name)===fn)events.delete(name);},U1CoreViews:{register:(id,render,hooks)=>{window.registration={id,render,hooks};}},U1Data:{get:async()=>{getCalls++;return {templates:[],capabilities:{pdf:true}};},post:async()=>{throw Error('No mutation transport allowed');}}};
 if(options.locks)window.navigator={locks:{request:(_key,fn)=>Promise.resolve().then(fn)}};
 const context=vm.createContext({window,localStorage:storage,setTimeout:fn=>{timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id),Blob,URL,TextEncoder,Uint8Array,atob,btoa,console});
 vm.runInContext(source,context);
 const host=new Host(),api=window.U1StudioPro;
 return {api,window,host,shared,writes,events,render(){api.render(host);},flush(){const pending=[...timers.values()];timers.clear();pending.forEach(fn=>fn());},getCalls:()=>getCalls};
}
function type(f,key,value){const target=f.host.docs.find(n=>n.dataset.doc===key);target.value=value;f.host.oninput({target});}
function doc(f){return JSON.parse(f.shared.get(KEY)).document;}

test('render and cached activation do not write browser drafts or backend records',()=>{const f=fixture();f.render();f.api.activate(f.host);f.api.deactivate(f.host);assert.equal(f.writes.length,0);assert.equal(f.getCalls(),1);});
test('latest keystroke is checkpointed before debounce runs',()=>{const f=fixture();f.render();type(f,'title','Last keystroke');assert.equal(doc(f).title,'Baseline title');assert.equal(f.api.recoveryDrafts()[0].draft.document.title,'Last keystroke');});
test('deactivation flushes pending draft and cached return preserves DOM and handlers',()=>{const f=fixture();f.render();type(f,'title','Keep this form');const paints=f.host.paints;f.api.deactivate(f.host);assert.equal(doc(f).title,'Keep this form');f.host.onclick=null;f.host.oninput=null;f.api.activate(f.host);assert.equal(f.host.paints,paints);assert.equal(typeof f.host.oninput,'function');assert.equal(f.host.docs.find(n=>n.dataset.doc==='title').value,'Keep this form');});
test('rendering the same cached host does not reconstruct or discard dirty form state',()=>{const f=fixture();f.render();type(f,'title','Do not rebuild');const paints=f.host.paints;f.api.render(f.host);assert.equal(f.host.paints,paints);f.flush();assert.equal(doc(f).title,'Do not rebuild');});
test('two editors preserve conflicting drafts instead of silently overwriting',()=>{const shared=new Map([[KEY,JSON.stringify(baseline())]]),a=fixture(shared),b=fixture(shared);a.render();b.render();type(a,'title','Window A');a.flush();type(b,'title','Window B');b.flush();assert.equal(doc(a).title,'Window A');const titles=b.api.recoveryDrafts().map(row=>row.draft.document.title);assert.ok(titles.includes('Window A'));assert.ok(titles.includes('Window B'));assert.match(b.host.querySelector('[data-draft]').textContent,/Another editor/);});
test('explicit shared replacement retains the displaced draft in recovery',()=>{const f=fixture(),a=f.api.createDraftSession(),b=f.api.createDraftSession();assert.equal(a.save({...baseline().document,title:'First'}).saved,true);assert.equal(b.save({...baseline().document,title:'Second'}).conflict,true);assert.equal(b.save({...baseline().document,title:'Second'},true).saved,true);assert.equal(doc(f).title,'Second');assert.ok(f.api.recoveryDrafts().some(row=>row.draft.document.title==='First'));});
test('shared revisions increase when an operator adopts another editor draft',()=>{const f=fixture(),a=f.api.createDraftSession();a.save(baseline().document);const one=JSON.parse(f.shared.get(KEY)).revision;const b=f.api.createDraftSession();b.save({...baseline().document,title:'Next'});assert.ok(JSON.parse(f.shared.get(KEY)).revision>one);});
test('quota errors never claim a saved or recoverable draft',()=>{const f=fixture(undefined,{quota:true}),session=f.api.createDraftSession();const result=session.save(baseline().document);assert.equal(result.saved,false);assert.equal(result.recovered,false);assert.equal(doc(f).title,'Baseline title');});
test('pagehide retains latest edit without waiting for async Web Locks',async()=>{const f=fixture(undefined,{locks:true});f.render();type(f,'title','Safe before pagehide');f.events.get('pagehide')();assert.ok(f.api.recoveryDrafts().some(row=>row.draft.document.title==='Safe before pagehide'));f.api.deactivate(f.host);await Promise.resolve();await Promise.resolve();assert.equal(doc(f).title,'Safe before pagehide');});
test('registration publishes optional activate/deactivate hooks',()=>{const f=fixture();assert.equal(f.window.registration.id,'studio');assert.equal(f.window.registration.hooks.activate,f.api.activate);assert.equal(f.window.registration.hooks.deactivate,f.api.deactivate);});
