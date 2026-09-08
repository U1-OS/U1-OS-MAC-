'use strict';
/* Positive regressions for the nine adverse baseline checks. Synthetic DOM/data only. */
const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const files=['u1-platform','u1-safety','u1os','u1-core-workspaces','u1-data','u1-connections-workspace','u1-media-research'];
const sources=Object.fromEntries(files.map(n=>[n,fs.readFileSync(path.join(root,'static/js',n+'.js'),'utf8')]));
const policy=require('../static/js/u1-connection-policy.js');
const platformCore=require('../static/js/u1-platform-core.js');
function expose(code,addition){const i=code.lastIndexOf('})();');assert(i>0);return code.slice(0,i)+addition+'\n'+code.slice(i);}
function eventTarget(target={}){const listeners={};return Object.assign(target,{listeners,addEventListener(name,fn){(listeners[name]||=[]).push(fn);},removeEventListener(name,fn){listeners[name]=(listeners[name]||[]).filter(x=>x!==fn);},dispatchEvent(event){for(const fn of [...(listeners[event.type]||[])])fn(event);return true;}});}
function node(id=''){
 const children=[],attrs=new Map(),classes=new Set(),queries=new Map();let markup='';
 return eventTarget({id,children,dataset:{},style:{},isConnected:true,inert:false,hidden:false,textContent:'',writes:0,
  get innerHTML(){return markup;},set innerHTML(v){markup=v;this.writes++;},
  classList:{add(...s){s.forEach(x=>classes.add(x));},remove(...s){s.forEach(x=>classes.delete(x));},contains:s=>classes.has(s),toggle(s,on){on=on===undefined?!classes.has(s):on;on?classes.add(s):classes.delete(s);return on;}},
  setAttribute(k,v){attrs.set(k,String(v));},getAttribute:k=>attrs.has(k)?attrs.get(k):null,removeAttribute:k=>attrs.delete(k),
  appendChild(n){children.push(n);n.parentNode=this;n.parentElement=this;return n;},append(n){return this.appendChild(n);},replaceChildren(n){children.length=0;this.appendChild(n);},
  contains(n){return n===this||n.owner===this||children.includes(n);},closest(){return null;},querySelectorAll(){return [];},
  querySelector(s){if(!queries.has(s))queries.set(s,node(s));return queries.get(s);},focus(){this.focused=true;},blur(){},scrollTop:0
 });
}
function environment(){
 const nodes=new Map(),dialogs=[],stack=[],timers=[];
 const document=eventTarget({readyState:'loading',hidden:false,body:node('body'),documentElement:{dataset:{u1Safety:'open'}},getElementById:id=>nodes.get(id)||null,
  querySelectorAll(s){if(s==='dialog[open]')return dialogs.filter(d=>d.open);if(s==='.shell,#dock,#u1-utility-shelf')return [nodes.get('shell')].filter(Boolean);if(s==='.view')return [...nodes.values()].filter(n=>n.id.startsWith('v-'));return [];},
  querySelector(){return null;},createElement:()=>node()});
 document.body.dataset.u1View='home';
 const window=eventTarget({U1PlatformCore:platformCore});
 const context={window,document,location:{search:'',hash:'#home'},URL,URLSearchParams,AbortController,CustomEvent:class{constructor(type,o={}){this.type=type;this.detail=o.detail;}},console,localStorage:{getItem:()=>null,setItem(){}},setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(){return 1;},clearInterval(){},MutationObserver:class{observe(){}disconnect(){}}};
 function modal(id){const d=node(id);d.open=false;d.showModal=function(){this.open=true;stack.push(this);};d.close=function(){if(!this.open)return;this.open=false;const i=stack.indexOf(this);if(i>=0)stack.splice(i,1);this.dispatchEvent({type:'close'});};dialogs.push(d);nodes.set(id,d);return d;}
 return {window,document,context,nodes,dialogs,stack,timers,modal};
}
function fixturePlatform(options={}){
 const e=environment(),body=node('platform-body'),dialog=e.modal('u1-platform-dialog'),calls=[];
 e.nodes.set('u1-platform-title',node());e.nodes.set('u1-platform-search-results',node());e.nodes.set('shell',node('shell'));
 e.window.U1Data={get:async url=>{calls.push(url);if(options.get)return options.get(url);throw Error('Fixture offline');}};
 const inputLine=sources['u1-platform'].split('\n').find(l=>l.includes("dialog.addEventListener('input'"));
 const keyLine=sources['u1-platform'].split('\n').find(l=>l.includes("window.addEventListener('keydown'"));
 const closeLine=sources['u1-platform'].split('\n').find(l=>l.includes("dialog.addEventListener('close'"));
 vm.runInNewContext(expose(sources['u1-platform'],`window.auditPlatform={seed:function(s,r){state=s;received=r||{};},attach:function(d,b){dialog=d;body=b;${inputLine}\n${keyLine}\n${closeLine}},snapshot:function(){return state;},open:open,refresh:refresh,searchHTML:searchHTML,business:business};`),e.context);
 const api=e.window.auditPlatform;api.attach(dialog,body);
 api.seed({summary:{records:[{kind:'note',title:'PRIVATE fixture note'}]},business:{entries:[{id:'fixture',title:'PRIVATE fixture ledger',kind:'income',created:1,currency:'AUD',amount_minor:4700}],totals:{AUD:{income_minor:4700,expense_minor:0}}}},{business:Date.now()-60000});
 vm.runInNewContext(expose(sources['u1-safety'],`window.auditSafety={attach:function(d){dialog=d;state={locked:false,configured:true};lastLock=false;},apply:apply,containDialogs:containDialogs};`),e.context);
 const safety=e.modal('u1-safety-dialog');e.window.auditSafety.attach(safety);
 function lock(yes){e.window.auditSafety.apply({locked:yes,configured:true,server_time:Date.now()/1000,reason:'Fixture'});}
 return {...e,api,body,platformDialog:dialog,safety,calls,lock};
}
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};

