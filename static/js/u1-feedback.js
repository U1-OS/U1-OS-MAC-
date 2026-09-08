(function(){
  'use strict';
  var key='u1.connection-sounds.v1',context=null,last=0,prefs;
  try{prefs=window.U1ReadyCore.soundPrefs(JSON.parse(localStorage.getItem(key)||'{}'));}catch(_){prefs=window.U1ReadyCore.soundPrefs();}
  function save(value){prefs=window.U1ReadyCore.soundPrefs(value);try{localStorage.setItem(key,JSON.stringify(prefs));}catch(_){throw new Error('Sound preferences could not be saved on this device.');}return Object.assign({},prefs);}
  async function play(kind,preview){
    if((!prefs.enabled&&!preview)||document.hidden||prefs.volume===0||Date.now()-last<600)return false;
    var Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return false;
    try{
      context=context||new Audio();if(context.state==='suspended')await context.resume();if(context.state!=='running')return false;
      last=Date.now();var notes=kind==='error'?[330,294]:kind==='warning'?[440,554]:kind==='open'?[587,740]:[523.25,659.25,783.99];
      notes.forEach(function(note,index){var oscillator=context.createOscillator(),gain=context.createGain(),at=context.currentTime+index*.075;oscillator.type='sine';oscillator.frequency.value=note;gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(prefs.volume*.28,at+.018);gain.gain.exponentialRampToValueAtTime(.0001,at+.24);oscillator.connect(gain);gain.connect(context.destination);oscillator.start(at);oscillator.stop(at+.26);oscillator.onended=function(){oscillator.disconnect();gain.disconnect();};});return true;
    }catch(_){return false;}
  }
  document.addEventListener('visibilitychange',function(){if(document.hidden&&context&&context.state==='running')context.suspend().catch(function(){});});
  window.U1Feedback=Object.freeze({play:play,save:save,preferences:function(){return Object.assign({},prefs);}});
})();
