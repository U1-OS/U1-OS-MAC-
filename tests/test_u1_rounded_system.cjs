'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const appearance=require('../static/js/u1-rounded-system.js');
const cinematic=fs.readFileSync(path.join(__dirname,'../static/js/u1-cinematic.js'),'utf8');

test('appearance accepts only supported themes and bounded options',()=>{
  assert.deepEqual(appearance.normalize({theme:'graphite',density:'compact',corners:'soft',glow:'off',startupSound:true}),{theme:'graphite',density:'compact',corners:'soft',glow:'off',startupSound:true});
  for(const value of [null,[],false,'daylight',{theme:'constructor',startupSound:'true'}])assert.deepEqual(appearance.normalize(value),{theme:'orbit',density:'comfortable',corners:'rounded',glow:'subtle',startupSound:false});
});
test('normalisation never mutates stored input',()=>{const input=Object.freeze({theme:'daylight'});assert.equal(appearance.normalize(input).theme,'daylight');assert.deepEqual(input,{theme:'daylight'});});
test('themes describe appearance, not fabricated provider data',()=>{assert.deepEqual(appearance.themes.map(x=>x.id),['orbit','graphite','daylight']);assert.equal(appearance.themes.length,3);});

function fixture(saved={}){
  const events=[],timers=new Map(),requests=[],attrs={},stages={},frames=[],listeners={},shellAttrs={};let timerId=0;
  const root={dataset:{},style:{setProperty(){}}},body={},shell={inert:false,dataset:{},setAttribute(k,v){shellAttrs[k]=v;},removeAttribute(k){delete shellAttrs[k];},hasAttribute:k=>Object.hasOwn(shellAttrs,k)};
  const doc={documentElement:root,body,activeElement:body,hidden:false,addEventListener(type,fn){(listeners[type]||=[]).push(fn);},querySelector(selector){if(selector==='.shell')return shell;const match=selector.match(/data-boot-stage="([^"]+)"/);return match?stages[match[1]]:null;},getElementById(id){return elements[id]||null;}};
  const skip={id:'u1-skip-boot',isConnected:true,focus(){doc.activeElement=this;},getClientRects(){return [{}];}};
  const main={id:'main',isConnected:true,setAttribute(){},focus(){doc.activeElement=this;}};
  const classes=new Set(['gone']);
  const boot={inert:true,classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)},setAttribute:(k,v)=>{attrs[k]=v;},removeAttribute:k=>{delete attrs[k];},contains:x=>x===skip,querySelectorAll:()=>[skip]};
  const elements={boot,main,'u1-skip-boot':skip,'u1-boot-message':{textContent:''}};
  for(const id of ['core','data','services','ai','integrations']){const text={textContent:''};stages[id]={dataset:{},querySelector:()=>text,text};}
  const win={U1Safety:{isLocked:()=>false},dispatchEvent:e=>events.push(e),addEventListener(){}};
  const context={window:win,document:doc,localStorage:{getItem:()=>JSON.stringify(saved),setItem(){}},matchMedia:()=>({matches:false,addEventListener(){}}),performance:{now:()=>0},AbortController,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},Event:class{constructor(type){this.type=type;}},requestAnimationFrame:fn=>frames.push(fn),setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),fetch:url=>new Promise(resolve=>requests.push({url,resolve})),Set,Map,Promise};
  vm.runInNewContext(cinematic,context);
  function resolveRows(start,count){requests.slice(start,start+count).forEach(row=>row.resolve({ok:true,json:()=>Promise.resolve(row.url.includes('/api/state')?{services:{}}:row.url.includes('/prism/')?{success:true,records:[]}:{success:true,cards:[]})}));}
  return {win,doc,boot,shell,stages,attrs,shellAttrs,events,timers,frames,listeners,requests,resolveRows,classes,flush:()=>new Promise(setImmediate)};
}
test('startup completion and dismissal are idempotent',()=>{const f=fixture();f.win.U1Launch.start();assert.equal(f.shell.inert,true);assert.equal(f.attrs['aria-modal'],'true');assert.equal(f.win.U1Launch.dismiss(),true);assert.equal(f.win.U1Launch.dismiss(),false);assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,1);assert.equal(f.shell.inert,false);assert.equal(f.doc.activeElement.id,'main');});
test('older readiness results cannot close or update a newer explicit preview',async()=>{const f=fixture();f.win.U1Launch.start();f.win.U1Launch.preview();assert.equal(f.requests.length,6);f.resolveRows(0,3);await f.flush();assert.equal(f.stages.data.dataset.state,'checking');assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,0);f.resolveRows(3,3);await f.flush();assert.equal(f.stages.data.dataset.state,'ready');assert.equal(f.timers.size,0);assert.equal(f.classes.has('gone'),false);assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,0);f.win.U1Launch.dismiss();assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,1);});
test('skipped startup stays closed when background checks finish',async()=>{const f=fixture({skipBoot:true});f.win.U1Launch.start();assert.equal(f.classes.has('gone'),true);f.resolveRows(0,3);await f.flush();assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,1);assert.equal(f.stages.data.dataset.state,'checking');});
test('finishing startup never removes an active Safety inert state',()=>{const f=fixture();f.win.U1Launch.start();f.win.U1Safety.isLocked=()=>true;f.win.U1Launch.dismiss();assert.equal(f.shell.inert,true);assert.notEqual(f.doc.activeElement.id,'main');});
test('late readiness does not reopen an explicitly dismissed screen',async()=>{const f=fixture();f.win.U1Launch.start();f.win.U1Launch.dismiss();f.resolveRows(0,3);await f.flush();assert.equal(f.classes.has('gone'),true);assert.equal(f.events.filter(e=>e.type==='u1:boot-complete').length,1);});

