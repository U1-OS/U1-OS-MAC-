export {icon, mark, badge} from './u1-icons.js';
import {icon} from './u1-icons.js';
export const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const bytes=value=>{if(!Number.isFinite(value))return 'Unavailable';const units=['B','KB','MB','GB','TB'];let n=Math.max(0,value),i=0;while(n>=1024&&i<4){n/=1024;i++;}return `${n.toFixed(i===0?0:n<10?1:0)} ${units[i]}`;};
export const empty=(title,description,action='')=>`<div class="prism-empty">${icon('ai')}<strong>${escape(title)}</strong><p>${escape(description)}</p>${action}</div>`;
export const action=(label,route,style='quiet')=>`<button type="button" class="prism-button ${style}" data-route="${escape(route)}">${escape(label)}${icon('arrow')}</button>`;
export const panel=(title,body,actionHtml='',kind='')=>`<section class="prism-panel ${kind}"><header><h2>${icon(kind||'ai')}${escape(title)}</h2>${actionHtml}</header>${body}</section>`;
