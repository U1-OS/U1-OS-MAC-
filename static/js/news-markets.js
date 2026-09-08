(() => {
  'use strict';
  const $=id=>document.getElementById(id),esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  if(!$('desktop-news')||!$('desktop-stocks'))return;
  let category='australia',symbols='BHP.AX,CBA.AX,AAPL,MSFT,NVDA,SPY',newsData=null,stockData=null,view='news',newsError='',stockError='',newsAt=0,stocksAt=0;
  const busy=new Set();
  try{const saved=JSON.parse(localStorage.getItem('u1-news-market-preferences')||'{}');if(['australia','world','business','technology'].includes(saved.category))category=saved.category;if(typeof saved.symbols==='string'&&saved.symbols.length<=200)symbols=saved.symbols;}catch(_){}
  const fmtTime=value=>Number.isFinite(value)?new Date(value*1000).toLocaleString():'Timestamp unavailable';
  const safeURL=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:'#';}catch(_){return '#';}};
  function save(){try{localStorage.setItem('u1-news-market-preferences',JSON.stringify({category,symbols}));}catch(_){}}
  function price(quote){if(!Number.isFinite(quote.price))return '--';if(/^[A-Z]{3}$/.test(quote.currency||''))return new Intl.NumberFormat(undefined,{style:'currency',currency:quote.currency,maximumFractionDigits:2}).format(quote.price);return quote.price.toFixed(2)+' '+(quote.currency||'');}
  const track=document.querySelector('.live-bar-track');
  if(track){
    for(const [id,title,colour] of [['news','NEWS','#ffc394'],['stocks','SHARES','#9ee8b7']]){
      const button=document.createElement('button');button.className='live-chip';button.style.setProperty('--live-tone',colour);button.dataset.marketLens=id;button.innerHTML=`<span class="live-chip-label">${title}</span><strong id="lensBar-${id}">Connecting...</strong>`;track.append(button);button.onclick=()=>open(id);
    }
  }
  const dialog=document.createElement('dialog');dialog.className='live-dialog news-market-dialog';dialog.setAttribute('aria-labelledby','marketLensTitle');dialog.innerHTML='<div class="live-dialog-heading"><div><small>U1 OS / SOURCED INFORMATION</small><h2 id="marketLensTitle">Live information</h2></div><button class="feature-button" id="marketLensClose" autofocus>Close</button></div><div id="marketLensControls"></div><p id="marketLensStatus" class="live-feed-note" role="status"></p><div id="marketLensBody"></div>';
  document.body.append(dialog);$('marketLensClose').onclick=()=>dialog.close();
  document.addEventListener('click',event=>{const button=event.target.closest('[data-desktop-nav="news"],[data-desktop-nav="stocks"]');if(button){event.preventDefault();event.stopImmediatePropagation();open(button.dataset.desktopNav);}},true);
  async function get(path){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),32000);try{const response=await fetch('/api/workspace/live/'+path,{cache:'no-store',signal:controller.signal});const data=await response.json();if(!response.ok)throw new Error(data.error||'Feed unavailable');return data;}finally{clearTimeout(timer);}}
  async function refreshNews(force=false){
    if(busy.has('news')||document.hidden||!force&&Date.now()-newsAt<300000)return;busy.add('news');newsAt=Date.now();const requested=category;
    try{const data=await get('news?category='+requested);if(category!==requested)return;newsData=data;newsError=data.success&&!data.stale?'':data.error||'News feed is currently unavailable.';}catch(_){newsError='News connection unavailable. Restart the updated backend or check the source.';}
    finally{busy.delete('news');renderNews();if(dialog.open&&view==='news')renderDialog();if(category!==requested)refreshNews(true);}
  }
  async function refreshStocks(force=false){
    if(busy.has('stocks')||document.hidden||!force&&Date.now()-stocksAt<300000)return;busy.add('stocks');stocksAt=Date.now();const requested=symbols;
    try{const data=await get('stocks?symbols='+encodeURIComponent(requested));if(symbols!==requested)return;if(!data.success)throw new Error(data.error||'Watchlist unavailable');stockData=data;stockError='';}catch(error){stockError=error.name==='AbortError'?'Share quote request timed out. Values are not live.':error.message||'Share quotes unavailable.';}
    finally{busy.delete('stocks');renderStocks();if(dialog.open&&view==='stocks')renderDialog();if(symbols!==requested)refreshStocks(true);}
  }
  function headlines(limit=5){
    if(newsError)return `<p class="neon-placeholder">${esc(newsError)}</p>`;
    if(!newsData)return '<p class="neon-placeholder">Requesting current publisher headlines...</p>';
    const rows=(newsData.items||[]).slice(0,limit);
    return rows.map((item,index)=>`<a class="headline-item" href="${esc(safeURL(item.url))}" target="_blank" rel="noopener noreferrer"><span class="headline-index">${String(index+1).padStart(2,'0')}</span><span><b>${esc(item.title)}</b><small>${esc(item.source)} / ${esc(fmtTime(item.published_at))}</small></span><span class="headline-arrow" aria-hidden="true">&#8599;</span></a>`).join('')||'<p class="neon-placeholder">No headlines returned by this publisher.</p>';
  }
  function renderNews(){
    $('desktop-news').innerHTML=`<div class="news-category-pills">${['australia','world','business','technology'].map(id=>`<button data-news-category="${id}" class="${id===category?'selected':''}">${id==='australia'?'Australia':id[0].toUpperCase()+id.slice(1)}</button>`).join('')}</div>${headlines(4)}`;
    $('desktop-news-status').textContent=newsError?'Feed unavailable; no generated headlines.':newsData?(newsData.feed_age_warning?'Feed may be old. ':'')+newsData.source+' / retrieved '+fmtTime(newsData.fetched_at):'Connecting to the publisher...';
    const bar=$('lensBar-news');if(bar)bar.textContent=newsError?'Unavailable':newsData?.items?.[0]?(newsData.feed_age_warning?'OLDER FEED / ':'')+newsData.items[0].title:'Waiting for headlines';
  }
  $('desktop-news').addEventListener('click',event=>{const button=event.target.closest('[data-news-category]');if(button){category=button.dataset.newsCategory;newsData=null;newsError='';save();renderNews();refreshNews(true);}});
  function sparkline(quote){
    const points=(quote.points||[]).filter(item=>Number.isFinite(item.price));if(points.length<2)return '';
    const min=Math.min(...points.map(item=>item.price)),max=Math.max(...points.map(item=>item.price)),span=max-min||1;
    const line=points.map((point,index)=>`${(index/(points.length-1)*100).toFixed(2)},${(28-(point.price-min)/span*24).toFixed(2)}`).join(' ');
    return `<svg class="stock-sparkline" viewBox="0 0 100 32" role="img" aria-label="Provider intraday price observations, not a forecast"><polyline points="${line}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
  }
  function stockRows(limit=8,full=false){
    if(stockError)return `<p class="neon-placeholder">${esc(stockError)}</p>`;
    if(!stockData)return '<p class="neon-placeholder">Requesting provider quote snapshots...</p>';
    return (stockData.quotes||[]).slice(0,limit).map(quote=>{
      const valid=quote.success&&!quote.stale;
      return `<a class="stock-snapshot ${valid?'':'quote-unavailable'}" href="${esc(safeURL(quote.source_url))}" target="_blank" rel="noopener noreferrer"><span class="stock-initial">${esc(quote.symbol.slice(0,2))}</span><span class="stock-description"><b>${esc(quote.symbol)}</b><small>${valid?esc(quote.currency)+' / '+esc(quote.exchange||'Provider snapshot'):'UNAVAILABLE'}</small>${full?`<small>${esc(quote.name||'')}<br>Quoted: ${esc(fmtTime(quote.quoted_at))}<br>Retrieved: ${esc(fmtTime(quote.fetched_at))}</small>`:''}</span>${valid&&full?sparkline(quote):''}<span class="stock-value"><strong>${valid?esc(price(quote)):'--'}</strong><small class="${quote.change_percent<0?'down':'up'}">${valid&&Number.isFinite(quote.change_percent)?(quote.change_percent>0?'+':'')+quote.change_percent.toFixed(2)+'%':'No quote'}</small></span></a>`;
    }).join('');
  }
  function renderStocks(){
    $('desktop-stocks').innerHTML=`${stockRows(5)}<button class="neon-text-button" id="homeEditWatchlist">Edit watchlist / quote details &#8599;</button>`;
    $('homeEditWatchlist').onclick=()=>open('stocks');
    $('desktop-stocks-status').textContent=stockError?'Quotes unavailable. No simulated values.':'Yahoo Finance / indicative, potentially delayed. Open details for each quote time.';
    const bar=$('lensBar-stocks');if(bar)bar.textContent=stockError?'Unavailable':stockData?(stockData.quotes.filter(quote=>quote.success&&!quote.stale).slice(0,3).map(quote=>quote.symbol+' '+price(quote)).join(' / ')||'Quotes unavailable')+' / SNAPSHOTS':'Connecting...';
  }
  function open(id){view=id;renderDialog(true);if(!dialog.open)dialog.showModal();if(id==='news')refreshNews();else refreshStocks();}
  function renderDialog(controls=false){
    $('marketLensTitle').textContent=view==='news'?'Headlines, with context':'Stocks and shares';
    const control=$('marketLensControls');
    if(controls){
      if(view==='news'){
        control.innerHTML=`<div class="news-category-pills">${['australia','world','business','technology'].map(id=>`<button data-lens-category="${id}" class="${id===category?'selected':''}">${id}</button>`).join('')}<button id="refreshLensNews">Refresh</button></div>`;
        control.onclick=event=>{const button=event.target.closest('[data-lens-category]');if(button){category=button.dataset.lensCategory;newsData=null;newsError='';save();renderDialog(true);renderNews();refreshNews(true);}};$('refreshLensNews').onclick=()=>refreshNews(true);
      }else{
        control.onclick=null;control.innerHTML=`<form id="lensWatchlistForm" class="lens-watchlist-form"><label>Up to eight ticker symbols, separated by commas<input id="lensWatchlistInput" value="${esc(symbols)}" maxlength="200" placeholder="BHP.AX,CBA.AX,AAPL,MSFT,NVDA,SPY"></label><button class="feature-button primary">Update watchlist</button></form><p class="live-feed-note">Use .AX for ASX shares, for example BHP.AX. US examples: AAPL, MSFT, NVDA. ETFs and supported indices can also be added. This does not connect a brokerage account or place trades.</p>`;
        $('lensWatchlistForm').onsubmit=event=>{event.preventDefault();const input=$('lensWatchlistInput').value.toUpperCase().split(',').map(value=>value.trim()).filter(Boolean),unique=[...new Set(input)];if(!unique.length||unique.length>8||unique.some(value=>!(/^[A-Z0-9^][A-Z0-9.^=\-]{0,15}$/).test(value))){$('marketLensStatus').textContent='Enter one to eight valid ticker symbols.';return;}symbols=unique.join(',');stockData=null;stockError='';save();renderStocks();renderDialog();refreshStocks(true);};
      }
    }
    if(view==='news'){
      $('marketLensStatus').textContent=newsError||((newsData?.feed_age_warning?'The newest item is over 48 hours old. ':'')+'Publisher headlines refresh every five minutes while visible. Publication time is shown for each item.');
      $('marketLensBody').innerHTML=headlines(20)+(newsData?.source_url?`<p class="live-feed-note">Source: <a href="${esc(safeURL(newsData.source_url))}" target="_blank" rel="noopener noreferrer">${esc(newsData.source)}</a>. Retrieved ${esc(fmtTime(newsData.fetched_at))}. Headlines link directly to the original article; no generated story summaries are substituted.</p>`:'');
    }else{
      $('marketLensStatus').textContent=stockError||'INDICATIVE SNAPSHOTS / NOT GUARANTEED REAL-TIME. Refreshing does not eliminate exchange or provider delays.';
      $('marketLensBody').innerHTML=stockRows(8,true)+'<p class="live-feed-note">Prices are the latest regular-session observations returned by the provider. Percentage change is relative to the previous close when supplied. Intraday sparklines use actual returned observations. Last-trade time may be old while a market is closed. Public access can be blocked or unavailable; no fallback prices are fabricated.</p><a href="https://help.yahoo.com/kb/finance/article-exchanges-data-delays-sln2310.html" target="_blank" rel="noopener noreferrer">Yahoo Finance exchange coverage and delays</a>';
    }
  }
  renderNews();renderStocks();refreshNews();refreshStocks();
  setInterval(()=>{if(!document.hidden){refreshNews();refreshStocks();}},30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){refreshNews();refreshStocks();}});
})();
