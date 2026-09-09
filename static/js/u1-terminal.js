import {icon} from './u1-icons.js';
let panel,term,fit,session=null,csrf=null,cursor=0,pollTimer=null,inputChain=Promise.resolve(),resizeObserver;
const decoder=new TextDecoder();
const status=text=>{panel.querySelector('#u1-terminal-state').textContent=text;};
async function post(body,retry=true){
  if(!csrf){const response=await fetch('/api/integrations',{cache:'no-store'});const data=await response.json();csrf=data.csrf_token;if(!csrf)throw new Error('Local session authorization is unavailable.');}
  const response=await fetch('/api/workspace/terminal',{method:'POST',headers:{'Content-Type':'application/json','X-U1-CSRF':csrf},body:JSON.stringify({...body,...(session?{session:session.session,capability:session.capability}:{})})});
  if(response.status===403&&retry){csrf=null;return post(body,false);}
  const data=await response.json();if(!response.ok||!data.success)throw new Error(data.error||'Terminal request failed.');return data;
}
function script(url){return new Promise((resolve,reject)=>{const element=document.createElement('script');element.src=url;element.onload=resolve;element.onerror=()=>reject(new Error('The local terminal UI could not load.'));document.head.append(element);});}
async function poll(){
  if(!session)return;
  try{const result=await post({action:'poll',cursor});cursor=result.cursor;if(result.truncated)term.writeln('\r\n[Older output dropped from the bounded session buffer.]');if(result.output){const data=Uint8Array.from(atob(result.output),c=>c.charCodeAt(0));term.write(decoder.decode(data,{stream:true}));}if(result.exited){status('Shell exited. Start a new session.');await post({action:'close'}).catch(()=>{});session=null;panel.querySelector('[data-terminal-start]').hidden=false;return;}}
  catch(error){status(error.message);}
  pollTimer=setTimeout(poll,panel.hidden?1800:450);
}
function input(text){inputChain=inputChain.then(async()=>{if(!session)return;try{await post({action:'input',input:text});}catch(error){status(error.message);}});}
async function resize(){if(!term||panel.hidden)return;fit.fit();if(session)await post({action:'resize',cols:Math.max(20,Math.min(300,term.cols)),rows:Math.max(5,Math.min(100,term.rows))}).catch(()=>{});}
async function start(){
  const button=panel.querySelector('[data-terminal-start]');button.disabled=true;
  try{
    if(!term){await script('/vendor/xterm/xterm.js');await script('/vendor/xterm/addon-fit.js');term=new window.Terminal({cursorBlink:true,fontFamily:'"JetBrains Mono", monospace',fontSize:12,lineHeight:1.35,scrollback:3000,allowProposedApi:false,theme:{background:'#030b16',foreground:'#dcefff',cursor:'#78e5ff',selectionBackground:'#235d8880',black:'#061426',red:'#ff8791',green:'#76e8bc',yellow:'#ffd38e',blue:'#7bb1ff',magenta:'#b9a8ff',cyan:'#81e9ff',white:'#edf7ff'}});fit=new window.FitAddon.FitAddon();term.loadAddon(fit);term.open(panel.querySelector('#u1-terminal-mount'));term.onData(input);fit.fit();resizeObserver=new ResizeObserver(()=>resize());resizeObserver.observe(panel.querySelector('#u1-terminal-mount'));}
    session=await post({action:'start',acknowledge:true,cols:Math.max(20,Math.min(300,term.cols)),rows:Math.max(5,Math.min(100,term.rows))});cursor=0;term.clear();
    status(`LOCAL SHELL / ${session.tools.claude?'Claude Code found':'Claude Code not found'} / ${session.tools.codex?'Codex found':'Codex not found'}`);button.hidden=true;panel.querySelector('.u1-terminal-consent').hidden=true;term.focus();poll();
  }catch(error){status(error.message);}finally{button.disabled=false;}
}
function open(){panel.hidden=false;resize();if(term)term.focus();}
function init(){
  if(new URLSearchParams(location.search).has('u1-frame'))return;
  for(const href of ['/vendor/xterm/xterm.css','/css/u1-terminal.css']){const style=document.createElement('link');style.rel='stylesheet';style.href=href;document.head.append(style);}
  panel=document.createElement('section');panel.id='u1-terminal';panel.hidden=true;panel.setAttribute('aria-label','U1 local terminal');
  panel.innerHTML=`<header><div>${icon('code')}<strong>U1 Terminal</strong><span>YOUR MAC / REAL COMMANDS</span></div><div><button type="button" data-terminal-max aria-label="Toggle terminal size">Expand</button><button type="button" data-terminal-hide aria-label="Hide terminal without ending session">${icon('close')}</button></div></header><div class="u1-terminal-toolbar"><button type="button" data-terminal-cli="claude">Insert Claude Code</button><button type="button" data-terminal-cli="codex">Insert Codex</button><button type="button" data-terminal-interrupt>Ctrl+C</button><button type="button" data-terminal-end>End session</button></div><div class="u1-terminal-consent"><h2>Build from inside your OS.</h2><p>This is a real local shell with your Mac user's file permissions. Claude Code and Codex use their own sign-in and approval settings. Nothing is executed until you start a session and enter a command.</p><p>Commands can modify or delete files. AI tools may send prompts to their configured provider. Closing this panel keeps the session running; End session stops it. Disconnected sessions expire after 15 minutes.</p></div><button type="button" data-terminal-start>Start local terminal</button><div id="u1-terminal-mount"></div><footer><span id="u1-terminal-state">Not started / no commands running</span><small>AI shortcuts insert a command. Press Enter yourself to run it.</small></footer>`;
  document.body.append(panel);
  const header=document.querySelector('.u1-global-heading');if(header){const button=document.createElement('button');button.type='button';button.setAttribute('aria-label','Open local terminal');button.title='Local terminal';button.innerHTML=icon('code');button.onclick=open;header.append(button);}
  panel.querySelector('[data-terminal-start]').onclick=start;panel.querySelector('[data-terminal-hide]').onclick=()=>panel.hidden=true;
  panel.querySelector('[data-terminal-max]').onclick=()=>{panel.classList.toggle('is-expanded');resize();};
  panel.querySelector('[data-terminal-interrupt]').onclick=()=>input('\x03');
  panel.querySelector('[data-terminal-end]').onclick=async()=>{if(!session)return;try{await post({action:'close'});clearTimeout(pollTimer);session=null;status('Session ended.');panel.querySelector('[data-terminal-start]').hidden=false;term.writeln('\r\n[Session ended.]');}catch(error){status(error.message);}};
  for(const button of panel.querySelectorAll('[data-terminal-cli]'))button.onclick=()=>{if(!session){status('Start a terminal session first.');return;}input(button.dataset.terminalCli);term.focus();};
  window.addEventListener('pagehide',()=>{clearTimeout(pollTimer);resizeObserver?.disconnect();if(session&&csrf)fetch('/api/workspace/terminal',{method:'POST',headers:{'Content-Type':'application/json','X-U1-CSRF':csrf},body:JSON.stringify({action:'close',session:session.session,capability:session.capability}),keepalive:true}).catch(()=>{});},{once:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(init),{once:true});else requestAnimationFrame(init);
