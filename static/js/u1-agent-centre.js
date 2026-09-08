import {icon, mark} from './prism-ui.js';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, selected = 'improvement', busy = false, csrf, dialog;
const names = {improvement:'Systems engineer', design:'Design director', trading:'Trading researcher', crypto:'Crypto analyst'};
const symbols = {improvement:'system', design:'notes', trading:'globe', crypto:'shield'};
const timestamp = value => value ? new Date(value * 1000).toLocaleString() : 'Not checked';
async function post(body) {
  if (!csrf) { const r = await fetch('/api/integrations', {cache:'no-store'}); if (!r.ok) throw Error('Connection settings are unavailable'); csrf = (await r.json()).csrf_token; }
  const response = await fetch('/api/workspace/agents', {method:'POST', headers:{'Content-Type':'application/json','X-U1-CSRF':csrf}, body:JSON.stringify(body), signal:AbortSignal.timeout(85000)});
  const data = await response.json();
  if (!response.ok || data.success === false) { if (response.status === 403) csrf = null; throw Error(data.error || data.message || 'The action did not complete'); }
  return data;
}
function visualMeasurements() {
  const visible = el => { const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 && getComputedStyle(el).visibility!=='hidden'; };
  const logos = [...document.querySelectorAll('.prism-provider-mark')].filter(visible);
  const clipped = logos.filter(el => {const r=el.getBoundingClientRect(),svg=el.querySelector('svg');if(!svg)return false;const s=svg.getBoundingClientRect();return s.width>r.width+1||s.height>r.height+1;}).length;
  const unlabelled = [...document.querySelectorAll('button')].filter(visible).filter(el => !el.textContent.trim() && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby') && !el.title).length;
  return {logos_clipped:clipped, controls_unlabelled:unlabelled, horizontal_overflow:Number(document.documentElement.scrollWidth>innerWidth+2), viewport_width:Math.round(innerWidth)};
}
function notice(message, error=false) { const el=dialog.querySelector('[data-agent-notice]'); el.textContent=message; el.dataset.error=String(error); }
function render() {
  if (!state) return;
  const agent = state.agents.find(a=>a.id===selected), history=state.history.filter(r=>r.agent===selected), latest=history[0];
  dialog.querySelector('[data-agent-tabs]').innerHTML=state.agents.map(a=>`<button type="button" data-agent-select="${a.id}" aria-pressed="${a.id===selected}">${icon(symbols[a.id])}<span>${esc(a.name)}<small>${a.enabled?'Monitoring every 15 min':'Manual checks'}</small></span></button>`).join('');
  dialog.querySelector('[data-agent-content]').innerHTML=`<div class="u1-agent-heading"><div><span class="u1-agent-eyebrow">${selected==='trading'||selected==='crypto'?'RESEARCH ONLY':'OBSERVE / REVIEW / IMPROVE'}</span><h2>${esc(agent.name)}</h2><p>${esc(agent.description)}</p></div><span class="u1-agent-status">${state.running?'Check in progress':'Ready for a check'}</span></div>
  <div class="u1-agent-actions"><button type="button" data-agent-run ${busy?'disabled':''}>${icon('search')} Run evidence check</button><button type="button" data-agent-monitor ${busy?'disabled':''}>${icon(agent.enabled?'close':'automation')}${agent.enabled?'Pause monitoring':'Enable 15-min monitoring'}</button></div>
  <div class="u1-agent-metrics"><div><strong>${history.length}</strong><span>Retained runs for this agent</span></div><div><strong>${state.feedback_count}</strong><span>Saved feedback across agents</span></div><div><strong>Read only</strong><span>No orders, code changes or publishing</span></div></div>
  <section class="u1-agent-results" aria-label="Latest evidence"><div class="u1-agent-section-title"><h3>Latest evidence</h3><span>${latest?esc(timestamp(latest.created)):'No run yet'}</span></div>
  ${latest?`<p class="u1-agent-source">${esc(latest.engine)} / ${esc(latest.evidence?.source || 'Local evidence')}</p>`:'<p class="u1-agent-empty">Run a check to collect actual evidence. No sample findings, trades or performance figures are displayed.</p>'}
  ${(latest?.evidence?.quotes||[]).map(q=>`<div class="u1-agent-quote"><span>${esc(q.symbol)} <small>${esc(q.currency)}</small></span><strong>${new Intl.NumberFormat(undefined,{style:'currency',currency:'USD'}).format(q.amount)}</strong><small>Snapshot retrieved ${esc(timestamp(q.retrieved_at))}; not streaming</small></div>`).join('')}
  ${(latest?.findings||[]).map(f=>`<article class="u1-agent-finding"><div><span class="u1-agent-priority">${esc(f.priority)}</span><h4>${esc(f.title)}</h4><p>${esc(f.detail)}</p></div><div class="u1-agent-feedback"><button type="button" data-feedback="1" data-finding="${esc(f.key)}" data-run="${latest.id}" aria-label="Mark ${esc(f.title)} useful">Useful</button><button type="button" data-feedback="-1" data-finding="${esc(f.key)}" data-run="${latest.id}" aria-label="Lower the priority of ${esc(f.title)}">Lower priority</button></div></article>`).join('')}
  ${latest?.analysis?`<article class="u1-agent-analysis"><h4>AI review / verify before acting</h4><pre>${esc(latest.analysis)}</pre></article>`:''}</section>
  <details class="u1-agent-ai"><summary>Local AI review</summary><p>Optional Ollama analysis runs on your Mac. Only this agent's evidence and the objective below are sent to the local model. No subscription account is assumed connected.</p><label>Review objective<textarea data-agent-objective maxlength="3000" placeholder="What should this agent investigate or improve?"></textarea></label><div class="u1-agent-actions"><button type="button" data-agent-models>Find installed models</button><select data-agent-model aria-label="Installed local model"><option value="">Choose an installed model</option></select><button type="button" data-agent-ai-run>Request AI review</button></div></details>
  <details class="u1-agent-history"><summary>Run history and permissions</summary><p>Feedback changes future suggestion ranking, not model weights. Safety findings retain priority. Monitoring runs bounded checks while the local server is running; it never invokes AI automatically.</p><ul>${history.map(r=>`<li>${esc(timestamp(r.created))} / ${esc(r.engine)} / ${r.findings.length} findings</li>`).join('')||'<li>No runs recorded.</li>'}</ul><p>Cannot execute trades, access wallets, edit code, read email, send messages, publish, or expand permissions.</p></details>`;
}
async function refresh() {const r=await fetch('/api/workspace/agents',{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Agent Centre backend is unavailable. Restart the local U1 OS server to load the new module.');state=await r.json();render();}
async function execute(action) {if(busy)return;busy=true;dialog.setAttribute('aria-busy','true');try{await action();await refresh();}catch(e){notice(e.message,true);}finally{busy=false;dialog.removeAttribute('aria-busy');dialog.querySelectorAll('[data-agent-run],[data-agent-monitor]').forEach(button=>{button.disabled=false;});}}
function init() {
  if (new URLSearchParams(location.search).has('u1-frame') || !(document.getElementById('prism-shell') || document.querySelector('.shell'))) return;
  const sheet=document.createElement('link');sheet.rel='stylesheet';sheet.href='/css/u1-agent-centre.css';document.head.append(sheet);
  dialog=document.createElement('dialog');dialog.className='u1-agent-centre';dialog.id='u1-agent-centre';dialog.setAttribute('aria-labelledby','u1-agent-title');
  dialog.innerHTML=`<header>${mark()}<div><span class="u1-agent-eyebrow">U1 OS / BUSINESS INTELLIGENCE</span><h1 id="u1-agent-title">Agent Centre</h1></div><button type="button" data-agent-close aria-label="Close Agent Centre">${icon('close')}</button></header><div class="u1-agent-layout"><nav data-agent-tabs aria-label="Agents"></nav><main><p data-agent-notice role="status">Loading local agent history...</p><div data-agent-content></div></main></div>`;
  document.body.append(dialog);
  const nav=document.querySelector('.prism-sidebar nav') || document.getElementById('rail');
  if(nav){const button=document.createElement('button');button.type='button';button.className='navitem';button.dataset.u1OpenAgents='';button.innerHTML=`${icon('ai')}<span>Agent Centre</span>`;button.setAttribute('aria-haspopup','dialog');button.addEventListener('click',()=>{dialog.showModal();refresh().then(()=>notice('Evidence stays local. Review suggestions before acting.')).catch(e=>notice(e.message,true));});nav.append(button);}
  dialog.addEventListener('click',event=>{
    const b=event.target.closest('button');if(!b)return;
    if(b.hasAttribute('data-agent-close'))return dialog.close();
    if(b.dataset.agentSelect){if(busy)return;selected=b.dataset.agentSelect;render();return;}
    if(b.hasAttribute('data-agent-run'))return execute(async()=>{notice('Collecting evidence...');await post({action:'run',agent:selected,...(selected==='design'?{visual:visualMeasurements()}:{})});notice('Evidence collected. No changes or trades were executed.');});
    if(b.hasAttribute('data-agent-monitor'))return execute(async()=>{const enabled=!state.agents.find(a=>a.id===selected).enabled;await post({action:'configure',agent:selected,enabled});notice(enabled?'Monitoring enabled. First automatic check is within 15 minutes. No AI calls are scheduled.':'Monitoring paused. An in-progress read-only check may finish.');});
    if(b.dataset.feedback)return execute(async()=>{const result=await post({action:'feedback',agent:selected,run_id:b.dataset.run,finding:b.dataset.finding,value:Number(b.dataset.feedback)});notice(result.message);});
    if(b.hasAttribute('data-agent-models')){if(busy)return;b.disabled=true;post({action:'models'}).then(data=>{dialog.querySelector('[data-agent-model]').innerHTML='<option value="">Choose an installed model</option>'+data.models.map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join('');notice(data.available?'Installed local models discovered.':data.message||'No local models are installed.');}).catch(e=>notice(e.message,true)).finally(()=>b.disabled=false);return;}
    if(b.hasAttribute('data-agent-ai-run')){const model=dialog.querySelector('[data-agent-model]').value,objective=dialog.querySelector('[data-agent-objective]').value;if(!model)return notice('Find and choose an installed local model first.',true);return execute(async()=>{notice('The local model is reviewing evidence. No tools or trading permissions are provided.');await post({action:'run',agent:selected,model,objective,...(selected==='design'?{visual:visualMeasurements()}:{})});notice('AI review saved. Check its conclusions against the evidence.');});}
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(init,0),{once:true});else setTimeout(init,0);
