import {icon,mark} from './u1-icons.js';
import {escape as esc} from './prism-ui.js';
import {parseMediaLink,playbackTime,playbackFraction} from './u1-media-core.mjs';

const sources = [
  {id:'spotify',name:'Spotify',color:'#4bef9d',url:'https://open.spotify.com/',copy:'Tracks, albums and playlists',shape:'<circle cx="24" cy="24" r="19" fill="currentColor"/><g fill="none" stroke="#04150e" stroke-width="3" stroke-linecap="round"><path d="M12 19q13-6 25 1M14 25q11-5 21 1M16 31q9-4 17 0"/></g>'},
  {id:'youtube',name:'YouTube Music',color:'#ff5e7e',url:'https://music.youtube.com/',copy:'Music and video in view',shape:'<circle cx="24" cy="24" r="19" fill="currentColor"/><circle cx="24" cy="24" r="13" fill="none" stroke="#fff" stroke-width="1.4"/><path d="m20 16 13 8-13 8z" fill="#fff"/>'},
  {id:'soundcloud',name:'SoundCloud',color:'#ffab67',url:'https://soundcloud.com/',copy:'Tracks and creator playlists',shape:'<path d="M23 33V17a10 10 0 0 1 18 6 5 5 0 0 1 0 10Z" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 19v14M13 23v10M8 25v8M3 28v4"/></g>'},
  {id:'stremio',name:'Stremio',color:'#b7a2ff',url:'https://web.stremio.com/',copy:'Open your Stremio library',shape:'<path d="M24 3 44 24 24 45 4 24Z" fill="currentColor"/><path d="m20 15 14 9-14 9Z" fill="#fff"/>'},
];
const logo = id => {const source=sources.find(s=>s.id===id);return source?`<svg viewBox="0 0 48 48" class="u1-source-logo" style="color:${source.color}" aria-hidden="true">${source.shape}</svg>`:icon('media');};
const sourceName = id => sources.find(s=>s.id===id)?.name || (id==='local'?'Local file':'Direct media');
const scripts = new Map();
let drawer, mini, mount, statusNode, formNode, current=null, controller=null, disposer=null, poll=null, objectUrl=null, generation=0;
let state={playing:false,title:'Nothing playing',artist:'',position:0,duration:0};
let pageObserver;

function loadSdk(name,url,ready) {
  if (ready()) return Promise.resolve(ready());
  if (scripts.has(name)) return scripts.get(name);
  const promise=new Promise((resolve,reject)=>{
    const script=document.createElement('script'); script.src=url; script.async=true;
    const interval=setInterval(()=>{const api=ready();if(api){clearInterval(interval);clearTimeout(timeout);resolve(api);}},100);
    const fail=()=>{clearInterval(interval);clearTimeout(timeout);script.remove();scripts.delete(name);reject(new Error(`${name} could not load. Check your connection or content blocker.`));};
    const timeout=setTimeout(fail,14000);script.onerror=fail;document.head.append(script);
  });
  scripts.set(name,promise);return promise;
}

function setText(element,value) {if(element && element.textContent!==String(value)) element.textContent=String(value);}
function message(text,error=false) {setText(statusNode,text);statusNode.classList.toggle('is-error',error);}
function sync(next={}) {
  Object.assign(state,next);
  if (!mini) return;
  mini.hidden=!state.playing;
  setText(mini.querySelector('[data-media-title]'),state.title);
  setText(mini.querySelector('[data-media-subtitle]'),`${sourceName(current?.provider)}${state.artist?' / '+state.artist:''}`);
  setText(mini.querySelector('[data-media-time]'),`${playbackTime(state.position)} / ${state.duration?playbackTime(state.duration):'--:--'}`);
  mini.querySelector('progress').value=playbackFraction(state.position,state.duration);
  setText(drawer.querySelector('[data-player-state]'),state.playing?'PLAYING':current?'READY / PAUSED':'NO ACTIVE SOURCE');
  drawer.classList.toggle('is-playing',state.playing);
  const pageState=document.querySelector('#u1-media-page-status');
  setText(pageState,state.playing?`${sourceName(current?.provider)} / ${state.title}`:'No active playback. Choose a source or a local file.');
  if (current && ['local','direct'].includes(current.provider) && 'mediaSession' in navigator) {
    try {navigator.mediaSession.playbackState=state.playing?'playing':'paused';} catch {}
  }
}

function stop() {
  generation++; clearInterval(poll);poll=null;
  try {disposer?.();} catch {} disposer=null; controller=null;
  mount?.replaceChildren();
  if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null;}
  current=null;state={playing:false,title:'Nothing playing',artist:'',position:0,duration:0};sync();
  if('mediaSession' in navigator) {try{navigator.mediaSession.playbackState='none';navigator.mediaSession.metadata=null;['play','pause','seekto'].forEach(a=>navigator.mediaSession.setActionHandler(a,null));}catch{}}
}

