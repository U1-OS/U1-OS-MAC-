/* Decorative renderer. Archived Earth texture: NASA/GSFC via Wikimedia.
 * Attribution and image license are documented in docs/PRISM-OS.md. */
export function mountGlobe(canvas, effects = 'balanced') {
  if (!canvas) return () => {};
  const gl = canvas.getContext('webgl', {alpha:true, premultipliedAlpha:false, antialias:false, powerPreference:'low-power'});
  if (!gl) { canvas.classList.add('globe-fallback'); return () => {}; }
  let stopped=false, frame=0, previous=0, ready=false, visible=true, phase=.53, pointer=0;
  const motion=matchMedia('(prefers-reduced-motion: reduce)'),shaders=[];
  const vertex='attribute vec2 a_position;varying vec2 uv;void main(){uv=a_position*.5+.5;gl_Position=vec4(a_position,0.,1.);}';
  const fragment=`precision mediump float;varying vec2 uv;uniform sampler2D u_earth;uniform float u_rotation;uniform float u_tilt;
    void main(){vec2 p=(uv-.5)*2.3;float r=length(p);vec3 blue=vec3(.025,.57,1.);
    if(r>1.){gl_FragColor=vec4(blue,exp(-(r-1.)*23.)*.42);return;}
    vec3 normal=normalize(vec3(p,sqrt(max(0.,1.-dot(p,p)))));float ct=cos(u_tilt),st=sin(u_tilt);
    vec3 n=vec3(normal.x*ct-normal.y*st,normal.x*st+normal.y*ct,normal.z);
    vec2 map=vec2(fract(atan(n.z,n.x)/6.2831853+.5+u_rotation),asin(clamp(n.y,-1.,1.))/3.14159265+.5);
    vec3 earth=texture2D(u_earth,map).rgb;float daylight=max(0.,dot(normal,normalize(vec3(-.6,.35,.82))));
    vec3 color=earth*(.13+daylight*.95);color=mix(color,color*vec3(.72,1.04,1.42),.52);
    color+=blue*pow(1.-normal.z,3.2)*.82+vec3(.2,.82,1.)*pow(1.-normal.z,9.);gl_FragColor=vec4(color,1.);}`;
  function compile(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error('Globe shader unavailable');shaders.push(shader);return shader;}
  let program,buffer,texture;
  try {program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Globe unavailable');gl.useProgram(program);
    buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);const a=gl.getAttribLocation(program,'a_position');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
    texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([8,48,89,255]));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  }catch(_){canvas.classList.add('globe-fallback');return()=>{shaders.forEach(s=>gl.deleteShader(s));if(program)gl.deleteProgram(program);};}
  const rotation=gl.getUniformLocation(program,'u_rotation'),tilt=gl.getUniformLocation(program,'u_tilt');
  function resize(){const bounds=canvas.getBoundingClientRect(),scale=Math.min(devicePixelRatio||1,effects==='maximum'?2:1.5),size=Math.min(1100,Math.max(250,Math.round(bounds.width*scale)));if(canvas.width!==size||canvas.height!==size){canvas.width=size;canvas.height=size;gl.viewport(0,0,size,size);}}
  function draw(timestamp){if(stopped)return;resize();if(ready){if(timestamp&&previous&&effects!=='reduced'&&!motion.matches)phase+=Math.min(timestamp-previous,100)/1000*.006;gl.uniform1f(rotation,phase+pointer*.012);gl.uniform1f(tilt,-.16);gl.drawArrays(gl.TRIANGLES,0,6);}previous=timestamp;}
  const image=new Image();image.onload=()=>{if(stopped)return;gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);ready=true;draw(0);};image.onerror=()=>canvas.classList.add('globe-fallback');image.src='/assets/prism-earth.jpg';
  function tick(timestamp){if(stopped)return;frame=requestAnimationFrame(tick);if(document.hidden||!visible||motion.matches||effects==='reduced'||timestamp-previous<(effects==='maximum'?16:32))return;draw(timestamp);}
  const observer=new ResizeObserver(()=>draw(0));observer.observe(canvas);const intersection=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting!==false;});intersection.observe(canvas);
  const move=event=>{if(effects==='reduced'||motion.matches)return;const rect=canvas.getBoundingClientRect();pointer=(event.clientX-rect.left)/rect.width-.5;};canvas.addEventListener('pointermove',move);const preference=()=>draw(0);motion.addEventListener('change',preference);frame=requestAnimationFrame(tick);
  return()=>{stopped=true;cancelAnimationFrame(frame);observer.disconnect();intersection.disconnect();canvas.removeEventListener('pointermove',move);motion.removeEventListener('change',preference);image.onload=null;image.onerror=null;gl.deleteTexture(texture);gl.deleteBuffer(buffer);shaders.forEach(shader=>gl.deleteShader(shader));gl.deleteProgram(program);};
}