const safetySource=fs.readFileSync(path.join(__dirname,'../static/js/u1-safety.js'),'utf8');
function bootSafetyFixture(){
  const f=fixture(),dialog={open:false,innerHTML:'',querySelector:()=>null,close(){this.open=false;},showModal(){this.open=true;}};
  f.doc.readyState='loading';f.doc.dispatchEvent=e=>f.events.push(e);f.doc.querySelectorAll=s=>s==='.shell,#dock,#u1-utility-shelf'?[f.shell]:s==='dialog[open]'&&dialog.open?[dialog]:[];
  const end=safetySource.lastIndexOf('})();');
  const code=safetySource.slice(0,end)+'window.testSafetyApply=apply;dialog=window.fixtureSafetyDialog;\n'+safetySource.slice(end);
  f.win.fixtureSafetyDialog=dialog;
  vm.runInNewContext(code,{window:f.win,document:f.doc,CustomEvent:class{constructor(type,o){this.type=type;this.detail=o.detail;}}});
  f.setLocked=value=>f.win.testSafetyApply({locked:value,configured:true,server_time:Date.now()/1000});return f;
}
test('boot then lock then dismiss then unlock transfers and releases Safety ownership',()=>{
  const f=bootSafetyFixture();f.setLocked(false);f.win.U1Launch.start();assert.equal(f.shell.dataset.u1BootInert,'true');f.setLocked(true);assert.equal(f.shell.dataset.u1SafetyInert,'true');f.win.U1Launch.dismiss();assert.equal(f.shell.inert,true);assert.equal(f.shell.dataset.u1BootInert,undefined);f.setLocked(false);assert.equal(f.shell.inert,false);assert.equal(f.shell.dataset.u1SafetyInert,undefined);
});
test('lock then boot then unlock then dismiss retains boot ownership until dismissal',()=>{
  const f=bootSafetyFixture();f.setLocked(true);f.win.U1Launch.start();f.setLocked(false);assert.equal(f.shell.inert,true);assert.equal(f.shell.dataset.u1BootInert,'true');assert.equal(f.shell.dataset.u1SafetyInert,undefined);f.win.U1Launch.dismiss();assert.equal(f.shell.inert,false);
});
test('boot completion preserves independently preexisting inertness',()=>{
  const f=bootSafetyFixture();f.setLocked(false);f.shell.inert=true;f.win.U1Launch.start();f.win.U1Launch.dismiss();assert.equal(f.shell.inert,true);assert.equal(f.shell.dataset.u1BootInert,undefined);
});

test('normal startup still auto-completes after actual checks',async()=>{
  const f=fixture();f.win.U1Launch.start();f.resolveRows(0,3);await f.flush();const timer=[...f.timers.values()].find(x=>x.ms===1200);assert.ok(timer);timer.fn();assert.equal(f.classes.has('gone'),true);assert.equal(f.shell.hasAttribute('inert'),false);
});
test('explicit preview uses real failed readiness and stays open until Enter or Escape',async()=>{
  for(const key of ['Enter','Escape']){const f=fixture();f.win.U1Launch.preview();assert.equal(f.doc.activeElement.id,'u1-skip-boot');f.requests.forEach(r=>r.resolve({ok:false,status:503}));await f.flush();assert.equal(f.stages.data.dataset.state,'unavailable');assert.equal(f.timers.size,0);assert.equal(f.classes.has('gone'),false);for(const fn of f.listeners.keydown)fn({key,preventDefault(){}});assert.equal(f.classes.has('gone'),true);}
});
test('preview mirrors inert attributes and retries focus after display without stale focus stealing',()=>{
  const f=fixture(),skip=f.doc.getElementById('u1-skip-boot'),focus=skip.focus;let blocked=true;skip.focus=function(){if(!blocked)focus.call(this);};f.win.U1Launch.preview();assert.equal(f.shell.hasAttribute('inert'),true);assert.equal(Object.hasOwn(f.attrs,'inert'),false);assert.equal(f.doc.activeElement,f.doc.body);blocked=false;f.frames.shift()();assert.equal(f.doc.activeElement,skip);f.win.U1Launch.dismiss();assert.equal(Object.hasOwn(f.attrs,'inert'),true);assert.equal(f.shell.hasAttribute('inert'),false);f.win.U1Launch.preview();f.win.U1Launch.dismiss();f.frames.forEach(fn=>fn());assert.equal(f.doc.activeElement.id,'main');
});
test('both Safety orderings preserve and release the physical inert attribute',()=>{
  for(const lockFirst of [false,true]){const f=bootSafetyFixture();f.setLocked(lockFirst);f.win.U1Launch.preview();if(!lockFirst)f.setLocked(true);assert.equal(f.shell.hasAttribute('inert'),true);if(lockFirst){f.setLocked(false);assert.equal(f.shell.hasAttribute('inert'),true);f.win.U1Launch.dismiss();}else{f.win.U1Launch.dismiss();assert.equal(f.shell.hasAttribute('inert'),true);f.setLocked(false);}assert.equal(f.shell.hasAttribute('inert'),false);assert.equal(f.shell.inert,false);}
});