function show() {drawer.hidden=false;drawer.querySelector('input[type="url"]')?.focus();}
function close() {
  // Video must never be hidden while continuing to play.
  if(current?.provider==='youtube'||current?.video) {try{controller?.pause?.();}catch{}sync({playing:false});}
  drawer.hidden=true;
}

function nativeMedia(item,file) {
  const media=document.createElement(item.video?'video':'audio');
  media.controls=true;media.preload='metadata';media.setAttribute('playsinline','');
  media.setAttribute('aria-label',item.title);media.src=file?(objectUrl=URL.createObjectURL(file)):item.url;
  mount.append(media);controller={pause:()=>media.pause(),play:()=>media.play()};
  const alive=()=>current===item;
  media.addEventListener('playing',()=>{if(alive()){sync({playing:true});message('Playing your selected media.');}});
  media.addEventListener('pause',()=>{if(alive())sync({playing:false});});
  media.addEventListener('ended',()=>{if(alive()){sync({playing:false});message('Playback finished.');}});
  media.addEventListener('timeupdate',()=>{if(alive())sync({position:media.currentTime,duration:media.duration});});
  media.addEventListener('loadedmetadata',()=>{if(alive()){sync({duration:media.duration});message('Ready. Use the player controls to start.');}});
  media.addEventListener('error',()=>{if(alive()){sync({playing:false});message('This file could not play. Its format, permissions or network source may not be supported by this browser.',true);}});
  disposer=()=>{media.pause();media.removeAttribute('src');media.load();};
  if('mediaSession' in navigator) {try{navigator.mediaSession.metadata=new MediaMetadata({title:item.title,artist:sourceName(item.provider)});navigator.mediaSession.setActionHandler('play',()=>media.play().catch(()=>{}));navigator.mediaSession.setActionHandler('pause',()=>media.pause());navigator.mediaSession.setActionHandler('seekto',e=>{if(Number.isFinite(e.seekTime))media.currentTime=e.seekTime;});}catch{}}
}

