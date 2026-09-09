# U1 animation system

`u1-cinematic.js` owns the active ambient renderer. The older stars/dot-Earth
loops are not started. Archived day/night textures are projected onto a shaded
WebGL sphere; orbital lines and light nodes are explicitly decorative.

- Micro transitions: 150 ms. Panel transitions: 280-350 ms. Boot reveal: 650-800 ms.
- Pointer tilt is bounded to approximately 1.5 degrees each way.
- Auto, Ultra, High, Balanced and Low-power options are available. Ultra and
  High currently share the same DPR ceiling; they are not different renderers.
- DPR is capped, backing textures are budgeted to a 2048-pixel maximum edge,
  and Auto lowers backing resolution after sustained slow frames.
- Rendering stops when hidden or off-screen. Low-power and reduced-motion
  modes keep the Earth static. A static texture remains if WebGL cannot load.
- System reduced-motion preferences always take precedence over app settings.

No FPS guarantee is made without measurement on the target hardware. Boot
completion comes from real requests with a 2.8-second usability ceiling, not a
fake success timer. Enter workspace and Skip startup bypass the visual delay.
