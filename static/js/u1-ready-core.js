(function(root,factory){var api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.U1ReadyCore=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  function connection(card,google,now){
    now=now||Date.now();
    if(card.id==='gmail'||card.id==='google_calendar'){
      var fresh=google&&google.session_verified===true&&google.stale!==true&&typeof google.last_sync==='number'&&now-google.last_sync*1000<660000;
      return {label:fresh?'Synced':google&&google.configured?'Ready to authorise / sync':'Not connected',tone:fresh?'ready':'setup',sync:!!(google&&google.configured),lastSync:google&&google.last_sync||null};
    }
    return {label:card.stage==='setup_slot'?'Adapter pending':card.saved_fields?'Settings saved / unverified':card.local?'Local tool / check required':'Not connected',tone:'setup',sync:false,lastSync:null};
  }
  function safePortal(value){try{var u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;}catch(_){return null;}}
  function soundPrefs(value){value=value&&typeof value==='object'?value:{};return {enabled:value.enabled===true,volume:typeof value.volume==='number'&&Number.isFinite(value.volume)?Math.min(.5,Math.max(0,value.volume)):.14};}
  function canApply(plan,now){return !!(plan&&!plan.applied&&!plan.expired&&typeof plan.expires==='number'&&plan.expires*1000>(now||Date.now())&&/^[a-f0-9]{32}$/.test(plan.id||'')&&/^[a-f0-9]{40,64}$/.test(plan.to_commit||''));}
  return Object.freeze({connection:connection,safePortal:safePortal,soundPrefs:soundPrefs,canApply:canApply});
});
