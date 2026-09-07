/* Original U1 interface glyphs. Brand identifiers remain visually distinct. */
const glyphs = {
  home:'<path d="m3 10 9-7 9 7M5 9v12h14V9"/><path d="M9 21v-8h6v8"/>',
  ai:'<path d="m12 3 3.1 5.9L21 12l-5.9 3.1L12 21l-3.1-5.9L3 12l5.9-3.1L12 3Z"/><circle cx="12" cy="12" r="2.1"/>',
  projects:'<path d="M3 7V4h7l3 3h8v13H3V7Zm0 3h18"/><path d="M7 14h4m-4 3h8"/>',
  files:'<path d="M5 3h9l5 5v13H5V3Z"/><path d="M14 3v6h5M8 13h8m-8 4h6"/>',
  integrations:'<rect x="3" y="3" width="6" height="6" rx="2"/><rect x="15" y="15" width="6" height="6" rx="2"/><path d="M9 6h5a4 4 0 0 1 4 4v5M6 9v5a4 4 0 0 0 4 4h5"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18m-14 4h2m4 0h2m-8 3h2"/>',
  tasks:'<path d="M11 3H4v18h16v-8M8 11l4 4L22 4"/><path d="M8 18h6"/>',
  notes:'<path d="M11 3H4v18h16v-8M14 5l5 5m-10 7 1-5L19 3l3 3-9 9-4 2Z"/>',
  media:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="m10 9 5 3.5-5 3.5V9Zm-3-7h10"/>',
  automation:'<path d="m13 2-9 12h7l-1 8L21 9h-8l0-7Z"/><path d="M4 4 2 6m18 12 2 2"/>',
  system:'<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 9h6v6H9V9ZM8 2v3m8-3v3M8 19v3m8-3v3M2 8h3m-3 8h3m14-8h3m-3 8h3"/>',
  settings:'<path d="m10 2 4 0 1 3 3 1 3 3-1 3 1 3-3 3-3 1-1 3h-4l-1-3-3-1-3-3 1-3-1-3 3-3 3-1 1-3Z"/><circle cx="12" cy="12" r="3.5"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
  bell:'<path d="M18 9a6 6 0 0 0-12 0c0 6-3 6-3 9h18c0-3-3-3-3-9M10 22h4M12 1v2"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  plus:'<path d="M12 4v16M4 12h16"/>', arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  external:'<path d="M14 3h7v7m0-7L10 14M9 4H3v17h17v-6"/>', close:'<path d="m6 6 12 12M6 18 18 6"/>',
  menu:'<path d="M4 6h16M4 12h12M4 18h16"/>',
  globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/>',
  cloud:'<path d="M6 19a5 5 0 0 1-1-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1 0 11H6Z"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
  moon:'<path d="M20 15A9 9 0 0 1 9 3a9 9 0 1 0 11 12Z"/>',
  rain:'<path d="M5 14a4 4 0 0 1 0-8 6 6 0 0 1 11-1 4.5 4.5 0 0 1 2 9M7 17l-2 4m8-4-2 4m8-4-2 4"/>',
  shield:'<path d="m12 2 9 4v6c0 5-5 8-9 10-4-2-9-5-9-10V6l9-4Z"/><path d="m7 12 3 3 7-7"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>', upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  trash:'<path d="M3 6h18M9 3h6M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  restore:'<path d="M3 4v6h6M3 10a9 9 0 1 1 2 9M12 7v6l4 2"/>',
  code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
  mail:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="m3 6 9 7 9-7"/>',
  check:'<path d="m4 12 5 5L21 5"/>'
};
export const icon = name => `<svg class="u1-glyph u1-glyph-${glyphs[name]?name:'ai'}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${glyphs[name]||glyphs.ai}</svg>`;
export {mark} from './u1-premium-logo.js';
const brandSVG = (body, box='0 0 48 48') => `<svg viewBox="${box}" fill="none" aria-hidden="true">${body}</svg>`;
export function badge(name) {
  const id = String(name).toLowerCase();
  if (id === 'claude') return `<span class="prism-provider-mark claude-mark">${brandSVG('<g stroke="currentColor" stroke-width="3.5" stroke-linecap="round"><path d="M24 3v42M3 24h42M9 9l30 30M9 39 39 9M15 4l18 40M4 15l40 18M4 33l40-18M15 44 33 4"/></g>')}</span>`;
  if (id === 'canva') return '<span class="prism-provider-mark canva-mark" aria-hidden="true">C</span>';
  if (id === 'antigravity') return `<span class="prism-provider-mark antigravity-mark">${brandSVG('<path d="m24 4 20 38-11-5-9-20-9 20-11 5L24 4Z" fill="#aa8cff"/><path d="M24 4 4 42l11-5 9-20V4Z" fill="#49dfff"/><path d="m24 4 9 33 11 5L24 4Z" fill="#d8b9ff"/>')}</span>`;
  if (['codex','chatgpt','openai'].includes(id)) return `<span class="prism-provider-mark codex-mark">${brandSVG('<g stroke="currentColor" stroke-width="2.2"><path d="M24 5 40 14v20l-16 9-16-9V14l16-9Z"/><path d="m24 5 0 13 16-4M40 34l-12-7-4 16M8 34l12-7-12-13M24 18l4 9-8 0 4-9Z"/></g>')}</span>`;
  if (id === 'google_drive') return `<span class="prism-provider-mark drive-mark">${brandSVG('<path d="m17 4 12 0 15 26H32L17 4Z" fill="#f7c63c"/><path d="M17 4 3 29l6 11L23 15 17 4Z" fill="#27c78c"/><path d="M9 40h29l6-10H15L9 40Z" fill="#4a93fc"/>')}</span>`;
  if (id === 'github') return `<span class="prism-provider-mark github-mark">${brandSVG('<path d="M12 15 10 5l11 6h6l11-6-2 10c4 3 6 7 6 12 0 11-8 15-18 15S6 38 6 27c0-5 2-9 6-12Z" fill="#e9f2ff"/><path d="M17 29v4m14-4v4M18 38l-1 8m13-8 1 8" stroke="#092039" stroke-width="3" stroke-linecap="round"/>')}</span>`;
  if (id === 'gmail') return `<span class="prism-provider-mark gmail-mark">${brandSVG('<path d="M6 38V12l18 14 18-14v26" stroke="#e8eef6" stroke-width="7" stroke-linejoin="round"/><path d="M6 38V12l18 14 18-14v26" stroke="#ef665a" stroke-width="5" stroke-linejoin="round"/><path d="M6 24v14" stroke="#4a99ff" stroke-width="5"/><path d="M42 24v14" stroke="#43cb8f" stroke-width="5"/>')}</span>`;
  if (id === 'google_calendar') return `<span class="prism-provider-mark calendar-mark">${brandSVG('<rect x="6" y="7" width="36" height="36" rx="7" fill="#398cff"/><path d="M6 17h36M15 3v9m18-9v9" stroke="#b3e6ff" stroke-width="3"/><path d="M13 23h9v5h-6v5h7m9-10v11" stroke="white" stroke-width="3" stroke-linejoin="round"/>')}</span>`;
  if (id === 'slack') return `<span class="prism-provider-mark slack-mark">${brandSVG('<path d="M17 5v15M5 17h15" stroke="#38c9e7" stroke-width="7" stroke-linecap="round"/><path d="M31 5v15m-3-3h15" stroke="#43d391" stroke-width="7" stroke-linecap="round"/><path d="M31 28v15m-3-12h15" stroke="#efb84b" stroke-width="7" stroke-linecap="round"/><path d="M17 28v15M5 31h15" stroke="#ee5d8c" stroke-width="7" stroke-linecap="round"/>')}</span>`;
  if (id === 'notion') return '<span class="prism-provider-mark notion-mark" aria-hidden="true">N</span>';
  return `<span class="prism-provider-mark generic-mark">${icon('integrations')}</span>`;
}
