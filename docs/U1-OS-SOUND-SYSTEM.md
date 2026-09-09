# U1 sound system

The existing Web Audio synthesiser is retained. It covers navigation, open,
close, success, warning, error, notifications and focus actions. No synthetic
audio value is used as operational telemetry.

New profiles default to muted with a low configured volume. Existing explicit
sound preferences are preserved. Audio context creation requires a prior user
activation where the browser exposes that signal. Startup no longer fires an
unconditional boot sound.

Sound can be toggled in the top bar; volume is available in Settings. Separate
notification/interface/AI mix controls and microphone-reactive listening are
not implemented by this pass. The AI orb does not claim to be listening.
