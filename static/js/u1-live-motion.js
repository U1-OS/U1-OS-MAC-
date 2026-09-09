// Motion is presentation only. Live / snapshot / unavailable labels remain intact.
const shapes={weather:'<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',afl:'<ellipse cx="12" cy="12" rx="6" ry="10" transform="rotate(35 12 12)"/><path d="m9 8 6 8m-6-5 5-3m-3 6 5-3"/>',cricket:'<path d="m6 20 9-12 4 3-10 12ZM17 8l4-6"/><circle cx="5" cy="6" r="3"/>',mma:'<path d="m5 6 4 2 3-5 4 2 3 7-3 8H8L4 12Z"/>',boxing:'<path d="M5 13V7a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v8l-3 3H8Z M8 18v4h8v-4M5 9H3v6l5 3"/>',markets:'<path d="M3 21h18M5 16V9m5 7V5m5 11v-4m5 4V2"/>',news:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M7 7h4v5H7Zm8 0h3m-3 5h3M7 16h11"/>',shares:'<path d="m3 17 6-7 5 3 7-10m-6 0h6v6M3 22h18"/>'};
const countries={'australia':'AU','england':'GB','united kingdom':'GB','india':'IN','pakistan':'PK','new zealand':'NZ','south africa':'ZA','sri lanka':'LK','bangladesh':'BD','afghanistan':'AF','nepal':'NP','saudi arabia':'SA','oman':'OM','united arab emirates':'AE','ireland':'IE','scotland':'GB','zimbabwe':'ZW','netherlands':'NL','canada':'CA','united states':'US','usa':'US','namibia':'NA','uganda':'UG','kenya':'KE'};
const flag=code=>String.fromCodePoint(...code.toUpperCase().split('').map(c=>127397+c.charCodeAt(0)));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function badge(team){
  const name=String(team.name||'Team');const country=countries[name.toLowerCase()];
  let logo='';try{const url=new URL(team.logo);if(url.protocol==='https:'&&!url.username&&!url.password)logo=url.href;}catch{}
  if(logo)return `<img class="u1-team-symbol" src="${esc(logo)}" alt="" title="${esc(name)}" referrerpolicy="no-referrer">`;
  if(country)return `<span class="u1-team-flag" title="${esc(name)}" aria-label="${esc(name)} flag">${flag(country)}</span>`;
  return `<span class="u1-team-initials" title="${esc(name)} / initials, logo unavailable">${esc(name.split(/\s+/).map(w=>w[0]).slice(0,2).join(''))}</span>`;
}
function init(){
  const bar=document.querySelector('.u1-live-bar'),track=bar?.querySelector('.live-bar-track');if(!track)return;
  const style=document.createElement('link');style.rel='stylesheet';style.href='/css/u1-global-controls.css';if(!document.querySelector('link[href="/css/u1-global-controls.css"]'))document.head.append(style);
  let enabled=true;try{enabled=localStorage.getItem('u1-live-moving')!=='off';}catch{}
  const toggle=document.createElement('button');toggle.type='button';toggle.className='u1-ticker-toggle';
  const updateToggle=()=>{toggle.setAttribute('aria-label',enabled?'Pause moving live bar':'Resume moving live bar');toggle.title=enabled?'Pause ticker movement':'Resume ticker movement';toggle.innerHTML=enabled?'<svg viewBox="0 0 20 20"><path d="M7 4v12M13 4v12"/></svg>':'<svg viewBox="0 0 20 20"><path d="m6 3 10 7-10 7Z"/></svg>';toggle.setAttribute('aria-pressed',String(!enabled));};
  toggle.onclick=()=>{enabled=!enabled;try{localStorage.setItem('u1-live-moving',enabled?'on':'off');}catch{}updateToggle();};updateToggle();bar.insertBefore(toggle,bar.querySelector('.live-options-button')); 
  let hovering=false,manualUntil=0,previous=0,direction=1,frame;
  bar.addEventListener('pointerenter',()=>hovering=true);bar.addEventListener('pointerleave',()=>hovering=false);
  track.addEventListener('wheel',()=>manualUntil=performance.now()+5000,{passive:true});track.addEventListener('touchstart',()=>manualUntil=performance.now()+8000,{passive:true});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function step(now){const dt=Math.min(now-(previous||now),60);previous=now;
    if(enabled&&!hovering&&!document.hidden&&!reduced.matches&&document.documentElement.dataset.u1Motion!=='off'&&!bar.contains(document.activeElement)&&now>manualUntil){const max=track.scrollWidth-track.clientWidth;if(max>0){track.scrollLeft+=direction*dt*.024;if(track.scrollLeft>=max-1)direction=-1;else if(track.scrollLeft<=0)direction=1;}}
    frame=requestAnimationFrame(step);
  }frame=requestAnimationFrame(step);
  function decorate(){for(const chip of track.querySelectorAll('.live-chip')){if(chip.querySelector('.u1-feed-symbol'))continue;const id=chip.dataset.livePane||chip.querySelector('strong')?.id.replace('live-','');const shape=shapes[id];if(!shape)continue;const el=document.createElement('span');el.className='u1-feed-symbol';el.setAttribute('aria-hidden','true');el.innerHTML=`<svg viewBox="0 0 24 24">${shape}</svg>`;chip.prepend(el);}}
  const observer=new MutationObserver(decorate);observer.observe(track,{childList:true});decorate();
  const sportsHandler=event=>{for(const {sport,events} of event.detail){const chip=track.querySelector(`[data-live-pane="${sport}"]`);if(!chip)continue;const match=events.find(e=>e.state==='in')||events[0];const teams=match?.competitors||[];let group=chip.querySelector('.u1-live-team-marks');if(!teams.length){group?.remove();continue;}if(!group){group=document.createElement('span');group.className='u1-live-team-marks';group.setAttribute('aria-hidden','true');chip.insertBefore(group,chip.querySelector('strong'));}const content=teams.slice(0,2).map(badge).join('');if(group.innerHTML!==content)group.innerHTML=content;}};
  window.addEventListener('u1-live-sports',sportsHandler);
  const detail=document.querySelector('#liveDialogBody');let detailsObserver;
  if(detail){detailsObserver=new MutationObserver(()=>{for(const row of detail.querySelectorAll('.live-team')){if(row.querySelector('.u1-team-symbol,.u1-team-flag,.u1-team-initials'))continue;const name=row.querySelector('b')?.textContent;if(name)row.insertAdjacentHTML('afterbegin',badge({name}));}});detailsObserver.observe(detail,{childList:true});}
  window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);observer.disconnect();detailsObserver?.disconnect();window.removeEventListener('u1-live-sports',sportsHandler);},{once:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(init),{once:true});else requestAnimationFrame(init);
