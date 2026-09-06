(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const header=$('topBezel');if(!header)return;
  const safeURL=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:'#';}catch(_){return '#';}};
  const stamp=value=>value?new Date(value*1000).toLocaleString():'Not received';
  const sports=['afl','cricket','mma','boxing'];
  const state={}, quotes={}, busy=new Set(), lastAttempt={}, attention=new Set();
  let socket=null,retryTimer,retryDelay=2000,lastSocketMessage=0,activePane='warnings',pulseTimer,renderTimer;
  let pulseEnabled=true;try{pulseEnabled=localStorage.getItem('u1-live-pulse')!=='off';JSON.parse(sessionStorage.getItem('u1-live-seen')||'[]').forEach(id=>attention.add(id));}catch(_){}
  const bar=document.createElement('div');bar.className='u1-live-bar';bar.setAttribute('aria-label','Live information bar');
  const chip=(id,label,tone)=>`<button class="live-chip" data-live-pane="${id}" style="--live-tone:${tone}"><span class="live-chip-label">${label}</span><strong id="live-${id}">Connecting...</strong></button>`;
  bar.innerHTML=`<span class="live-bar-brand"><i></i> FEEDS</span><div class="live-bar-track" tabindex="0" aria-label="Scroll for more feeds">${chip('weather','WEATHER','#ffd28c')}${sports.map(s=>chip(s,s.toUpperCase(),'#ade7a3')).join('')}${chip('crypto','BTC / ETH / SOL','#8cd6f9')}${chip('markets','MARKET CLOCKS','#baaef6')}</div><button id="liveWarningsButton" class="live-warning-button" data-live-pane="warnings"><span aria-hidden="true">!</span><b id="liveWarningCount">Checking</b></button><button class="live-options-button" data-live-pane="settings" aria-label="Live bar settings">Settings</button>`;
  header.after(bar);document.body.classList.add('has-live-bar');
  const dialog=document.createElement('dialog');dialog.id='liveBarDialog';dialog.className='live-dialog';dialog.setAttribute('aria-labelledby','liveDialogTitle');
  dialog.innerHTML='<div class="live-dialog-heading"><div><small>U1 OS / LIVE INFORMATION</small><h2 id="liveDialogTitle">Feed details</h2></div><button id="liveDialogClose" class="feature-button" autofocus>Close</button></div><div id="liveDialogBody"></div>';
  document.body.append(dialog);$('liveDialogClose').onclick=()=>dialog.close();
  bar.onclick=event=>{const button=event.target.closest('[data-live-pane]');if(!button)return;activePane=button.dataset.livePane;renderPane();if(!dialog.open)dialog.showModal();};
  const sr=document.createElement('div');sr.className='live-sr';sr.setAttribute('role','status');sr.setAttribute('aria-live','polite');document.body.append(sr);

  const definitions={weather:{seconds:600,path:()=>{let city='Melbourne';try{city=localStorage.getItem('u1-weather-city')||city;}catch(_){}return 'weather?city='+encodeURIComponent(city);}},markets:{seconds:30,path:()=> 'live/markets'},warnings:{seconds:120,path:()=> 'live/warnings'},crypto:{seconds:30,path:()=> 'live/crypto'},notices:{seconds:60,path:()=> 'notifications'}};
  sports.forEach(s=>definitions[s]={seconds:45,path:()=> 'sports?sport='+s});
  async function refresh(key,force=false){
    if(busy.has(key)||document.hidden)return;
    if(!force&&Date.now()-(lastAttempt[key]||0)<definitions[key].seconds*1000)return;
    if(key==='crypto'&&socket?.readyState===WebSocket.OPEN&&Object.values(quotes).filter(q=>Date.now()-q.received<90000).length===3)return;
    busy.add(key);lastAttempt[key]=Date.now();
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),22000);
    try{
      const response=await fetch('/api/workspace/'+definitions[key].path(),{cache:'no-store',signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||'Feed unavailable');
      state[key]={data,failed:!data.success||!!data.stale,received:Date.now(),error:data.error};
    }catch(_){state[key]={...(state[key]||{}),failed:true,error:'Feed unavailable. Check the provider or restart the updated backend.'};}
    finally{clearTimeout(timer);busy.delete(key);scheduleRender();}
  }
  function tickFeeds(){Object.keys(definitions).forEach(key=>refresh(key));}
  function fresh(key){return !!state[key]?.data&&!state[key].failed&&Date.now()-state[key].received<Math.max(definitions[key].seconds*2000,120000);}
  function quoteRows(){
    const fallback=fresh('crypto')?state.crypto.data.quotes:[];
    return ['BTC','ETH','SOL'].map(symbol=>{
      const q=quotes[symbol];
      const streaming=!!q&&socket?.readyState===WebSocket.OPEN&&Date.now()-q.received<90000&&Date.now()-lastSocketMessage<40000;
      if(streaming)return {...q,live:true};
      const snapshot=fallback?.find(item=>item.symbol===symbol);
      return snapshot?{...snapshot,live:false,received:state.crypto.data.fetched_at*1000}:q?{...q,live:false,stale:true}:{symbol,price:null};
    });
  }
  function money(value){return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(value);}
  function connectQuotes(){
    if(document.hidden||socket&&(socket.readyState===0||socket.readyState===1))return;
    try{socket=new WebSocket('wss://ws.kraken.com/v2');}catch(_){queueReconnect();return;}
    const connection=socket;
    connection.onopen=()=>{lastSocketMessage=Date.now();connection.send(JSON.stringify({method:'subscribe',params:{channel:'ticker',symbol:['BTC/USD','ETH/USD','SOL/USD'],snapshot:true},req_id:1}));};
    connection.onmessage=event=>{
      lastSocketMessage=Date.now();
      try{
        const data=JSON.parse(event.data);
        if(data.method==='subscribe'&&data.success===false){connection.close();return;}
        if(data.channel!=='ticker')return;
        for(const item of data.data||[]){
          const symbol=String(item.symbol||'').split('/')[0];
          if(!['BTC','ETH','SOL'].includes(symbol)||!Number.isFinite(item.last)||item.last<=0)continue;
          const sourceTime=Date.parse(item.timestamp);
          quotes[symbol]={symbol,price:item.last,change_pct:Number.isFinite(item.change_pct)?item.change_pct:null,received:Date.now(),source_at:Number.isFinite(sourceTime)?sourceTime:null};
        }
        retryDelay=2000;scheduleRender();
      }catch(_){}
    };
    connection.onerror=()=>connection.close();
    connection.onclose=()=>{if(socket===connection)socket=null;queueReconnect();scheduleRender();};
  }
  function queueReconnect(){clearTimeout(retryTimer);if(document.hidden)return;retryTimer=setTimeout(connectQuotes,retryDelay);retryDelay=Math.min(60000,retryDelay*2);}
  function scheduleRender(){if(!renderTimer)renderTimer=setTimeout(()=>{renderTimer=null;render();if(dialog.open&&activePane!=='settings')renderPane();},700);}
  function countdown(at){const sec=Math.max(0,Math.ceil(at-Date.now()/1000));return sec>=86400?`${Math.floor(sec/86400)}d ${Math.floor(sec%86400/3600)}h`:sec>=3600?`${Math.floor(sec/3600)}h ${Math.floor(sec%3600/60)}m`:`${Math.floor(sec/60)}m ${sec%60}s`;}
  function alerts(){
    const list=[];
    if(fresh('warnings'))for(const warning of state.warnings.data.items||[])list.push({...warning,id:'bom:'+warning.id,source:'BOM / Victoria',level:warning.major?'major':'warning'});
    for(const q of quoteRows())if(q.live&&Math.abs(q.change_pct||0)>=10)list.push({id:'move:'+q.symbol+':'+Math.sign(q.change_pct)+':'+new Date().toISOString().slice(0,10),title:`${q.symbol} ${q.change_pct>0?'+':''}${q.change_pct.toFixed(2)}% over 24 hours`,level:'major',source:'Kraken / 10% attention threshold',url:'https://www.kraken.com/prices'});
    if(fresh('notices'))for(const note of state.notices.data.notifications||[])if(note.threshold>=90&&Date.now()/1000-note.created_at<86400&&(!note.resets_at||note.resets_at>Date.now()/1000))list.push({id:'usage:'+note.id,title:note.title,source:'U1 usage monitor',level:note.threshold>=100?'major':'warning',url:null});
    if(fresh('markets'))for(const market of state.markets.data.markets||[]){const seconds=market.next_at-Date.now()/1000;if(market.next_at&&seconds>0&&seconds<=900)list.push({id:'session:'+market.name+':'+market.next_at,title:`${market.name} scheduled ${market.next_event} in ${countdown(market.next_at)}`,source:'Exchange calendar / not a halt monitor',level:'notice',url:market.source_url});}
    for(const key of Object.keys(definitions))if(state[key]?.failed&&!(key==='crypto'&&quoteRows().every(q=>q.live)))list.push({id:'feed:'+key,title:key==='warnings'?'Official warning feed unavailable. Check BOM directly.':key.toUpperCase()+' feed unavailable',source:'Connection status',level:'unavailable',url:key==='warnings'?'https://www.bom.gov.au/vic/warnings.shtml':null});
    return list.sort((a,b)=>({major:0,warning:1,unavailable:2,notice:3}[a.level]-{major:0,warning:1,unavailable:2,notice:3}[b.level]));
  }
  function render(){
    window.dispatchEvent(new CustomEvent('u1-live-prices',{detail:quoteRows()}));
    if(fresh('weather')&&state.weather.data.current){const d=state.weather.data;$('live-weather').textContent=`${d.city} ${Math.round(d.current.temperature_2m)} C`;}else $('live-weather').textContent=state.weather?'Unavailable':'Connecting...';
    for(const sport of sports){
      const node=$('live-'+sport);if(!fresh(sport)){node.textContent=state[sport]?'Unavailable':'Connecting...';continue;}
      const events=state[sport].data.events||[],event=events.find(e=>e.state==='in')||events[0];
      node.textContent=event?`${event.state==='in'?'LIVE':event.state==='post'?'FINAL':'NEXT'} / ${(event.competitors||[]).map(t=>t.name+(t.score!=null?' '+t.score:'')).join(' - ')||event.name}`:'No events in feed';
    }
    $('live-crypto').textContent=quoteRows().map(q=>q.price?`${q.symbol} ${money(q.price)}${q.stale?' STALE':q.live?'':' SNAPSHOT'}`:`${q.symbol} --`).join(' / ');
    $('live-markets').textContent=fresh('markets')?state.markets.data.markets.map(m=>`${m.name} ${m.state==='scheduled_open'?'OPEN (sched.)':m.state==='scheduled_closed'?'CLOSED (sched.)':'UNKNOWN'}${m.next_at?' / '+m.next_event+' '+countdown(m.next_at):''}`).join(' | '):'Schedule unavailable';
    const items=alerts(),major=items.filter(item=>item.level==='major');
    $('liveWarningCount').textContent=items.length?`${items.length} alerts`:fresh('warnings')?'No feed alerts':'Checking';
    $('liveWarningsButton').classList.toggle('has-major',major.length>0);
    const unseen=major.filter(item=>!attention.has(item.id));
    if(unseen.length){
      unseen.forEach(item=>attention.add(item.id));
      try{sessionStorage.setItem('u1-live-seen',JSON.stringify([...attention].slice(-200)));}catch(_){}
      sr.textContent='Attention: '+unseen.map(item=>item.title).join('. ');
      if(pulseEnabled){bar.classList.remove('attention-pulse');requestAnimationFrame(()=>bar.classList.add('attention-pulse'));clearTimeout(pulseTimer);pulseTimer=setTimeout(()=>bar.classList.remove('attention-pulse'),6000);}
    }
  }
  function statusLine(key){const entry=state[key],data=entry?.data;return `<p class="live-feed-note">${entry?.failed?'UNAVAILABLE / ':''}${esc(data?.source||key.toUpperCase())} / Last successful response: ${esc(stamp(data?.fetched_at||(!entry?.failed?data?.checked_at:null)))}. Public feeds may be delayed.</p>`;}
  function renderPane(){
    const body=$('liveDialogBody');$('liveDialogTitle').textContent=({crypto:'Crypto prices',markets:'Trading session clocks',warnings:'Warnings and attention',weather:'Weather',settings:'Live bar settings'}[activePane]||activePane.toUpperCase()+' scores');
    if(activePane==='settings'){
      let city='Melbourne';try{city=localStorage.getItem('u1-weather-city')||city;}catch(_){}
      body.innerHTML=`<form id="liveSettingsForm" class="live-settings"><label>Weather city<input id="liveCityInput" maxlength="100" value="${esc(city)}"></label><label class="live-check"><input type="checkbox" id="livePulseToggle" ${pulseEnabled?'checked':''}> Briefly pulse for new major alerts</label><button class="feature-button primary">Save preferences</button></form><p class="live-feed-note">Prices: Kraken WebSocket, with 30-second REST fallback. Sports: 45-second refresh. Weather and Victoria warnings: cached for 10 minutes. Market clocks: published 2026 schedules, refreshed every 30 seconds. Polling pauses while this tab is hidden.</p><p class="live-feed-note">Major attention flags: severe-warning headline matches, a 10% crypto move over 24 hours, or a recorded 100% usage threshold. No fast strobing, sounds, trades, or push notifications. System reduced-motion preferences take priority.</p><p class="live-feed-note">Warnings cover Victoria regardless of your weather-city selection. This is not an emergency-alert service or an exchange halt feed.</p>`;
      $('liveSettingsForm').onsubmit=event=>{event.preventDefault();pulseEnabled=$('livePulseToggle').checked;try{localStorage.setItem('u1-live-pulse',pulseEnabled?'on':'off');localStorage.setItem('u1-weather-city',$('liveCityInput').value.trim()||'Melbourne');}catch(_){}if(!pulseEnabled)bar.classList.remove('attention-pulse');refresh('weather',true);dialog.close();};return;
    }
    if(activePane==='warnings'){
      body.innerHTML=`<p class="live-feed-note">BOM warnings are state-wide for Victoria. Attention flags based on headlines are not official severity ratings. Do not rely on this dashboard as your only warning source.</p>${alerts().map(item=>`<article class="live-alert ${item.level}"><span>${esc(item.level.toUpperCase())} / ${esc(item.source)}</span><h3>${esc(item.title)}</h3>${item.url?`<a href="${esc(safeURL(item.url))}" target="_blank" rel="noopener noreferrer">Open original source</a>`:''}</article>`).join('')||'<p class="live-feed-note">No alerts returned by the currently available feeds. This is not an all-clear.</p>'}${statusLine('warnings')}<a class="feature-button" href="https://www.bom.gov.au/vic/warnings.shtml" target="_blank" rel="noopener noreferrer">Bureau of Meteorology warnings</a>`;return;
    }
    if(activePane==='crypto'){
      body.innerHTML=`<div class="live-detail-grid">${quoteRows().map(q=>`<article class="live-detail-card"><span>${q.symbol} / USD</span><h3>${q.price?money(q.price):'Unavailable'}</h3><p>${q.change_pct!=null&&q.live?(q.change_pct>0?'+':'')+q.change_pct.toFixed(2)+'% / 24h':'24-hour change unavailable'}</p><small>${q.stale?'STALE':q.live?'LIVE SOCKET':'SNAPSHOT'} / received ${q.received?new Date(q.received).toLocaleTimeString():'never'}</small></article>`).join('')}</div><p class="live-feed-note">Prices are Kraken market data, not an execution guarantee or consolidated market price. A public data connection does not sign you into an exchange or enable trading.</p><a href="https://www.kraken.com/prices" target="_blank" rel="noopener noreferrer">Source: Kraken</a>`;return;
    }
    if(activePane==='markets'){
      body.innerHTML=(fresh('markets')?state.markets.data.markets.map(m=>`<article class="live-detail-card"><span>${m.name} / ${esc(m.timezone)}</span><h3>${m.state==='scheduled_open'?'Scheduled open':m.state==='scheduled_closed'?'Scheduled closed':'Calendar unavailable'}</h3><p>${m.next_at?`Next ${m.next_event}: ${esc(stamp(m.next_at))} (${countdown(m.next_at)})`:'Check exchange calendar'}${m.early_close?' / early-close session':''}</p><small>${esc(m.notice)}</small><p><a href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">Official exchange calendar</a></p></article>`).join(''):'<p class="live-feed-note">Calendar unavailable. Restart the backend if it has not loaded the new routes.</p>')+'<p class="live-feed-note">Times above are displayed in your device timezone. These are ASX cash and NYSE core sessions only, not futures, forex, Nasdaq, or market-halt monitoring. Calendar snapshot: 6 September 2026.</p>';return;
    }
    if(activePane==='weather'){
      const data=fresh('weather')?state.weather.data:null,c=data?.current;
      body.innerHTML=c?`<article class="live-detail-card"><span>${esc(data.city)} / ${esc(data.region)}</span><h3>${Math.round(c.temperature_2m)} degrees C</h3><p>Feels like ${Math.round(c.apparent_temperature)} C / Wind ${c.wind_speed_10m} km/h / Humidity ${c.relative_humidity_2m}%</p><small>Observation time: ${esc(c.time)} / ${esc(data.timezone)}</small></article>${statusLine('weather')}<a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Weather data by Open-Meteo</a>`:'<p class="live-feed-note">Weather unavailable. The last value is not presented as live.</p>';return;
    }
    if(sports.includes(activePane)){
      const data=state[activePane]?.data;
      body.innerHTML=(fresh(activePane)?(data.events||[]).slice(0,24).map(event=>`<article class="live-detail-card"><span>${event.state==='in'?'LIVE':event.state==='post'?'FINAL':'SCHEDULED'} / ${esc(event.status)}</span><h3>${esc(event.name)}</h3>${(event.competitors||[]).map(team=>`<p class="live-team"><b>${esc(team.name)}</b><strong>${esc(team.score??'--')}</strong></p>`).join('')}<small>${esc(event.date||'')} / ${esc(event.venue||'')}</small></article>`).join('')||'<p class="live-feed-note">No events returned. This does not guarantee complete coverage.</p>':'<p class="live-feed-note">Live coverage is currently unavailable from this provider.</p>')+statusLine(activePane)+(data?.source_url?`<a href="${esc(safeURL(data.source_url))}" target="_blank" rel="noopener noreferrer">Open source coverage</a>`:'');
    }
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(retryTimer);if(socket)socket.close();}else{connectQuotes();tickFeeds();scheduleRender();}});
  window.addEventListener('pagehide',()=>{clearTimeout(retryTimer);if(socket)socket.close();});
  setInterval(()=>{if(document.hidden)return;if(socket?.readyState===WebSocket.OPEN&&Date.now()-lastSocketMessage>40000)socket.close();tickFeeds();render();},5000);
  connectQuotes();tickFeeds();render();
})();