async function playItem(item,file) {
  stop();const version=generation;current=item;state.title=item.title;sync();show();
  drawer.dataset.provider=item.provider;
  mini.querySelector('[data-media-logo]').innerHTML=logo(item.provider);
  message(`Loading ${sourceName(item.provider)}...`);
  if(item.provider==='stremio') {
    mount.innerHTML=`<div class="u1-media-empty">${logo('stremio')}<h3>Your Stremio library</h3><p>Stremio opens in its own app. Its playback status is not connected to U1 OS, so it will not appear as a playing track here.</p><a href="https://web.stremio.com/" target="_blank" rel="noopener noreferrer">Open Stremio ${icon('external')}</a></div>`;
    message('External launcher only. No account or playback connection is claimed.');return;
  }
  if(['local','direct'].includes(item.provider)){nativeMedia(item,file);return;}
  const alive=()=>version===generation;
  try {
    if(item.provider==='spotify') {
      const previous=window.onSpotifyIframeApiReady;
      if(!window.__u1SpotifyReadyInstalled){window.__u1SpotifyReadyInstalled=true;window.onSpotifyIframeApiReady=api=>{window.__u1SpotifyApi=api;previous?.(api);};}
      const api=await loadSdk('Spotify','https://open.spotify.com/embed/iframe-api/v1',()=>window.__u1SpotifyApi);
      if(!alive())return;
      const target=document.createElement('div');mount.append(target);
      api.createController(target,{uri:item.uri,width:'100%',height:352},embed=>{
        if(!alive()){embed.destroy();return;}
        controller={pause:()=>embed.pause(),play:()=>embed.play()};disposer=()=>embed.destroy();
        embed.addListener('ready',()=>{if(alive())message('Ready. Press play in Spotify. Availability depends on Spotify and your session.');});
        embed.addListener('playback_update',event=>{if(alive()){const d=event.data;sync({playing:!d.isPaused&&!d.isBuffering,position:d.position/1000,duration:d.duration/1000,title:d.playingURI?`Spotify / ${d.playingURI.split(':').at(-1)}`:item.title});}});
      });
    } else if(item.provider==='soundcloud') {
      const api=await loadSdk('SoundCloud','https://w.soundcloud.com/player/api.js',()=>window.SC?.Widget);
      if(!alive())return;
      const iframe=document.createElement('iframe');iframe.title='SoundCloud player';iframe.allow='autoplay';iframe.height='300';
      iframe.src=`https://w.soundcloud.com/player/?url=${encodeURIComponent(item.url)}&auto_play=false&visual=true&color=%2351dfff`;
      mount.append(iframe);const widget=api(iframe);controller={play:()=>widget.play(),pause:()=>widget.pause()};
      const metadata=()=>widget.getCurrentSound(sound=>{if(alive()&&sound)sync({title:sound.title||item.title,artist:sound.user?.username||'',duration:(sound.duration||0)/1000});});
      widget.bind(api.Events.READY,()=>{if(alive()){metadata();message('Ready. Use the SoundCloud player to start.');}});
      widget.bind(api.Events.PLAY,()=>{if(alive()){metadata();sync({playing:true});}});
      widget.bind(api.Events.PAUSE,()=>{if(alive())sync({playing:false});});
      widget.bind(api.Events.FINISH,()=>{if(alive())sync({playing:false});});
      widget.bind(api.Events.PLAY_PROGRESS,event=>{if(alive())sync({position:event.currentPosition/1000});});
      if(api.Events.ERROR)widget.bind(api.Events.ERROR,()=>{if(alive()){sync({playing:false});message('SoundCloud could not play this track. Check availability in SoundCloud.',true);}});
      disposer=()=>{widget.pause();Object.values(api.Events).forEach(event=>widget.unbind(event));};
    } else {
      const api=await loadSdk('YouTube','https://www.youtube.com/iframe_api',()=>window.YT?.Player&&window.YT);
      if(!alive())return;
      const target=document.createElement('div');mount.append(target);
      const player=new api.Player(target,{width:'100%',height:260,videoId:item.id,playerVars:{playsinline:1,origin:location.origin,autoplay:0},events:{
        onReady:()=>{if(alive())message('Ready. Use the visible YouTube player to start.');},
        onStateChange:event=>{if(alive()){const info=player.getVideoData?.()||{};sync({playing:event.data===1,title:info.title||item.title,artist:info.author||'',position:player.getCurrentTime(),duration:player.getDuration()});}},
        onError:event=>{if(alive()){sync({playing:false});message(`YouTube could not play this item (code ${event.data}). It may require sign-in or prohibit embedding. Open it on YouTube instead.`,true);}},
      }});
      controller={pause:()=>player.pauseVideo(),play:()=>player.playVideo()};disposer=()=>player.destroy();
      poll=setInterval(()=>{if(alive()&&state.playing)sync({position:player.getCurrentTime(),duration:player.getDuration()});},1000);
    }
    if(alive()) {
      const link=document.createElement('a');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';link.className='u1-media-provider-link';link.textContent=`Open in ${sourceName(item.provider)}`;mount.append(link);
    }
  } catch(error) {if(alive()){sync({playing:false});message(error.message,true);}}
}

function sourceCards() {return sources.map(source=>`<article class="u1-source-card" style="--source:${source.color}"><span class="u1-source-emblem">${logo(source.id)}</span><h3>${source.name}</h3><p>${source.copy}</p><small>${source.id==='stremio'?'External app / no playback telemetry':'Official embedded player'}</small><div><button type="button" data-u1-source="${source.id}">${source.id==='stremio'?'View launcher':'Load a link'} ${icon('arrow')}</button><a href="${source.url}" target="_blank" rel="noopener noreferrer" aria-label="Open ${source.name}">${icon('external')}</a></div></article>`).join('');}

function mountPage() {
  const page=document.querySelector('#prism-page.prism-view-media');if(!page||page.querySelector('#u1-media-zone'))return;
  const zone=document.createElement('section');zone.id='u1-media-zone';zone.setAttribute('aria-label','Music and video');
  zone.innerHTML=`<div class="u1-media-hero"><div><span class="u1-overline">U1 OS / MEDIA CONTROL</span><h2>Your sound.<br><em>Your atmosphere.</em></h2><p>One player for the music and video you choose.<br>Nothing pretends to be playing.</p><div class="u1-media-actions"><button type="button" data-u1-player-open>${icon('media')} Open player</button><button type="button" data-u1-local-file>${icon('files')} Choose local media</button></div></div><div class="u1-media-sculpture" aria-hidden="true"><i></i><i></i><i></i>${icon('media')}</div></div><div class="u1-media-live-status"><span></span><p id="u1-media-page-status">No active playback. Choose a source or a local file.</p><small>REAL PLAYBACK EVENTS</small></div><div class="u1-source-grid">${sourceCards()}</div><p class="u1-media-disclosure">Now playing follows media started inside this U1 OS tab. Other tabs, desktop apps and devices are not monitored. Provider sign-in, subscriptions and regional restrictions still apply. Loading a provider link contacts that provider; local files stay on your Mac.</p>`;
  const header=page.querySelector('.prism-page-header');if(header)header.after(zone);else page.prepend(zone);sync();
}