test('armed lock blocks actual global search shortcut and clears cached private snapshots',async()=>{
 const e=fixturePlatform();await e.api.open('business');assert.match(e.body.innerHTML,/PRIVATE fixture ledger/);
 e.lock(true);assert.equal(e.stack.at(-1),e.safety);assert.equal(e.platformDialog.open,false);assert.equal(e.body.inert,true);
 e.window.dispatchEvent({type:'keydown',metaKey:true,key:'k',preventDefault(){},stopImmediatePropagation(){}});
 assert.equal(e.stack.at(-1),e.safety);assert.equal(await e.api.open('business'),false);
 assert.doesNotMatch(e.api.searchHTML('PRIVATE'),/PRIVATE fixture/);assert.deepEqual(Object.keys(e.api.snapshot()),[]);
 assert.equal(e.calls.length,0);
});
test('an additional modal opened while locked is contained on reconciliation',()=>{
 const e=fixturePlatform();e.lock(true);const rogue=e.modal('fixture-late-dialog');rogue.showModal();e.window.auditSafety.containDialogs();
 assert.equal(rogue.open,false);assert.equal(e.stack.at(-1),e.safety);
});
test('late pre-lock responses cannot repopulate state or reopen a modal after unlock',async()=>{
 const pending=[];const e=fixturePlatform({get:url=>new Promise(resolve=>pending.push({url,resolve}))});e.api.seed({});
 const opening=e.api.open('search');await flush();assert.equal(pending.length,5);const old=pending.splice(0);
 e.lock(true);e.lock(false);await flush();assert.equal(pending.length,5);
 old.forEach(p=>p.resolve({success:true,records:[{kind:'note',title:'OLD private title'}]}));await opening;await flush();
 assert.doesNotMatch(JSON.stringify(e.api.snapshot()),/OLD private/);assert.equal(e.platformDialog.open,false);
 pending.splice(0).forEach(p=>p.resolve({success:true,records:[{kind:'note',title:'NEW private title'}]}));await flush();
 await e.api.open('search');assert.match(e.api.searchHTML('NEW'),/NEW private title/);assert.doesNotMatch(e.api.searchHTML('OLD'),/OLD private title/);
});
test('locking preserves an unsaved modal form only as closed inert DOM, then restores that form',async()=>{
 const e=fixturePlatform();await e.api.open('documents');const field=e.body.querySelector('[name=title]');field.value='Unsaved fixture document';
 e.platformDialog.dispatchEvent({type:'input',target:{id:'title',closest:()=>({})}});const markup=e.body.innerHTML;
 e.lock(true);assert.equal(e.platformDialog.open,false);assert.equal(e.body.inert,true);assert.equal(e.body.innerHTML,markup);
 e.lock(false);await flush();await e.api.open('documents');assert.equal(e.body.querySelector('[name=title]'),field);assert.equal(field.value,'Unsaved fixture document');assert.equal(e.body.innerHTML,markup);
});
test('stale and unavailable ledgers explicitly label source failure instead of current or empty data',async()=>{
 const e=fixturePlatform();await e.api.refresh();await e.api.open('business');assert.match(e.body.innerHTML,/data-ledger-state="stale"/);assert.match(e.body.innerHTML,/Last successful read/);assert.match(e.body.innerHTML,/47\.00/);
 e.api.seed({summary:{records:[]},business:{unavailable:true}});await e.api.open('business');assert.match(e.body.innerHTML,/Ledger unavailable/);assert.doesNotMatch(e.body.innerHTML,/No entries recorded/);
});
test('stale and unavailable news carries source and snapshot labels in the actual signals view',async()=>{
 const e=fixturePlatform({get:async url=>url.endsWith('/news')?{success:true,stale:true,source:'Fixture feed',fetched_at:1788825600,items:[{title:'Fixture retained headline',published_at:'2026-09-07T00:00:00Z'}]}:{success:true}});
 await e.api.open('signals');assert.match(e.body.innerHTML,/STALE news snapshot/);assert.match(e.body.innerHTML,/Fixture feed/);assert.match(e.body.innerHTML,/Snapshot time:/);assert.match(e.body.innerHTML,/Published/);
 const failed=fixturePlatform();await failed.api.open('signals');assert.match(failed.body.innerHTML,/News unavailable/);
});

