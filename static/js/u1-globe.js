/* U1's decorative Earth. Archived NASA imagery, not live satellite telemetry. */
export function mountGlobe(canvas, effects = 'balanced') {
  if (!canvas) return () => {};
  const gl = canvas.getContext('webgl', {alpha: true, premultipliedAlpha: false, antialias: false, powerPreference: 'low-power'});
  if (!gl) { canvas.classList.add('globe-fallback'); return () => {}; }
  let disposed = false, frame = 0, previous = 0, phase = .035, pointer = 0, visible = true, loaded = false;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const shaders = [], textures = [], images = [];
  const vertex = 'attribute vec2 position; varying vec2 uv; void main(){uv=position*.5+.5;gl_Position=vec4(position,0.,1.);}';
  const fragment = `precision mediump float;
    varying vec2 uv; uniform sampler2D earthDay; uniform sampler2D earthNight; uniform float rotation; uniform float parallax;
    void main(){
      vec2 p=(uv-.5)*2.26; float r=length(p); vec3 azure=vec3(.055,.59,1.);
      if(r>1.){float a=exp(-(r-1.)*55.)*.78;gl_FragColor=vec4(azure,a);return;}
      vec3 normal=normalize(vec3(p,sqrt(max(0.,1.-dot(p,p)))));
      float angle=-.13; vec3 n=vec3(normal.x*cos(angle)-normal.y*sin(angle),normal.x*sin(angle)+normal.y*cos(angle),normal.z);
      vec2 coord=vec2(fract(atan(n.z,n.x)/6.2831853+.5+rotation+parallax),asin(clamp(n.y,-1.,1.))/3.14159265+.5);
      vec3 day=texture2D(earthDay,coord).rgb; vec3 night=texture2D(earthNight,coord).rgb;
      float light=pow(max(0.,dot(normal,normalize(vec3(.86,.46,.32)))),1.7);
      float terrain=dot(day,vec3(.23,.58,.19));
      vec3 surface=day*vec3(.12,.35,.62)*(.22+light*1.7);
      surface+=vec3(.004,.018,.045)+vec3(.013,.045,.095)*terrain;
      float city=pow(max(0.,night.r-night.b*.62),1.65);
      surface+=vec3(1.,.72,.34)*city*(1.1-light*.55);
      float fresnel=pow(1.-normal.z,3.6);
      surface+=azure*fresnel*(.35+light*.75)+vec3(.3,.86,1.)*pow(1.-normal.z,13.)*.64;
      gl_FragColor=vec4(surface,1.);
    }`;
  let program, buffer;
  function shader(type, source) {
    const item = gl.createShader(type); shaders.push(item); gl.shaderSource(item, source); gl.compileShader(item);
    if (!gl.getShaderParameter(item, gl.COMPILE_STATUS)) throw new Error('Earth shader unavailable');
    return item;
  }
  function cleanup() {
    disposed = true; cancelAnimationFrame(frame); images.forEach(image => { image.onload = null; image.onerror = null; });
    textures.forEach(texture => gl.deleteTexture(texture)); shaders.forEach(item => gl.deleteShader(item));
    if (program) gl.deleteProgram(program); if (buffer) gl.deleteBuffer(buffer);
  }
  try {
    program = gl.createProgram(); gl.attachShader(program, shader(gl.VERTEX_SHADER, vertex)); gl.attachShader(program, shader(gl.FRAGMENT_SHADER, fragment)); gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Earth renderer unavailable');
    gl.useProgram(program); buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  } catch (_) { cleanup(); canvas.classList.add('globe-fallback'); return () => {}; }
  const rotation = gl.getUniformLocation(program, 'rotation'), parallax = gl.getUniformLocation(program, 'parallax');
  function resize() {
    const width = canvas.getBoundingClientRect().width, scale = Math.min(devicePixelRatio || 1, effects === 'maximum' ? 2 : 1.5);
    const size = Math.min(1200, Math.max(200, Math.round(width * scale)));
    if (canvas.width !== size || canvas.height !== size) { canvas.width = size; canvas.height = size; gl.viewport(0, 0, size, size); }
  }
  function draw(timestamp = 0) {
    if (disposed || !loaded) return;
    resize();
    if (timestamp && previous && effects !== 'reduced' && !motion.matches) phase += Math.min(timestamp - previous, 100) * .0000007;
    gl.uniform1f(rotation, phase); gl.uniform1f(parallax, pointer * .008); gl.drawArrays(gl.TRIANGLES, 0, 6); previous = timestamp;
  }
  function loadTexture(unit, uniform, source, primary) {
    const texture = gl.createTexture(); textures.push(texture); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0,0,0,255]));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.uniform1i(gl.getUniformLocation(program, uniform), unit);
    const image = new Image(); images.push(image);
    image.onload = () => { if (disposed) return; gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, texture); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image); if (primary) loaded = true; draw(); };
    image.onerror = () => { if (primary) canvas.classList.add('globe-fallback'); };
    image.src = source;
  }
  loadTexture(0, 'earthDay', '/assets/prism-earth.jpg', true);
  loadTexture(1, 'earthNight', '/assets/u1-earth-night.jpg', false);
  function tick(timestamp) {
    if (disposed) return;
    frame = requestAnimationFrame(tick);
    if (document.hidden || !visible || effects === 'reduced' || motion.matches) { previous = 0; return; }
    if (timestamp - previous >= (effects === 'maximum' ? 17 : 33)) draw(timestamp);
  }
  const observer = new ResizeObserver(() => draw()); observer.observe(canvas);
  const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting !== false; }); intersection.observe(canvas);
  const move = event => { if (effects !== 'reduced' && !motion.matches) { const rect = canvas.getBoundingClientRect(); pointer = (event.clientX - rect.left) / rect.width - .5; } };
  const preference = () => draw(); canvas.addEventListener('pointermove', move); motion.addEventListener('change', preference); frame = requestAnimationFrame(tick);
  return () => { observer.disconnect(); intersection.disconnect(); canvas.removeEventListener('pointermove', move); motion.removeEventListener('change', preference); cleanup(); };
}
