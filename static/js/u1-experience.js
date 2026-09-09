import {icon, mark} from './u1-icons.js';

const KEY='u1-experience-v1';
let settings={sounds:true,volume:22,boot:true,motion:true};
try{const saved=JSON.parse(localStorage.getItem(KEY)||'{}');for(const key of ['sounds','boot','motion'])if(typeof saved[key]==='boolean')settings[key]=saved[key];if(Number.isFinite(saved.volume))settings.volume=Math.max(0,Math.min(100,saved.volume));}catch(_){}
let audio=null,unlocked=false,lastSound=0,boot=null,bootPoll=null,settingsPanel=null,observer=null,started=Date.now();
const remembered=new WeakMap(),motion=matchMedia('(prefers-reduced-motion: reduce)');
const css=document.createElement('link');css.rel='stylesheet';css.href='/css/u1-experience.css';document.head.appendChild(css);
function preferences(){document.documentElement.dataset.u1Motion=settings.motion?'on':'off';try{localStorage.setItem(KEY,JSON.stringify(settings));}catch(_){} }
preferences();

async function unlock(){
  if(!settings.sounds)return;
  try{const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;if(!audio)audio=new Audio();if(audio.state==='suspended')await audio.resume();unlocked=audio.state==='running';}catch(_){unlocked=false;}
}
function chime(urgent=false,force=false){
  if(!settings.sounds||!unlocked||!audio||document.hidden)return;
  if(!force&&Date.now()-lastSound<2500)return;lastSound=Date.now();
  const volume=settings.volume/100*.16,notes=urgent?[523.25,440]:[659.25,987.77];
  notes.forEach((frequency,index)=>{const start=audio.currentTime+index*.095,oscillator=audio.createOscillator(),gain=audio.createGain();oscillator.type='sine';oscillator.frequency.value=frequency;gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(volume,start+.015);gain.gain.exponentialRampToValueAtTime(.0001,start+.24);oscillator.connect(gain);gain.connect(audio.destination);oscillator.start(start);oscillator.stop(start+.26);oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};});
}
document.addEventListener('pointerdown',()=>unlock(),{passive:true});
document.addEventListener('keydown',()=>unlock(),{passive:true});

function showBoot(){
  if(boot)return;
  const began=Date.now();boot=document.createElement('section');boot.id='u1-boot-screen';boot.setAttribute('aria-label','U1 OS startup');boot.setAttribute('role','status');
  boot.innerHTML=`<div class="u1-boot-stars"></div><div class="u1-boot-content"><div class="u1-boot-emblem"><i></i><i></i>${mark()}</div><p class="u1-boot-kicker">YOUR PERSONAL COMMAND CENTRE</p><h1>U1 OS</h1><p class="u1-boot-tagline">YOUR WORLD. AMPLIFIED.</p><div class="u1-boot-line"><span></span></div><p id="u1-boot-status">Starting your workspace</p><div class="u1-boot-checks"><span data-boot-check="interface">Interface <i>Checking</i></span><span data-boot-check="workspace">Local workspace <i>Connecting</i></span><span data-boot-check="readers">Live readers <i>Starting</i></span></div><button type="button" id="u1-boot-skip">Continue to workspace ${icon('arrow')}</button></div><footer>BUILT AROUND YOU <b>+</b> POWERED BY POSSIBILITY</footer>`;
  document.body.appendChild(boot);boot.querySelector('#u1-boot-skip').addEventListener('click',hideBoot);
  bootPoll=setInterval(()=>{
    if(!boot)return;const label=document.getElementById('prism-connection-label')?.textContent||'',online=label.includes('ONLINE'),offline=label.includes('UNAVAILABLE'),shell=!!document.getElementById('prism-shell');
    const interfaceReady=shell&&[...document.querySelectorAll('link[rel="stylesheet"]')].filter(link=>/prism-os|u1-reference/.test(link.href)).every(link=>!!link.sheet);
    const set=(name,text,ready)=>{const el=boot.querySelector(`[data-boot-check="${name}"]`);el.querySelector('i').textContent=text;el.classList.toggle('ready',ready);};
    set('interface',interfaceReady?'Ready':'Loading',interfaceReady);set('workspace',online?'Online':offline?'Offline':'Connecting',online);set('readers',online?'Checking sources':'Waiting',false);
    boot.querySelector('#u1-boot-status').textContent=online?'Your workspace is ready':offline?'Local server unavailable. You can still open the interface.':'Connecting to your local workspace';
    if(interfaceReady&&online&&Date.now()-began>1300||Date.now()-began>8500)hideBoot();
  },180);
}
function hideBoot(){if(!boot)return;clearInterval(bootPoll);bootPoll=null;const element=boot;boot=null;element.classList.add('complete');setTimeout(()=>element.remove(),motion.matches?0:260);}