function fixtureCore(){
 const e=environment(),requests=[],postings=[];let mounted=Promise.resolve();
 e.window.U1={esc:s=>String(s??''),icons:{svg:()=>''},model:{NAV:[],DOCK:[],VIEWS:{}},sound:{enabled:()=>false,nav(){},open(){},close(){}},notify:{paint(){},push(){}},scenes(){}};
 e.window.U1ConnectionPolicy=policy;e.window.U1Launch={start(){},preferences:()=>({quality:'auto',motion:'full',skipBoot:false})};
 e.window.U1Data={get:async()=>({success:true,records:[],files:[]})};e.window.confirm=()=>true;
 e.context.fetch=async(url,options={})=>{requests.push(url);if(options.method==='POST')postings.push(url);return {ok:true,status:200,json:async()=>url==='/api/integrations'?{success:true,cards:[],csrf_token:'fixture'}:url==='/api/workspace/google'?{success:true,configured:false,oauth_status:'idle'}:{success:true,providers:[]}};};
 vm.runInNewContext(sources['u1-core-workspaces'],e.context);
 vm.runInNewContext(sources['u1-connections-workspace'],e.context);
 const controller=sources.u1os.indexOf('  var U = window.U1, esc = U.esc');
 const end=sources.u1os.indexOf("  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);",controller);
 assert(controller>0&&end>controller);
 vm.runInNewContext('(function(){'+sources.u1os.slice(controller,end)+'\nwindow.auditShell={go:go,fillView:fillView,boot:boot,syncSoundButton:syncSoundButton};})();',e.context);
 e.window.U1Workspaces={profile:{},mount(id,host){mounted=e.window.U1CoreViews.mount(id,host);return mounted;},refresh:()=>Promise.resolve()};
 for(const id of ['main','rail','dock','views','v-home','soundBtn','avatar','whoName','omni','palInput','scrim','palList','notif','boot'])e.nodes.set(id,node(id));
 for(const match of sources.u1os.matchAll(/\$\('([^']+)'\)/g))if(!e.nodes.has(match[1]))e.nodes.set(match[1],node(match[1]));
 function host(id){const h=node('body-'+id);e.nodes.set(h.id,h);e.nodes.set('v-'+id,node('v-'+id));return h;}
 async function go(id){e.window.auditShell.go(id,{silent:true});await flush();await mounted;await flush();}
 return {...e,requests,postings,host,go,api:e.window.U1CoreViews,shell:e.window.auditShell};
}
for(const id of ['integrations','settings'])test(id+' reentry restores active handlers without replacing dirty form DOM',async()=>{
 const e=fixtureCore(),host=e.host(id);await e.go(id);
 const field=host.querySelector('[name=fixture-secret]');field.value='unsaved fixture only';
 host.dispatchEvent({type:'input',target:{name:'fixture-secret',closest:()=>({})}});const markup=host.innerHTML,writes=host.writes;
 await e.go('home');await e.go(id);assert.equal(host.innerHTML,markup);assert.equal(host.writes,writes);assert.equal(field.value,'unsaved fixture only');
 let opened=0;e.window.U1Platform={open:async()=>opened++};const control={owner:host,disabled:false,dataset:{ucAction:'platform',ucTarget:'controls'},closest(){return this;}};
 host.dispatchEvent({type:'click',target:control});await flush();assert.equal(opened,1);
 const refresh={owner:host,disabled:false,dataset:{ucAction:'refresh'},closest(){return this;}};const before=e.requests.length;
 host.dispatchEvent({type:'click',target:refresh});await flush();assert(e.requests.length>before);
});
test('hooks are optional; cached renderer stays mounted and activation is not called on first render',async()=>{
 const e=fixtureCore(),h=e.host('fixture'),counts={render:0,activate:0,deactivate:0};
 e.api.register('fixture',()=>{counts.render++;h.innerHTML='draft';},{activate:()=>counts.activate++,deactivate:()=>counts.deactivate++});
 await e.go('fixture');assert.deepEqual(counts,{render:1,activate:0,deactivate:0});await e.go('fixture');assert.equal(counts.activate,0);
 await e.go('home');await e.go('fixture');assert.deepEqual(counts,{render:1,activate:1,deactivate:1});assert.equal(h.innerHTML,'draft');
 e.document.documentElement.dataset.u1Safety='locked';e.document.dispatchEvent({type:'u1:safety-change',detail:{locked:true}});assert.equal(counts.deactivate,2);
 e.api.register('nohooks',()=>{});e.host('nohooks');assert.equal(e.api.supports('nohooks'),true);
});
test('deactivation cancels immediately during async initialization, reactivation waits and stale transitions are skipped',async()=>{
 const e=fixtureCore(),h=e.host('slow');let finish;const calls=[];
 e.api.register('slow',()=>{calls.push('render');return new Promise(r=>finish=r);},{activate:()=>calls.push('activate'),deactivate:()=>calls.push('deactivate')});
 const first=e.api.mount('slow',h);await flush();e.api.deactivate('slow',h);const second=e.api.activate('slow',h);e.api.deactivate('slow',h);const third=e.api.activate('slow',h);
 assert.deepEqual(calls,['render','deactivate','deactivate']);finish();await Promise.all([first,second,third]);assert.deepEqual(calls,['render','deactivate','deactivate','activate']);
});
test('actual Media hooks return the existing player to its slot on cached reentry',async()=>{
 const e=fixtureCore(),h=e.host('media');const slot=node('slot'),parking=node('parking'),mini=node('mini'),mediaRoot=node('media-root');mediaRoot.parentNode=h;
 let mounts=0;const media=sources['u1-media-research'];
 const move=media.slice(media.indexOf('  function movePlayer('),media.indexOf('  function updateMetadata('));
 const mount=media.slice(media.indexOf('  async function mountMedia('),media.indexOf('  function localTime('));
 const ctx={document:{body:parking},mediaRoot,mini,parking,player:{paused:true},cap:{},qs:()=>slot,ensurePlayer(){},syncPlayerState(){},updateMetadata(){},hasPlayerSource:()=>false};
 vm.runInNewContext(move+'\n'+mount,ctx);
 e.api.register('media',host=>{mounts++;return ctx.mountMedia(host);},{activate:ctx.mountMedia,deactivate:ctx.unmountMedia});
 await e.go('media');assert.equal(mini.parentNode,slot);await e.go('home');assert.equal(mini.parentNode,parking);await e.go('media');assert.equal(mini.parentNode,slot);assert.equal(mounts,1);
 assert.match(media,/register\('media', mountMedia, \{ activate: mountMedia, deactivate: unmountMedia \}\)/);
});
test('prototype properties are not routes and denied storage does not prevent boot handlers',()=>{
 const e=fixtureCore();for(const id of ['constructor','__proto__','toString'])assert.equal(e.api.supports(id),false);
 e.shell.go('constructor');assert.equal(e.document.body.dataset.u1View,'home');
 e.context.localStorage.getItem=()=>{throw Error('Fixture SecurityError');};assert.doesNotThrow(()=>e.shell.boot());
 assert(e.document.listeners.click.length>0);assert(e.window.listeners.hashchange.length>0);assert.equal(e.nodes.get('whoName').textContent,'Operator');
});

test('the complete unmodified shell script bootstraps with denied storage and no private helper globals',()=>{
 const e=environment();let starts=0,refreshes=0;
 for(const match of sources.u1os.matchAll(/\$\('([^']+)'\)/g))if(!e.nodes.has(match[1]))e.nodes.set(match[1],node(match[1]));
 for(const id of ['v-home','main','rail','dock','views'])if(!e.nodes.has(id))e.nodes.set(id,node(id));
 e.context.localStorage={getItem(){throw Error('Fixture SecurityError');},setItem(){throw Error('Fixture SecurityError');}};
 const context=Object.assign(e.context,e.window,{navigator:{userActivation:{hasBeenActive:false}},matchMedia:()=>({matches:true,addEventListener(){}}),requestAnimationFrame:()=>1,cancelAnimationFrame(){},U1Workspaces:{profile:{},refresh(){refreshes++;return Promise.resolve();}},U1Launch:{start(){starts++;},preferences:()=>({quality:'auto',motion:'reduced',skipBoot:false})}});
 context.window=context;
 assert.equal(context.ls,undefined);assert.equal(context.Sound,undefined);assert.equal(context.Notify,undefined);
 vm.runInNewContext(sources.u1os,context,{filename:'u1os-full-bootstrap.js'});
 assert.doesNotThrow(()=>e.document.dispatchEvent({type:'DOMContentLoaded'}));
 assert.equal(starts,1);assert.equal(refreshes,1);assert.equal(e.nodes.get('whoName').textContent,'Operator');
 assert.equal(typeof context.U1.navigate,'function');assert(context.listeners.hashchange.length>0);assert(e.document.listeners.click.length>0);
 assert.equal(context.ls,undefined);assert.equal(context.Sound,undefined);assert.equal(context.Notify,undefined);
});

function fixtureData(){const e=environment(),requests=[];e.context.fetch=async(url,options={})=>{if(url==='/api/integrations')return {ok:true,json:async()=>({success:true,csrf_token:'fixture'})};if(options.method==='POST')return {ok:true,json:async()=>({success:true,version:2})};return {ok:true,json:()=>new Promise(resolve=>requests.push({url,resolve,signal:options.signal}))};};vm.runInNewContext(sources['u1-data'],e.context);return {...e,api:e.window.U1Data,requests};}
test('POST invalidation detaches pending reads and rejects late pre-write data',async()=>{
 const e=fixtureData(),first=e.api.get('/api/workspace/prism/summary');const rejected=assert.rejects(first,e=>e.code==='U1_INVALIDATED');await flush();
 await e.api.post('/api/workspace/prism/record',{title:'fixture update'});const second=e.api.get('/api/workspace/prism/summary');await flush();assert.notEqual(first,second);assert.equal(e.requests.length,2);assert.equal(e.requests[0].signal.aborted,true);
 e.requests[0].resolve({success:true,version:1});e.requests[1].resolve({success:true,version:2});await rejected;assert.equal((await second).version,2);
});
test('lock invalidates pending data even if the user unlocks before the old response arrives',async()=>{
 const e=fixtureData(),first=e.api.get('/api/workspace/prism/summary');const rejected=assert.rejects(first,error=>['U1_LOCKED','U1_INVALIDATED'].includes(error.code));await flush();
 e.document.documentElement.dataset.u1Safety='locked';e.document.dispatchEvent({type:'u1:safety-change',detail:{locked:true}});await assert.rejects(e.api.get('/api/workspace/prism/summary'),/Unlock/);
 e.document.documentElement.dataset.u1Safety='open';e.requests[0].resolve({success:true,records:[{title:'OLD PRIVATE'}]});await rejected;
 const next=e.api.get('/api/workspace/prism/summary');await flush();assert.equal(e.requests.length,2);e.requests[1].resolve({success:true,records:[]});await next;
});

test('global Feedback preferences govern legacy tones, noise, gain and button aria state',()=>{
 const e=environment(),gains=[],oscillators=[],events=[];let prefs={enabled:false,volume:.3};
 e.window.U1Feedback={preferences:()=>({...prefs}),save:p=>{prefs={...p};events.push(p);}};
 class Audio{constructor(){this.state='running';this.currentTime=0;this.sampleRate=100;this.destination={};}createGain(){const gain={gain:{value:0,setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};gains.push(gain);return gain;}createOscillator(){const osc={frequency:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},start(){},stop(){}};oscillators.push(osc);return osc;}createBuffer(c,n){return {getChannelData:()=>new Float32Array(n)};}createBufferSource(){return {connect(){},start(){}};}createBiquadFilter(){return {frequency:{},Q:{},connect(){}};}}
 e.window.AudioContext=Audio;e.context.navigator={userActivation:{hasBeenActive:true}};e.context.ls=(key,fallback)=>key==='u1.sound'?'1':fallback;e.context.lsSet=()=>{throw Error('Legacy storage must not be written with Feedback available');};
 const start=sources.u1os.indexOf('  var Sound = (function () {'),end=sources.u1os.indexOf('\n  })();',start);
 vm.runInNewContext(sources.u1os.slice(start,end+9)+'\nwindow.testSound=Sound;',e.context);const sound=e.window.testSound;
 sound.nav();assert.equal(oscillators.length,0);assert.equal(gains.length,0);sound.toggle();sound.nav();assert(oscillators.length>0);assert.equal(gains[0].gain.value,.3);
 prefs={enabled:false,volume:.3};e.window.dispatchEvent({type:'u1:audio-preferences'});assert.equal(gains[0].gain.value,0);const count=oscillators.length;sound.nav();sound.tick();sound.boot();assert.equal(oscillators.length,count);
 prefs={enabled:true,volume:0};e.window.dispatchEvent({type:'u1:audio-preferences'});sound.nav();assert.equal(oscillators.length,count);
 const shell=fixtureCore();shell.window.U1.sound.enabled=()=>false;shell.shell.syncSoundButton();assert.equal(shell.nodes.get('soundBtn').getAttribute('aria-pressed'),'false');shell.window.U1.sound.enabled=()=>true;shell.shell.syncSoundButton();assert.equal(shell.nodes.get('soundBtn').getAttribute('aria-pressed'),'true');
});

function fixtureMedia(mode){
 const e=environment(),host=node('media'),player=node('u1-local-media'),mini=node('u1-player-mini'),parking=node('parking'),calls=[];let resolveStart;
 e.document.baseURI='http://localhost:8000/';parking.appendChild(mini);mini.appendChild(player);e.nodes.set(player.id,player);e.nodes.set(mini.id,mini);e.nodes.set('u1-player-title',node());
 player.paused=true;player.duration=10;player.currentSrc='';player.pause=()=>{player.paused=true;};player.load=()=>{player.currentSrc=player.getAttribute('src')||'';player.dispatchEvent({type:'loadedmetadata'});};Object.defineProperty(player,'src',{get:()=>player.getAttribute('src'),set:value=>player.setAttribute('src',value)});
 let url=0;e.context.URL=class extends URL{static createObjectURL(){return 'blob:http://localhost:8000/fixture-'+(++url);}static revokeObjectURL(){}};e.context.btoa=s=>Buffer.from(s,'binary').toString('base64');e.window.U1CoreViews={register(){}};
 e.context.fetch=async(url,options={})=>{
  if(url==='/api/integrations')return {ok:true,json:async()=>({success:true,csrf_token:'fixture'})};
  const payload=options.body?JSON.parse(options.body):null;calls.push({url,payload});
  if(url.endsWith('/upload-start')&&mode==='cancel')return {ok:true,json:()=>new Promise(resolve=>resolveStart=resolve)};
  if(url.endsWith('/upload-start'))return {ok:true,json:async()=>({success:true,id:'owned-reservation'})};
  if(url.endsWith('/upload-chunk'))return {ok:mode==='ready',json:async()=>mode==='ready'?{success:true,status:'ready',received:4}:{success:false,error:'Fixture chunk failure'}};
  if(url.endsWith('/upload-abort'))return {ok:true,json:async()=>({success:true})};
  return {ok:false,json:async()=>({success:false,error:'Fixture library failure'})};
 };
 vm.runInNewContext(expose(sources['u1-media-research'],`window.auditMedia={seed:function(h){mediaRoot=h;cap={ffmpeg_available:true};},loadFile:loadFile,sourceChanged:sourceChanged,managedSource:managedSource,availability:availability,importSelected:importSelected,snapshot:function(){return {selected:selected,sourceId:sourceId,ownedSource:ownedSource};}};`),e.context);
 const api=e.window.auditMedia;api.seed(host);const file={name:'fixture.wav',size:4,type:'audio/wav',slice:()=>({arrayBuffer:async()=>new Uint8Array([1,2,3,4]).buffer})};
 return {...e,api,host,player,calls,file,resolveStart:value=>resolveStart(value)};
}
test('external player replacement or clear invalidates source identity, consent and export controls',()=>{
 for(const replacement of ['blob:http://localhost:8000/external','']){
  const e=fixtureMedia();e.api.loadFile(e.file,'owned-file');e.host.querySelector('[name=rights]').checked=true;e.api.availability();assert.equal(e.host.querySelector('[data-mr-export]').disabled,false);
  if(replacement)e.player.src=replacement;else e.player.removeAttribute('src');e.api.sourceChanged();
  assert.equal(e.api.snapshot().sourceId,null);assert.equal(e.api.snapshot().selected,null);assert.equal(e.host.querySelector('[name=rights]').checked,false);assert.equal(e.host.querySelector('[data-mr-export]').disabled,true);assert.throws(()=>e.api.managedSource(),/Choose or reload/);
 }
});
test('cancelled import releases only its own incomplete reservation and never starts old-source chunks',async()=>{
 const e=fixtureMedia('cancel');e.api.loadFile(e.file);e.host.querySelector('[name=rights]').checked=true;const importing=e.api.importSelected();const rejected=assert.rejects(importing,/changed/);await flush();
 e.player.src='blob:http://localhost:8000/replacement';e.api.sourceChanged();e.resolveStart({success:true,id:'owned-reservation'});await rejected;
 assert.deepEqual(e.calls.filter(c=>c.url.endsWith('/upload-abort')).map(c=>c.payload),[{id:'owned-reservation'}]);assert.equal(e.calls.some(c=>c.url.endsWith('/upload-chunk')),false);assert.equal(e.api.snapshot().sourceId,null);
});
test('failed chunks are aborted, but a completed managed file is never aborted for a later library-read failure',async()=>{
 for(const mode of ['failure','ready']){
  const e=fixtureMedia(mode);e.api.loadFile(e.file);e.host.querySelector('[name=rights]').checked=true;await assert.rejects(e.api.importSelected(),/Fixture/);
  assert.equal(e.calls.filter(c=>c.url.endsWith('/upload-abort')).length,mode==='ready'?0:1);assert.equal(e.api.snapshot().sourceId,mode==='ready'?'owned-reservation':null);
 }
});