function init() {
  for(const [id,href] of [['u1-unified-style','/css/u1-unified.css'],['u1-media-style','/css/u1-media.css']]) {if(document.getElementById(id))continue;const link=document.createElement('link');link.id=id;link.rel='stylesheet';link.href=href;document.head.append(link);}
  const studioMark=document.querySelector('.studio-brand .brand-orbit');if(studioMark)studioMark.innerHTML=mark();
  if(new URLSearchParams(location.search).has('u1-frame'))return;
  drawer=document.createElement('section');drawer.id='u1-player';drawer.hidden=true;drawer.setAttribute('aria-label','U1 music and video player');
  drawer.innerHTML=`<header><div>${icon('media')}<strong>U1 Player</strong><small data-player-state>NO ACTIVE SOURCE</small></div><button type="button" data-u1-player-close aria-label="Close player; pause video">${icon('close')}</button></header><form id="u1-media-form"><label for="u1-media-url">Spotify, YouTube Music, SoundCloud or media link</label><div><input id="u1-media-url" type="url" placeholder="https://..." required autocomplete="off"><button type="submit">Load</button></div></form><div id="u1-player-mount"><div class="u1-media-empty">${mark()}<h3>A little atmosphere.</h3><p>Choose a link or a local audio/video file. Playback starts only when you press play.</p></div></div><p id="u1-player-status" role="status">No source loaded.</p><footer><button type="button" data-u1-local-file>${icon('files')} Local file</button><button type="button" data-u1-player-stop>${icon('close')} Stop & clear</button><span>Only actual playback appears in Now playing.</span></footer>`;
  mini=document.createElement('aside');mini.id='u1-now-playing';mini.hidden=true;mini.setAttribute('aria-label','Now playing');
  mini.innerHTML=`<button type="button" class="u1-now-open" data-u1-player-open aria-label="Open current player"><span data-media-logo>${icon('media')}</span><span><small>NOW PLAYING</small><strong data-media-title>Nothing playing</strong><span data-media-subtitle></span></span></button><button type="button" data-u1-player-pause aria-label="Pause playback"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14M16 5v14" stroke="currentColor" stroke-width="3"/></svg></button><progress max="100" value="0" aria-label="Playback progress"></progress><small data-media-time>0:00 / --:--</small>`;
  const fileInput=document.createElement('input');fileInput.type='file';fileInput.accept='audio/*,video/*';fileInput.hidden=true;fileInput.id='u1-local-media';
  fileInput.addEventListener('change',()=>{const file=fileInput.files?.[0];if(!file)return;if(!/^(audio|video)\//.test(file.type)&&!(/\.(mp4|webm|mov|m4v|mp3|m4a|ogg|oga|opus|wav|flac)$/i.test(file.name))){show();message('Choose a supported audio or video file.',true);return;}playItem({provider:'local',title:file.name,video:file.type.startsWith('video/')||/\.(mp4|webm|mov|m4v)$/i.test(file.name)},file);fileInput.value='';});
  document.body.append(drawer,mini,fileInput);mount=drawer.querySelector('#u1-player-mount');statusNode=drawer.querySelector('#u1-player-status');formNode=drawer.querySelector('form');
  formNode.addEventListener('submit',event=>{event.preventDefault();try{playItem(parseMediaLink(formNode.elements['u1-media-url'].value));}catch(error){message(error.message,true);}});
  document.addEventListener('click',event=>{
    if(event.target.closest('[data-u1-player-open]'))show();
    if(event.target.closest('[data-u1-player-close]'))close();
    if(event.target.closest('[data-u1-player-stop]')){stop();message('Playback cleared.');}
    if(event.target.closest('[data-u1-player-pause]')){controller?.pause?.();sync({playing:false});}
    if(event.target.closest('[data-u1-local-file]'))fileInput.click();
    const source=event.target.closest('[data-u1-source]')?.dataset.u1Source;
    if(source==='stremio')playItem({provider:'stremio',title:'Stremio',url:'https://web.stremio.com/'});
    else if(source){show();formNode.querySelector('input').placeholder=sources.find(s=>s.id===source).url;message(`Paste the ${sourceName(source)} track or video link you want to play.`);}
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!drawer.hidden)close();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&current?.provider==='youtube'){controller?.pause?.();sync({playing:false});}});
  const page=document.querySelector('#prism-page');if(page){pageObserver=new MutationObserver(mountPage);pageObserver.observe(page,{childList:true});}mountPage();
  window.addEventListener('pagehide',()=>{stop();pageObserver?.disconnect();},{once:true});
}
// Wait until the desktop module has installed its shell and base styles.
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(init),{once:true});else requestAnimationFrame(init);
