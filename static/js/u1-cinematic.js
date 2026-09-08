/* U1 launch and motion runtime. Decorative motion is never telemetry. */
(function () {
  'use strict';
  var root=document.documentElement, key='u1.launch.preferences.v1';
  var preferences={quality:'auto',motion:'full',skipBoot:false,glow:1,depth:1};
  try {var saved=JSON.parse(localStorage.getItem(key)||'{}');Object.keys(preferences).forEach(function(k){if(saved[k]!==undefined)preferences[k]=saved[k];});} catch(e) {}
  function clamp(v,min,max){return Math.max(min,Math.min(max,Number(v)||0));}
  function normalise(){if(['auto','ultra','high','balanced','low'].indexOf(preferences.quality)<0)preferences.quality='auto';if(['full','reduced'].indexOf(preferences.motion)<0)preferences.motion='full';preferences.glow=clamp(preferences.glow,0,1.5);preferences.depth=clamp(preferences.depth,0,1);preferences.skipBoot=preferences.skipBoot===true;}
  function apply(){normalise();root.dataset.u1Quality=preferences.quality;root.dataset.u1Motion=preferences.motion;root.style.setProperty('--u1-glow',preferences.glow);root.style.setProperty('--u1-depth',preferences.depth);}
  apply();
  var reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function still(){return reduced.matches||preferences.motion==='reduced'||preferences.quality==='low';}
  function get(url,timeout){var controller=new AbortController(),timer=setTimeout(function(){controller.abort();},timeout||7000);return fetch(url,{cache:'no-store',signal:controller.signal}).then(function(r){if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).finally(function(){clearTimeout(timer);});}
  function checked(url,valid){return get(url,2200).then(function(data){if(!valid(data))throw Error('Unexpected API response');return {available:true,data:data};}).catch(function(){return {available:false,data:null};});}
  var pending=null,results=null;
  function requests(fresh){
    if(pending&&!fresh)return pending;
    pending=Promise.all([
      checked('/api/state',function(d){return d&&d.services&&typeof d.services==='object';}),
      checked('/api/workspace/prism/summary',function(d){return d&&d.success===true&&Array.isArray(d.records);}),
      checked('/api/integrations',function(d){return d&&d.success===true&&Array.isArray(d.cards);})
    ]).then(function(rows){results={services:rows[0],workspace:rows[1],integrations:rows[2]};return results;});
    return pending;
  }
  function stage(id,status,message){var el=document.querySelector('[data-boot-stage="'+id+'"]');if(!el)return;el.dataset.state=status;el.querySelector('b').textContent=message;}
  var bootTimer,bootMinimum;
  function enter(){clearTimeout(bootTimer);clearTimeout(bootMinimum);var boot=document.getElementById('boot');if(!boot)return;boot.classList.add('gone');boot.setAttribute('aria-hidden','true');boot.inert=true;window.dispatchEvent(new CustomEvent('u1:boot-complete',{detail:{checks:results}}));}
  function startup(preview){
    var boot=document.getElementById('boot');if(!boot)return;
    clearTimeout(bootTimer);clearTimeout(bootMinimum);boot.classList.remove('gone');boot.removeAttribute('aria-hidden');boot.inert=false;
    ['core','data','services','ai','integrations'].forEach(function(id){stage(id,'checking','Checking');});
    root.style.setProperty('--u1-boot-progress','20%');stage('core','ready','Interface loaded');
    var start=performance.now();
    document.getElementById('u1-skip-boot').onclick=enter;
    if(preferences.skipBoot&&!preview)enter();
    bootTimer=setTimeout(function(){document.getElementById('u1-boot-message').textContent='Some checks are still unavailable. The workspace remains accessible.';enter();},2800);
    requests(!!preview).then(function(r){
      stage('services',r.services.available?'ready':'unavailable',r.services.available?'Backend responding':'Backend unavailable');
      stage('data',r.workspace.available?'ready':'unavailable',r.workspace.available?'Local records available':'Data unavailable');
      stage('integrations',r.integrations.available?'partial':'unavailable',r.integrations.available?'Account verification required':'Registry unavailable');
      stage('ai','partial','Choose an authorised provider');
      root.style.setProperty('--u1-boot-progress','100%');
      document.getElementById('u1-boot-message').textContent=r.services.available?'Local checks complete. Saved settings are not proof of account access.':'Backend unavailable. Use the U1 OS launcher to start your local server.';
      bootMinimum=setTimeout(enter,Math.max(0,(still()?0:1200)-(performance.now()-start)));
    });
  }
  window.U1Launch={start:startup,preview:function(){startup(true);},requests:requests,get:get,preferences:function(){return Object.assign({},preferences);},save:function(values){Object.keys(preferences).forEach(function(k){if(values[k]!==undefined)preferences[k]=values[k];});apply();var persisted=true;try{localStorage.setItem(key,JSON.stringify(preferences));}catch(e){persisted=false;}window.dispatchEvent(new Event('u1:preferences'));return persisted;}};

  var running=false,frame=0,last=0,engine=null,inView=true,slow=0,adaptiveScale=1;
  function desiredScale(){var cap=preferences.quality==='low'?1:preferences.quality==='balanced'?1.3:2;return Math.min(devicePixelRatio||1,cap)*adaptiveScale;}
  function createEarth(){
    var canvas=document.getElementById('globe');if(!canvas)return null;
    var parent=canvas.parentElement,gl=canvas.getContext('webgl',{alpha:true,antialias:false,powerPreference:'low-power',preserveDrawingBuffer:false});
    if(!gl){parent.dataset.webgl='unavailable';return null;}
    var vs='attribute vec2 p;varying vec2 uv;void main(){uv=p;gl_Position=vec4(p,0.,1.);}';
    var fs='precision mediump float;varying vec2 uv;uniform sampler2D day;uniform sampler2D night;uniform float aspect;uniform float angle;uniform vec2 pointer;void main(){vec2 p=uv*1.25;p.x*=aspect;float r=dot(p,p);if(r>1.18){gl_FragColor=vec4(0.);return;}if(r>1.){float a=pow(max(0.,1.-(sqrt(r)-1.)/.086),2.)*.3;gl_FragColor=vec4(.04,.44,1.,a);return;}vec3 n=vec3(p,sqrt(max(0.,1.-r)));float a=angle+pointer.x*.12;float c=cos(a),s=sin(a);vec3 q=vec3(c*n.x+s*n.z,n.y,-s*n.x+c*n.z);float t=pointer.y*.07-.13;vec3 w=vec3(q.x,cos(t)*q.y-sin(t)*q.z,sin(t)*q.y+cos(t)*q.z);vec2 tex=vec2(atan(w.z,w.x)/6.283185+.5,asin(clamp(w.y,-1.,1.))/3.141593+.5);vec3 d=texture2D(day,tex).rgb;vec3 k=texture2D(night,tex).rgb;float light=smoothstep(-.28,.48,dot(n,normalize(vec3(-.6,.45,.75))));vec3 col=d*(.08+.82*light)+k*(1.-light)*1.1;float rim=pow(1.-n.z,3.5);col+=vec3(.025,.35,.75)*rim;col*=.7+.3*n.z;gl_FragColor=vec4(col,1.);}';
    function shader(type,source){var s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('Earth shader unavailable');return s;}
    var program;try{program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vs));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Earth renderer unavailable');}catch(e){parent.dataset.webgl='unavailable';return null;}
    gl.useProgram(program);var buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);var position=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    var angleLoc=gl.getUniformLocation(program,'angle'),aspectLoc=gl.getUniformLocation(program,'aspect'),pointerLoc=gl.getUniformLocation(program,'pointer');
    var angle=-.82,targetX=0,targetY=0,x=0,y=0,available=false;
    function texture(url,index,name){return new Promise(function(resolve,reject){var image=new Image();var timeout=setTimeout(function(){reject(Error('Texture unavailable'));},7000);image.onload=function(){clearTimeout(timeout);gl.activeTexture(gl.TEXTURE0+index);var t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.uniform1i(gl.getUniformLocation(program,name),index);resolve();};image.onerror=function(){clearTimeout(timeout);reject(Error('Texture unavailable'));};image.src=url;});}
    Promise.all([texture('/assets/prism-earth.jpg',0,'day'),texture('/assets/u1-earth-night.jpg',1,'night')]).then(function(){available=true;parent.dataset.webgl='ready';resize();resume();}).catch(function(){parent.dataset.webgl='unavailable';});
    function resize(){var r=canvas.getBoundingClientRect(),scale=desiredScale();if(!r.width||!r.height)return;scale=Math.min(scale,2048/Math.max(r.width,r.height));canvas.width=Math.max(1,Math.round(r.width*scale));canvas.height=Math.max(1,Math.round(r.height*scale));gl.viewport(0,0,canvas.width,canvas.height);gl.uniform1f(aspectLoc,r.width/r.height);draw(0);}
    function draw(delta){if(!available)return;if(!still())angle+=Math.min(delta,50)*.000045;x+=(targetX-x)*.07;y+=(targetY-y)*.07;gl.uniform1f(angleLoc,angle);gl.uniform2f(pointerLoc,x,y);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.drawArrays(gl.TRIANGLES,0,6);}
    canvas.addEventListener('pointermove',function(e){if(e.pointerType==='touch')return;var r=canvas.getBoundingClientRect();targetX=(e.clientX-r.left)/r.width-.5;targetY=(e.clientY-r.top)/r.height-.5;if(still()){x=targetX;y=targetY;draw(0);}});
    canvas.addEventListener('pointerleave',function(){targetX=targetY=0;});
    canvas.addEventListener('webglcontextlost',function(e){e.preventDefault();available=false;parent.dataset.webgl='unavailable';});
    new ResizeObserver(resize).observe(canvas);resize();return {draw:draw,resize:resize};
  }
  function loop(now){frame=0;if(document.hidden||!inView)return;var delta=last?now-last:16;last=now;if(engine)engine.draw(delta);if(preferences.quality==='auto'&&delta>28&&delta<150){slow++;if(slow>100&&adaptiveScale>0.7){adaptiveScale=.7;if(engine)engine.resize();}}else slow=Math.max(0,slow-1);if(!still())frame=requestAnimationFrame(loop);}
  function resume(){if(!frame&&!document.hidden&&inView){last=0;frame=requestAnimationFrame(loop);}}
  function startMotion(){
    if(running)return;running=true;engine=createEarth();
    var globe=document.getElementById('globe');if(globe&&window.IntersectionObserver)new IntersectionObserver(function(entries){inView=entries[0].isIntersecting;if(!inView&&frame){cancelAnimationFrame(frame);frame=0;}else resume();}).observe(globe);
    document.addEventListener('visibilitychange',function(){root.dataset.u1Hidden=String(document.hidden);if(document.hidden){cancelAnimationFrame(frame);frame=0;}else resume();});
    reduced.addEventListener('change',function(){if(window.U1)window.U1.reduced=still();resume();});
    window.addEventListener('u1:preferences',function(){if(window.U1)window.U1.reduced=still();if(engine)engine.resize();resume();});
    var hovered=null,depthFrame=0;
    function clearCard(){if(hovered){hovered.style.setProperty('--u1-tilt-x','0deg');hovered.style.setProperty('--u1-tilt-y','0deg');hovered.removeAttribute('data-hover');hovered=null;}}
    document.addEventListener('pointermove',function(e){if(still()||e.pointerType==='touch')return;var card=e.target.closest('.card,.u1-quick-actions button');if(!card){clearCard();return;}if(hovered!==card){clearCard();hovered=card;card.classList.add('u1-motion-card');card.dataset.hover='true';}if(depthFrame)return;var px=e.clientX,py=e.clientY;depthFrame=requestAnimationFrame(function(){depthFrame=0;if(!hovered)return;var r=hovered.getBoundingClientRect();hovered.style.setProperty('--u1-tilt-x',(((py-r.top)/r.height-.5)*-3).toFixed(2)+'deg');hovered.style.setProperty('--u1-tilt-y',(((px-r.left)/r.width-.5)*3).toFixed(2)+'deg');});},{passive:true});
    window.addEventListener('u1:navigate',function(e){clearCard();var view=document.getElementById('v-'+e.detail.id);if(view&&!still())view.animate([{opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'none'}],{duration:350,easing:'cubic-bezier(.16,1,.3,1)'});});
    var mq=matchMedia('(max-width:700px)'),button=document.getElementById('u1-menu-toggle'),rail=document.getElementById('rail'),scrim=document.getElementById('u1-nav-scrim');
    function menu(open){document.body.classList.toggle('u1-nav-open',open);button.setAttribute('aria-expanded',String(open));button.setAttribute('aria-label',open?'Close navigation':'Open navigation');scrim.hidden=!open;rail.inert=mq.matches&&!open;}
    button.addEventListener('click',function(){menu(!document.body.classList.contains('u1-nav-open'));});scrim.addEventListener('click',function(){menu(false);button.focus();});mq.addEventListener('change',function(){menu(false);});window.addEventListener('u1:navigate',function(){menu(false);});document.addEventListener('keydown',function(e){if(e.key==='Escape')menu(false);});menu(false);resume();
  }
  window.U1Motion={start:startMotion,isReduced:still};
})();
