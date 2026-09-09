/* A passphrase-protected application lock, backed by the local server gate. */
(function () {
 'use strict';
  var state=null,dialog,mode='',busy=false,polling=false,incident=false,lastError='',clockOffset=0,lastLock=null;
 function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
 function locked(){return incident||!state||state.locked;}
  function message(value){var node=dialog&&dialog.querySelector('[data-safety-message]');if(node)node.textContent=value;}
  function containDialogs(){if(locked())document.querySelectorAll('dialog[open]').forEach(function(other){if(other!==dialog)other.close();});}
 function contain(){
  var yes=locked();document.documentElement.dataset.u1Safety=yes?'locked':'open';
   document.querySelectorAll('.shell,#dock,#u1-utility-shelf').forEach(function(node){if(yes){if(!node.inert||node.dataset.u1BootInert)node.dataset.u1SafetyInert='true';node.inert=true;node.setAttribute('inert','');}else if(node.dataset.u1SafetyInert){delete node.dataset.u1SafetyInert;node.inert=!!node.dataset.u1BootInert;if(node.inert)node.setAttribute('inert','');else node.removeAttribute('inert');}});
   if(yes){document.querySelectorAll('audio,video').forEach(function(media){media.pause();});if(window.speechSynthesis)window.speechSynthesis.cancel();}
   if(lastLock!==yes){lastLock=yes;document.dispatchEvent(new CustomEvent('u1:safety-change',{detail:{locked:yes,configured:!!(state&&state.configured)}}));}
   containDialogs();
 }
 function show(next){
  if(!dialog)return;mode=next;
  var setup=next==='setup',unavailable=next==='unavailable',configured=!!(state&&state.configured);
  dialog.innerHTML='<div class="u1-safety-emblem"><img src="/assets/u1-logo.svg" alt="U1 OS" width="76" height="76"></div><p class="u1-life-eyebrow">YOUR SPACE. YOUR CONTROL.</p><h2 id="u1-safety-title">'+(setup?'Safety Centre':unavailable?'Safety service unavailable':locked()?'U1 OS is locked':'Your safety controls')+'</h2><p data-safety-reason>'+esc(state?state.reason:'Connecting to the local safety service...')+'</p>'+
   (unavailable?'<p>Workspace access is concealed until the local safety service responds. Start or restart U1 OS using its launcher, then retry. This is not a Mac-wide lock.</p><button type="button" class="btn" data-safety-action="retry">Retry connection</button>':setup?'<form data-safety-form="configure">'+(configured?'<label>Current passphrase<input name="current_passphrase" type="password" autocomplete="current-password" maxlength="128" required></label>':'')+'<label>'+(configured?'New or existing passphrase':'Choose a safety passphrase')+'<input name="passphrase" type="password" autocomplete="new-password" minlength="10" maxlength="128" required></label><label>Confirm passphrase<input name="confirm_passphrase" type="password" autocomplete="new-password" minlength="10" maxlength="128" required></label><label class="u1-safety-check"><input name="offline" type="checkbox" '+(!configured||state.offline_lock?'checked':'')+'> Lock when internet reachability is lost</label><label>Dead-man check-in interval<select name="minutes">'+[[0,'Off: manual switch only'],[5,'Every 5 minutes'],[15,'Every 15 minutes'],[30,'Every 30 minutes'],[60,'Every hour'],[120,'Every 2 hours'],[240,'Every 4 hours']].map(function(pair){return '<option value="'+pair[0]+'" '+(state&&state.checkin_minutes===pair[0]?'selected':'')+'>'+pair[1]+'</option>';}).join('')+'</select></label><label class="u1-safety-check"><input name="confirmed" type="checkbox" required> I understand this locks U1 OS access only. It does not cancel existing jobs or trades. There is no passphrase recovery button.</label><p class="u1-life-source">Offline detection sends credential-free HTTPS checks to Google and Cloudflare. Two failed server checks lock the OS; a browser offline event locks immediately. Restart always requires an unlock after setup.</p><button class="btn" type="submit">Save and arm safety lock</button></form>':locked()?'<form data-safety-form="unlock"><label>Safety passphrase<input name="passphrase" type="password" autocomplete="current-password" maxlength="128" required autofocus></label><button class="btn" type="submit">Unlock U1 OS</button></form><p>Coming back online does not unlock your workspace.</p><button class="btn" type="button" data-safety-action="settings">Safety settings</button>':'<div class="u1-life-actions"><button class="btn u1-danger" type="button" data-safety-action="lock">Lock now</button><button class="btn" type="button" data-safety-action="checkin" '+(!state.checkin_minutes?'disabled':'')+'>I am here: check in</button><button class="btn" type="button" data-safety-action="settings">Change safety settings</button></div><p data-safety-countdown></p><p>Shortcut: Command / Control + Shift + L while this U1 OS window is focused.</p>')+
   '<p class="u1-life-source" data-safety-network></p><p role="status" data-safety-message>'+esc(lastError)+'</p>'+(!locked()?'<button type="button" class="btn" data-safety-action="close">Return to workspace</button>':'')+'<small class="u1-life-source">Application access lock, not encryption, an emergency service, a hardware dead-man device or a system firewall.</small>';
  if(locked())document.querySelectorAll('dialog[open]').forEach(function(other){if(other!==dialog)other.close();});
  if(!dialog.open)dialog.showModal();updateLabels();
 }
 function updateLabels(){
  if(!dialog||!state)return;
  var net=dialog.querySelector('[data-safety-network]');if(net)net.textContent='Internet checks: '+(!state.offline_lock?'disabled':state.network===true?'reachable':state.network===false?'unreachable':'waiting for a check')+'. '+(state.network_checked_at?'Checked '+new Date(state.network_checked_at*1000).toLocaleTimeString()+'.':'');
  var remaining=state.deadline?Math.max(0,Math.ceil((state.deadline*1000-Date.now()-clockOffset)/1000)):null;
  var count=dialog.querySelector('[data-safety-countdown]');if(count)count.textContent=remaining===null?'Check-in timer is off.':Math.floor(remaining/60)+'m '+remaining%60+'s until the next required check-in.';
  var button=document.getElementById('u1-safety-open');if(button){button.textContent=state.configured?(locked()?'OS locked':remaining!==null?'Check in '+Math.floor(remaining/60)+'m':'Safety armed'):'Set up safety';button.dataset.armed=String(state.configured);}
  if(remaining===0&&!state.locked&&!incident){incident=true;contain();show('unlock');poll();}
 }
 function apply(data){
  var previous=state;state=data;clockOffset=Date.now()-data.server_time*1000;
  if(data.locked)incident=false;
  contain();updateLabels();
  if(locked()) {if(!dialog.open||mode==='unavailable'||(!previous||!previous.locked)&&data.locked)show(data.fault?'unavailable':'unlock');}
  else if(previous&&previous.locked&&dialog.open){dialog.close();mode='';}
 }
 async function request(body){
  var controller=new AbortController(),timeout=setTimeout(function(){controller.abort();},15000);
  try{var response=await fetch('/api/safety',{method:body?'POST':'GET',cache:'no-store',headers:body?{'Content-Type':'application/json','X-U1-Safety':state&&state.csrf_token||''}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal});var data=await response.json();if(!response.ok||!data.success)throw Error(data.error||'Safety service did not accept the request.');return data;}finally{clearTimeout(timeout);}
 }
 async function poll(){
  if(polling||busy)return;polling=true;
  try{var data=await request();
   if(incident&&data.configured&&!data.locked){state=data;data=await request({action:'lock'});}
   lastError='';apply(data);
   if(!navigator.onLine&&data.configured&&data.offline_lock&&!data.locked)lockNow('offline');
  }catch(error){lastError=error.message||'The safety service is unavailable.';if(!state||state.configured){incident=true;contain();if(mode!=='unavailable'||!dialog.open)show('unavailable');else message(lastError);}}
  finally{polling=false;}
 }
 async function lockNow(action){
  if(!state||!state.configured){show('setup');return;}
  incident=true;contain();show('unlock');
  try{apply(await request({action:action||'lock'}));}catch(error){lastError=error.message;message('Workspace concealed locally. Server lock not confirmed; it will be requested when the local service reconnects.');}
 }
 function init(){
   dialog=document.createElement('dialog');dialog.id='u1-safety-dialog';dialog.setAttribute('aria-labelledby','u1-safety-title');document.body.append(dialog);
   if(typeof MutationObserver==='function'){var modalObserver=new MutationObserver(containDialogs);modalObserver.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['open']});window.addEventListener('pagehide',function(){modalObserver.disconnect();});}
  dialog.addEventListener('cancel',function(event){if(locked())event.preventDefault();});
  dialog.addEventListener('click',function(event){var button=event.target.closest('[data-safety-action]');if(!button)return;var action=button.dataset.safetyAction;if(action==='close'){dialog.close();return;}if(action==='settings'){lastError='';show('setup');return;}if(action==='retry'){poll();return;}if(action==='lock'){lockNow();return;}if(action==='checkin'){button.disabled=true;request({action:'checkin'}).then(function(data){apply(data);message('Check-in received by the server.');}).catch(function(error){message(error.message);}).finally(function(){button.disabled=false;});}});
  dialog.addEventListener('submit',async function(event){event.preventDefault();if(busy)return;var form=event.target,values=Object.fromEntries(new FormData(form));if(form.dataset.safetyForm==='configure'&&values.passphrase!==values.confirm_passphrase){message('The passphrases do not match.');return;}busy=true;var button=form.querySelector('[type=submit]');button.disabled=true;message('Waiting for the local safety service...');try{var payload={action:form.dataset.safetyForm,passphrase:values.passphrase};if(payload.action==='configure')Object.assign(payload,{current_passphrase:values.current_passphrase,minutes:Number(values.minutes),offline:form.elements.offline.checked,confirmed:form.elements.confirmed.checked});var data=await request(payload);form.reset();lastError='';incident=false;apply(data);if(data.locked)show('unlock');}catch(error){message(error.message);}finally{busy=false;button.disabled=false;}});
  var control=document.createElement('button');control.type='button';control.className='btn';control.id='u1-safety-open';control.textContent='Safety';control.onclick=function(){show(state&&state.configured?'controls':'setup');};var anchor=document.getElementById('u1-control-open')||document.getElementById('soundBtn');if(anchor)anchor.before(control);else document.body.append(control);
  window.addEventListener('keydown',function(event){if((event.metaKey||event.ctrlKey)&&event.shiftKey&&event.key.toLowerCase()==='l'){event.preventDefault();event.stopImmediatePropagation();lockNow();}},true);
  window.addEventListener('offline',function(){if(state&&state.configured&&state.offline_lock)lockNow('offline');});window.addEventListener('online',poll);
  document.addEventListener('visibilitychange',function(){if(!document.hidden)poll();});
  contain();poll();var timer=setInterval(poll,5000),countdown=setInterval(updateLabels,1000);window.addEventListener('pagehide',function(){clearInterval(timer);clearInterval(countdown);});
 }
 window.U1Safety={open:function(){show(state&&state.configured?'controls':'setup');},lock:lockNow,isLocked:locked};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
