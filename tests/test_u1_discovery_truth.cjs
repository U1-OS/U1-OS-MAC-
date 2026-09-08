'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const discovery = require('../static/js/u1-discovery-workspace.js');
const settle = () => new Promise(resolve => setImmediate(resolve));
const snapshot = (title = 'Real fixture headline', fetched = Date.now() / 1000) => ({
  success: true, stale: false, fetched_at: fetched, attempted_at: fetched, refresh_seconds: 300,
  source: 'Fixture publisher', items: [{title, url: 'https://www.bbc.com/news/fixture'}]
});
function fixture() {
  const routes = {}, requests = [], doc = {};
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.ownerDocument = doc; this.children = []; this.dataset = {}; this.value = ''; this.attrs = {}; this.handlers = {}; this._text = ''; }
    set textContent(text) { this._text = String(text); this.children = []; }
    get textContent() { return this._text + this.children.map(node => node.textContent || '').join(' '); }
    append(...nodes) { this.children.push(...nodes); if (this.tagName === 'SELECT' && !this.value && nodes[0]) this.value = nodes[0].value; }
    replaceChildren(...nodes) { this._text = ''; this.children = []; this.append(...nodes); }
    setAttribute(key, value) { this.attrs[key] = value; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
  }
  const win = {AbortController, setTimeout() { return 1; }, clearTimeout() {},
    fetch(url, options) { return new Promise(resolve => requests.push({url, signal: options.signal,
      complete(payload) { resolve({ok: true, json: async () => payload}); }})); }};
  doc.defaultView = win; doc.createElement = tag => new Element(tag);
  discovery.register({register(id, render, hooks) { routes[id] = {render, hooks}; }});
  const host = new Element('main');
  function flat(node = host) { return [node, ...node.children.flatMap(flat)]; }
  return {routes, requests, host, flat};
}
async function boot(good = snapshot()) {
  const f = fixture(); f.routes['tech-gaming'].render(f.host); f.requests[0].complete(good); await settle(); return f;
}
function refresh(f) { f.flat().find(node => node.tagName === 'BUTTON' && node.textContent === 'Refresh').handlers.click(); }
test('HTTP 200 provider failure retains last-good content, timestamp and error label', async () => {
  const good = snapshot(); const f = await boot(good); refresh(f);
  f.requests[1].complete({success: false, items: [], attempted_at: Date.now()/1000, error: 'Fixture provider unavailable'}); await settle();
  assert.ok(f.host.textContent.includes(good.items[0].title)); assert.match(f.host.textContent, /stale/i);
  assert.ok(f.host.textContent.includes('Fixture provider unavailable'));
  assert.ok(f.host.textContent.includes(new Date(good.fetched_at*1000).toLocaleString()));
});
test('successful empty snapshot clears old headlines and old failure', async () => {
  const f = await boot(); refresh(f); f.requests[1].complete({success:false, error:'Old fixture error'}); await settle();
  refresh(f); f.requests[2].complete({...snapshot(), items:[]}); await settle();
  assert.doesNotMatch(f.host.textContent, /Real fixture headline|Old fixture error/);
});
test('cold failure stays unavailable without invented stories', async () => {
  const f = await boot({success:false, items:[], error:'Cold fixture outage'});
  assert.match(f.host.textContent, /unavailable/i); assert.match(f.host.textContent, /Cold fixture outage/);
  assert.equal(f.flat().filter(node=>node.tagName==='ARTICLE').length,0);
});
test('older server cache cannot replace newer browser last-good', async () => {
  const f = await boot(snapshot('Newer browser story',Date.now()/1000)); refresh(f);
  f.requests[1].complete({...snapshot('Older server story',Date.now()/1000-600),success:false,stale:true}); await settle();
  assert.match(f.host.textContent,/Newer browser story/); assert.doesNotMatch(f.host.textContent,/Older server story/);
});
test('first failed server response may expose actual retained data only as stale', async () => {
  const f = await boot({...snapshot('Retained server fixture'),success:false,stale:true,error:'Feed outage'});
  assert.match(f.host.textContent,/Retained server fixture/); assert.match(f.host.textContent,/stale/i);
  assert.match(f.host.textContent,/Feed outage/);
});
const workspaceSource = fs.readFileSync(require.resolve('../static/js/u1-workspaces.js'),'utf8');
const weatherFunction = workspaceSource.slice(workspaceSource.indexOf(' function weatherWidget(){'),workspaceSource.indexOf(' function integrationList'));
async function renderWeather(value) {
  const node={innerHTML:''};
  const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const context={window:{U1Launch:{get:async()=>value}},el:()=>node,finite:value=>typeof value==='number'&&Number.isFinite(value),esc,empty:(title,description)=>title+' '+description,Date};
  vm.runInNewContext(weatherFunction+';weatherWidget()',context);
  await settle(); return node.innerHTML;
}
test('weather displays supplied place, observation time, timezone and fetch time safely', async () => {
  const html=await renderWeather({success:true,city:'Actual <town>',region:'Region',country:'Country',source:'Fixture <provider>',current:{temperature_2m:17,time:'2026-09-08T19:00'},timezone:'Australia/Melbourne',fetched_at:Date.now()/1000});
  assert.match(html,/Actual &lt;town&gt;, Region, Country/);assert.match(html,/2026-09-08T19:00/);
  assert.match(html,/Australia\/Melbourne/);assert.match(html,/Fetched \(device time\)/);assert.doesNotMatch(html,/<town>|<provider>/);
});
test('weather failed retained values are labelled stale; cold failures are unavailable', async () => {
  assert.match(await renderWeather({success:false,stale:true,current:{temperature_2m:17},fetched_at:Date.now()/1000-900}),/Stale weather snapshot/);
  assert.match(await renderWeather({success:false}),/Weather unavailable/);
});
test('weather never invents missing location, timestamp or timezone', async () => {
  const html=await renderWeather({success:true,current:{temperature_2m:17}});
  assert.match(html,/Location not supplied/);assert.match(html,/Provider time: Not supplied/);assert.match(html,/Timezone: Not supplied/);
});
