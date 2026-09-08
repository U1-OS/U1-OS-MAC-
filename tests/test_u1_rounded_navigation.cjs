'use strict';
/* Shell contracts and real appearance/audio event handlers. No browser or app data. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const read=name=>fs.readFileSync(path.join(root,'static',name),'utf8');
const html=read('u1os.html'),rounded=read('js/u1-rounded-system.js'),platform=read('js/u1-platform.js'),native=read('js/u1-native-operations.js');
const scripts=[...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"/g)].map(x=>x[1]);
const styles=[...html.matchAll(/<link\b[^>]*\bhref="([^"]+\.css(?:\?[^"]*)?)"/g)].map(x=>x[1]);
function target(value={}){const listeners={};return Object.assign(value,{listeners,addEventListener(type,fn){(listeners[type]||=[]).push(fn);},dispatchEvent(event){for(const fn of listeners[event.type]||[])fn(event);return true;}});}
function appearanceFixture(){
 const calls=[],registered={},elements=new Map();let feedback={enabled:false,volume:.3};
 const document={documentElement:{dataset:{}},getElementById:()=>null,querySelectorAll:()=>[]};
 const window=target({document,localStorage:{getItem:()=>null,setItem(){}},Event:class{constructor(type){this.type=type;}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},U1CoreViews:{register(id,render,hooks){registered[id]={render,hooks};}},U1Feedback:{preferences:()=>({...feedback}),save(patch){feedback={...feedback,...patch};},play(kind,preview){calls.push({kind,preview,volume:feedback.volume});return Promise.resolve(true);}}});
 vm.runInNewContext(rounded,{window,console,Set,CustomEvent:window.CustomEvent});
 const host={isConnected:true,writes:0,contains:()=>true,querySelectorAll:()=>[],querySelector(selector){if(!elements.has(selector))elements.set(selector,{textContent:'',checked:false,value:'',setAttribute(){}});return elements.get(selector);},get innerHTML(){return this.markup||'';},set innerHTML(value){this.markup=value;this.writes++;}};
 return {window,calls,registered,host,setFeedback:patch=>{feedback={...feedback,...patch};}};
}

test('Create/Earn and Appearance assets load once after the native widgets and feedback',()=>{
 const index=name=>scripts.findIndex(url=>url.startsWith('/js/'+name+'.js?'));
 for(const name of ['u1-create-earn-workspaces','u1-rounded-system'])assert.equal(scripts.filter(url=>url.startsWith('/js/'+name+'.js?')).length,1);
 for(const dependency of ['u1-core-workspaces','u1-feedback','u1-spotify-widget','u1-operational-polish','u1-native-operations'])assert(index(dependency)>=0&&index(dependency)<index('u1-create-earn-workspaces'),dependency);
 assert(index('u1-create-earn-workspaces')<index('u1-rounded-system'));
});
test('rounded global CSS is last and new hub styles follow release and operational polish',()=>{
 assert.equal(styles.at(-1),'/css/u1-rounded-system.css?v=20260908.11');
 const hub=styles.indexOf('/css/u1-create-earn-workspaces.css?v=20260908.8');assert(hub>=0);
 for(const part of ['release-polish','operational-polish']){const at=styles.findIndex(url=>url.includes(part));assert(at>=0&&at<hub,part);}
});
test('browser-visible repaired boot and Safety assets have a fresh cache key',()=>{
 for(const name of ['u1-cinematic','u1-safety'])assert(scripts.includes('/js/'+name+'.js?v=20260908.9'),name);
 assert(scripts.includes('/js/u1os.js?v=20260908.10'));
 for(const name of ['u1-operational-polish','u1-discovery-workspace','u1-workspaces'])assert(scripts.includes('/js/'+name+'.js?v=20260908.11'),name);
 for(const name of ['u1-feedback','u1-create-earn-workspaces','u1-rounded-system'])assert(scripts.includes('/js/'+name+'.js?v=20260908.8'),name);
});
test('real platform navigation accepts new hubs and Appearance, including no-rail hash fallback',()=>{
 const navigated=[],document=target({readyState:'loading',documentElement:{dataset:{u1Safety:'open'}},querySelector:()=>null,querySelectorAll:()=>[],getElementById:()=>null});
 const window=target({U1PlatformCore:require('../static/js/u1-platform-core.js'),U1:{navigate:id=>navigated.push(id)}});let hash='';const location={get hash(){return hash;},set hash(value){hash=value?(value.startsWith('#')?value:'#'+value):'';}};
 const end=platform.lastIndexOf('})();');assert(end>0);
 vm.runInNewContext(platform.slice(0,end)+'window.fixtureNavigate=navigate;window.fixtureSearch=searchHTML;\n'+platform.slice(end),{window,document,location,URL,URLSearchParams,console,setTimeout(){},clearTimeout(){}});
 for(const id of ['create','earn','appearance']){window.fixtureNavigate(id);assert(navigated.includes(id),id);assert.match(window.fixtureSearch(id),new RegExp(id,'i'));}
 delete window.U1;for(const id of ['create','earn','appearance']){location.hash='';window.fixtureNavigate(id);assert.equal(location.hash,'#'+id);}
 document.documentElement.dataset.u1Safety='locked';const count=navigated.length;location.hash='';window.fixtureNavigate('appearance');assert.equal(navigated.length,count);assert.equal(location.hash,'');
});
test('native registry keeps the advanced workspaces while exposing the new hub and Settings context',()=>{
 for(const id of ['create','earn','appearance','studio','income','crypto','trading'])assert(platform.includes("'"+id+"'"),id);
 assert.match(native,/settings:\[\['appearance'/);assert.match(native,/appearance:\[\['settings'/);
 assert.match(native,/create:\[\['studio'/);assert.match(native,/earn:\[\['income'/);
});
test('automatic startup audio requires both startup opt-in and authoritative global audio enable',()=>{
 const f=appearanceFixture();f.setFeedback({enabled:true});f.window.dispatchEvent({type:'u1:boot-start'});assert.equal(f.calls.length,0);
 f.window.U1Rounded.save({startupSound:true});f.setFeedback({enabled:false});f.window.dispatchEvent({type:'u1:boot-start'});assert.equal(f.calls.length,0);
 f.setFeedback({enabled:true,volume:.17});f.window.dispatchEvent({type:'u1:boot-start'});assert.deepEqual(f.calls,[{kind:'startup',preview:false,volume:.17}]);
 f.window.U1Rounded.save({startupSound:false});f.window.dispatchEvent({type:'u1:boot-start'});assert.equal(f.calls.length,1);
});
test('force-preview tone is only requested through an explicit Appearance gesture',()=>{
 const f=appearanceFixture();f.registered.appearance.render(f.host);assert.equal(f.calls.length,0);
 const button={getAttribute:name=>name==='data-u1r-action'?'tone':null,dataset:{u1rAction:'tone'},closest:()=>button};
 f.host.onclick({target:button});assert.equal(f.calls.length,1);assert.equal(f.calls[0].kind,'startup');assert.equal(f.calls[0].preview,true);
});
test('Appearance reactivation syncs preferences without replacing mounted DOM',()=>{
 const f=appearanceFixture();f.registered.appearance.render(f.host);const writes=f.host.writes;
 f.registered.appearance.hooks.deactivate(f.host);f.window.U1Rounded.save({theme:'daylight'});f.registered.appearance.hooks.activate(f.host);
 assert.equal(f.host.writes,writes);assert.equal(f.window.document.documentElement.dataset.u1WidgetTheme,'daylight');assert.equal(f.window.document.documentElement.dataset.u1Rounded,'true');
});