function experiencePanel(){
  const page=document.getElementById('prism-page');if(!page?.classList.contains('prism-view-settings'))return;
  if(page.querySelector('#u1-experience-panel'))return;
  settingsPanel=document.createElement('section');settingsPanel.id='u1-experience-panel';settingsPanel.className='prism-panel u1-experience-panel';
  settingsPanel.innerHTML=`<header><h2>${icon('settings')}Sound, motion & startup</h2><span class="prism-status neutral">This browser</span></header><div class="u1-experience-options"><label><span>${icon('bell')}Notification sounds<small>Gentle local tones after your first interaction.</small></span><input type="checkbox" data-u1-setting="sounds" ${settings.sounds?'checked':''}></label><label><span>${icon('ai')}Animated neon icons<small>Reduced-motion settings always take precedence.</small></span><input type="checkbox" data-u1-setting="motion" ${settings.motion?'checked':''}></label><label><span>${icon('home')}U1 startup screen<small>Shows real local workspace readiness on a new session.</small></span><input type="checkbox" data-u1-setting="boot" ${settings.boot?'checked':''}></label><label class="u1-volume"><span>Notification volume <output>${settings.volume}%</output></span><input type="range" min="0" max="100" value="${settings.volume}" data-u1-setting="volume" aria-label="Notification volume"></label></div><div class="prism-inline-actions"><button type="button" class="prism-button primary" data-u1-test-sound>Test notification sound</button><button type="button" class="prism-button quiet" data-u1-replay-boot>Preview startup screen</button></div><p class="prism-source">Audio is synthesized locally. No audio files, microphone permissions, or external service are needed. Preferences are stored in this browser.</p>`;
  page.appendChild(settingsPanel);
}

function observeToasts(){
  for(const id of ['prism-toast','u1WorkspaceToast','liveEventToast','u1-workspace-toast']){
    const el=document.getElementById(id);if(!el)continue;const text=el.textContent.trim(),before=remembered.get(el);remembered.set(el,text);
    if(!text||before===text||el.hidden||getComputedStyle(el).display==='none'||Date.now()-started<4000)continue;
    chime(el.classList.contains('error')||/warning|critical|failed/i.test(text));
  }
}
function decorateCurrencies(){
  const bar=document.getElementById('prism-live-bar');if(!bar)return;
  const button=[...bar.querySelectorAll('button')].find(item=>item.textContent.includes('BTC / ETH / SOL'));
  if(button&&!button.querySelector('.u1-currency-icons')){
    const icons=document.createElement('span');icons.className='u1-currency-icons';icons.setAttribute('aria-hidden','true');
    icons.innerHTML='<i class="u1-coin bitcoin">&#8383;</i><i class="u1-coin ethereum"><svg viewBox="0 0 24 24"><path d="m12 2-6 10 6 4 6-4-6-10Zm-6 12 6 8 6-8-6 4-6-4Z" fill="currentColor"/></svg></i><i class="u1-coin solana"><svg viewBox="0 0 24 24"><path d="m6 5 13 0-3 3H3l3-3Zm-3 6h13l3 3H6l-3-3Zm3 6h13l-3 3H3l3-3Z" fill="currentColor"/></svg></i>';button.prepend(icons);
  }
}
let queued=false;
function update(){if(queued)return;queued=true;queueMicrotask(()=>{queued=false;experiencePanel();observeToasts();decorateCurrencies();});}
function start(){
  observer=new MutationObserver(update);observer.observe(document.body,{childList:true,subtree:true,characterData:true});update();
  const desktop=location.pathname==='/'||location.pathname.endsWith('/index.html');let seen=false;try{seen=sessionStorage.getItem('u1-boot-seen')==='true';if(desktop)sessionStorage.setItem('u1-boot-seen','true');}catch(_){}
  if(desktop&&settings.boot&&!seen)showBoot();
}
document.addEventListener('change',async event=>{const key=event.target.dataset?.u1Setting;if(!key)return;settings[key]=key==='volume'?Math.max(0,Math.min(100,Number(event.target.value))):event.target.checked;preferences();if(key==='volume'){const output=event.target.closest('label')?.querySelector('output');if(output)output.textContent=`${settings.volume}%`;}if(settings.sounds)await unlock();});
document.addEventListener('click',async event=>{if(event.target.closest('[data-u1-test-sound]')){await unlock();chime(false,true);}if(event.target.closest('[data-u1-replay-boot]'))showBoot();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
window.addEventListener('pagehide',()=>{observer?.disconnect();clearInterval(bootPoll);if(audio)audio.close().catch(()=>{});});
