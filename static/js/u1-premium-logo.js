/* U1 OS owned identity. Provider marks keep their separate brand colours. */
let sequence = 0;
export function mark() {
  const id = `u1-premium-${++sequence}`;
  return `<svg class="u1-brand-mark u1-premium-mark" viewBox="0 0 128 128" fill="none" aria-hidden="true" focusable="false"><defs><linearGradient id="${id}-u" x1="24" y1="20" x2="88" y2="114" gradientUnits="userSpaceOnUse"><stop stop-color="#b0ffff"/><stop offset=".42" stop-color="#42e4ff"/><stop offset="1" stop-color="#2471ff"/></linearGradient><linearGradient id="${id}-one" x1="83" y1="18" x2="109" y2="113" gradientUnits="userSpaceOnUse"><stop stop-color="#ffffff"/><stop offset=".6" stop-color="#dcefff"/><stop offset="1" stop-color="#8dbaff"/></linearGradient></defs><path d="M18 27h19v51c0 11 5 17 15 17s15-6 15-17V48l19-14v45c0 23-13 36-34 36S18 102 18 79V27Z" fill="url(#${id}-u)"/><path d="m66 37 26-20h17v98H90V44L66 62V37Z" fill="url(#${id}-one)"/><path d="M21 29h13v48c0 13 6 20 18 20" stroke="#d4ffff" stroke-opacity=".7" stroke-width="1.3"/><path d="m69 38 24-18h13" stroke="white" stroke-width="1.3"/><path d="M18 82c1 22 14 33 34 33 15 0 27-8 32-20-9 8-17 12-29 12-17 0-29-9-37-25Z" fill="#164bbe" opacity=".4"/></svg>`;
}
if (typeof document !== 'undefined' && !document.getElementById('u1-premium-identity')) {
  const style = document.createElement('link');
  style.id = 'u1-premium-identity';
  style.rel = 'stylesheet';
  style.href = '/css/u1-premium-identity.css';
  document.head.append(style);
}
