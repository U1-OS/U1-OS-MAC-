import {icon,badge,escape as esc} from './prism-ui.js';
let root,detail,surface,timer,usage=null,busy=false,lastSuccess=0;
const framed=new URLSearchParams(location.search).has('u1-frame');
const names={codex:'Codex',claude:'Claude',antigravity:'Antigravity'};
const validWindow=w=>typeof w.used_percent==='number'&&Number.isFinite(w.used_percent);
const percent=w=>Math.min(100,Math.max(0,w.used_percent));
const reset=w=>w.resets_at?new Date(w.resets_at*1000).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Not supplied';
function render(){
  const providers=usage?.providers||{};
  root.querySelector('#u1-usage-compact').innerHTML=Object.entries(names).map(([id,name])=>{const provider=providers[id];const windows=provider?.windows?.filter(validWindow)||[];const w=windows.find(x=>x.name?.toLowerCase()===id)||windows[0];const fresh=provider?.success&&!provider.stale&&Date.now()-lastSuccess<120000;const active=fresh&&w&&(!w.resets_at||w.resets_at*1000>Date.now());return `<div title="${esc(provider?.notice||provider?.source||'Allowance not connected')}">${badge(name)}<span>${name}</span><b>${active?Math.round(percent(w))+'%':w&&!fresh?'Stale':'--'}</b></div>`;}).join('');
  const body=detail.querySelector('#u1-usage-body');
  body.innerHTML=Object.entries(names).map(([id,name])=>{const p=providers[id],windows=p?.windows?.filter(validWindow)||[];const fresh=p?.success&&!p.stale&&Date.now()-lastSuccess<120000;return `<section class="u1-usage-provider"><h3>${badge(name)}${name}<span>${fresh&&windows.length?'REPORTED ALLOWANCES':fresh?'LOCAL STATUS ONLY':'UNAVAILABLE / STALE'}</span></h3>${windows.map(w=>`<div class="u1-usage-window"><div><span>${esc(w.name||name)} / ${esc(w.period||'window')}</span><strong>${Math.round(percent(w))}% used</strong></div><progress value="${percent(w)}" max="100" aria-label="${esc(w.name||name)} used allowance"></progress><small>Reset: ${esc(reset(w))}${w.resets_at*1000<=Date.now()?' / awaiting refreshed allowance':''}${!fresh?' / stale report':''}</small></div>`).join('')||'<p>Subscription percentage is not available. No allowance has been inferred from local activity.</p>'}<p>${esc(p?.notice||p?.source||'No successful response yet.')}</p>${p?.checked_at?`<small>Source checked ${esc(new Date(p.checked_at*1000).toLocaleTimeString())}</small>`:''}</section>`;}).join('');
  detail.querySelector('#u1-usage-refreshed').textContent=lastSuccess?`Last response ${new Date(lastSuccess).toLocaleTimeString()}. Refreshes every 60 seconds while visible.`:'Waiting for the local usage service.';
}
async function refresh(){if(busy||document.hidden)return;busy=true;const abort=new AbortController(),timeout=setTimeout(()=>abort.abort(),20000);try{const res=await fetch('/api/workspace/usage',{cache:'no-store',signal:abort.signal});const data=await res.json();if(!res.ok||!data.success)throw new Error('unavailable');usage=data;lastSuccess=Date.now();}catch{if(usage)for(const p of Object.values(usage.providers||{}))p.stale=true;}finally{clearTimeout(timeout);busy=false;render();}}
function closeSurface(){if(!surface)return;surface.hidden=true;surface.querySelector('iframe').src='about:blank';document.body.classList.remove('u1-app-open');}
function openSurface(path,title){
  if(!surface){surface=document.createElement('section');surface.id='u1-app-surface';surface.setAttribute('aria-label','Workspace application');surface.innerHTML=`<header><div>${icon('globe')}<strong></strong><span>WORKSPACE APP / PLAYBACK STAYS WITH YOU</span></div><button type="button" aria-label="Return to workspace">${icon('close')} Return</button></header><iframe title="Workspace application"></iframe>`;surface.querySelector('button').onclick=closeSurface;document.body.append(surface);}
  surface.querySelector('strong').textContent=title;surface.querySelector('iframe').title=title;surface.querySelector('iframe').src=path+'?u1-frame=1';surface.hidden=false;document.body.classList.add('u1-app-open');
}
function init(){
  const style=document.createElement('link');style.rel='stylesheet';style.href='/css/u1-global-controls.css';if(!document.querySelector('link[href="/css/u1-global-controls.css"]'))document.head.append(style);
  if(framed){document.documentElement.classList.add('u1-framed');document.addEventListener('click',event=>{const link=event.target.closest('a[href]');if(!link)return;try{const u=new URL(link.href);if(u.origin===location.origin&&u.pathname==='/'){event.preventDefault();window.parent.postMessage({type:'u1-close-app'},location.origin);}}catch{}},true);return;}
  root=document.createElement('aside');root.id='u1-global-widgets';root.setAttribute('aria-label','Shared player and AI usage controls');
  root.innerHTML=`<div class="u1-global-heading"><span>U1 CONTROL</span><button type="button" id="u1-usage-open" aria-label="Open all usage limits">${icon('system')}</button><button type="button" data-u1-player-open aria-label="Open music and video player">${icon('media')}</button></div><button type="button" id="u1-usage-summary" aria-label="View provider usage allowances"><span id="u1-usage-compact"></span></button><small>Separate provider allowances</small>`;
  document.body.append(root);document.body.classList.add('u1-has-global-widgets');
  const mini=document.querySelector('#u1-now-playing');if(mini)root.append(mini);
  detail=document.createElement('dialog');detail.id='u1-usage-dialog';detail.setAttribute('aria-labelledby','u1-usage-title');detail.innerHTML=`<header><div><small>U1 OS / PROVIDER ALLOWANCES</small><h2 id="u1-usage-title">One view. Honest limits.</h2></div><button type="button" aria-label="Close usage limits">${icon('close')}</button></header><p class="u1-usage-explainer">Each provider keeps its own subscription, quota and reset window. A routing gateway cannot turn these into one shared allowance.</p><div id="u1-usage-body"></div><footer><p id="u1-usage-refreshed"></p><button type="button" id="u1-usage-refresh">Refresh usage</button><a href="http://127.0.0.1:20128/" target="_blank" rel="noopener noreferrer">Open local OmniRoute dashboard ${icon('external')}</a></footer>`;
  document.body.append(detail);detail.querySelector('header button').onclick=()=>detail.close();root.querySelector('#u1-usage-open').onclick=root.querySelector('#u1-usage-summary').onclick=()=>detail.showModal();detail.querySelector('#u1-usage-refresh').onclick=refresh;
  document.addEventListener('click',event=>{
    const route=event.target.closest('[data-route]')?.dataset.route;const anchor=event.target.closest('a[href]');let path;try{const u=anchor?new URL(anchor.href):null;if(u?.origin===location.origin)path=u.pathname;}catch{}
    if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    if(document.querySelector('#prism-shell')&&(route==='studio'||path==='/studio.html'||route==='connections'||path==='/integrations.html')){event.preventDefault();event.stopImmediatePropagation();const studio=route==='studio'||path==='/studio.html';openSurface(studio?'/studio.html':'/integrations.html',studio?'Creative Studio':'Integrations');return;}
    if(route&&surface&&!surface.hidden)closeSurface();
  },true);
  window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===surface?.querySelector('iframe')?.contentWindow&&event.data?.type==='u1-close-app')closeSurface();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  refresh();timer=setInterval(refresh,60000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(init),{once:true});else requestAnimationFrame(init);
