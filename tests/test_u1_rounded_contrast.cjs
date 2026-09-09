/* Static CSS/token regressions only. No browser, provider, network or account I/O. */
'use strict';
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const assert = require('node:assert/strict');
const test = require('node:test');
const css = readFileSync(resolve(__dirname, '../static/css/u1-rounded-system.css'), 'utf8');
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(match => ({
  selector: match[1].replace(/\/\*[\s\S]*?\*\//g, '').trim(),
  declarations: Object.fromEntries(match[2].split(';').map(item => {
    const colon = item.indexOf(':');
    return colon < 0 ? null : [item.slice(0, colon).trim(), item.slice(colon + 1).trim()];
  }).filter(Boolean))
}));
const declarations = selector => Object.assign({}, ...rules.filter(rule => rule.selector === selector).map(rule => rule.declarations));
const rounded = 'html[data-u1-rounded="true"]';
const life = `${rounded} .u1-life-actions .u1-life-button`;
const enabled = ':not(:disabled):not([aria-disabled="true"])';
const interactive = ':is(:hover,:focus-visible)';
const secondary = `${rounded} .u1-create-earn .ce-button:not(.ce-primary)${enabled}${interactive}`;
const primary = `${rounded} .u1-create-earn .ce-button.ce-primary${enabled}${interactive}`;
const groupDeclarations = selector => Object.assign({}, ...rules.filter(rule => rule.selector.includes(selector)).map(rule => rule.declarations));
function luminance(hex) {
  assert.match(hex, /^#[0-9a-f]{6}$/i);
  const channels = [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function contrast(foreground, background) {
  const first = luminance(foreground), second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}
for (const theme of ['default', 'graphite', 'daylight']) {
  const tokens = {...declarations(':root'), ...declarations(`html[data-u1-widget-theme="${theme}"]`)};
  test(`${theme}: related/control text and usage accents meet 4.5:1`, () => {
    for (const [foreground, background] of [['text', 'raised'], ['text', 'surface'], ['muted', 'raised'], ['muted', 'surface'], ['accent', 'surface'], ['on-accent', 'accent']]) {
      const ratio = contrast(tokens[`--u1r-${foreground}`], tokens[`--u1r-${background}`]);
      assert(ratio >= 4.5, `${foreground}/${background}: ${ratio.toFixed(2)}:1`);
    }
  });
  test(`${theme}: focus accent meets 3:1 against control and surrounding surface`, () => {
    for (const background of ['raised', 'surface']) {
      assert(contrast(tokens['--u1r-accent'], tokens[`--u1r-${background}`]) >= 3);
    }
  });
}
test('related links explicitly pair theme foreground and background', () => {
  const rule = declarations(life);
  assert.equal(rule.background, 'var(--u1r-raised)');
  assert.equal(rule.color, 'var(--u1r-text)');
  assert.equal(rule['-webkit-text-fill-color'], 'currentColor');
});
test('neutral and primary hover/focus each keep matching semantic color pairs', () => {
  const neutral = groupDeclarations(secondary), accent = declarations(primary);
  assert.equal(neutral.background, 'var(--u1r-raised)');
  assert.equal(neutral.color, 'var(--u1r-text)');
  assert.equal(accent.background, 'var(--u1r-accent)');
  assert.equal(accent.color, 'var(--u1r-on-accent)');
  assert(rules.some(rule => rule.selector.includes(`${life}${enabled}${interactive}`)));
});
test('usage percentages inherit the theme accent, not legacy pale cyan', () => {
  const rule = declarations(`${rounded} #u1-usage-chips strong`);
  assert.equal(rule.color, 'var(--u1r-accent)');
  assert.equal(rule['-webkit-text-fill-color'], 'currentColor');
  assert.equal(declarations(`${rounded} #u1-usage-chips`).color, 'var(--u1r-text)');
});
test('new interaction rules exclude disabled controls and retain visible keyboard focus', () => {
  const block = css.split('/* Rounded action contrast:')[1].split('/* End rounded action contrast. */')[0];
  const selectors = block.slice(block.indexOf('*/') + 2).match(/[^{}]+(?=\{)/g);
  for (const selector of selectors) {
    if (!selector.includes(':hover') && !selector.includes(':focus-visible')) continue;
    const instances = selector.match(/\.u1-life-button|\.ce-button/g) || [];
    assert.equal((selector.match(/:not\(:disabled\):not\(\[aria-disabled="true"\]\)/g) || []).length, instances.length);
  }
  assert.equal(groupDeclarations(`${life}${enabled}:focus-visible`).outline, '3px solid var(--u1r-accent)');
  assert(!/(?:opacity|cursor|pointer-events|display|animation|transition)\s*:/.test(block));
});
test('contrast repair stays scoped away from navigation, boot and Safety overlays', () => {
  const block = css.split('/* Rounded action contrast:')[1].split('/* End rounded action contrast. */')[0];
  assert(!/!important|#boot|safety|\.navitem|\.rail|\.shell|\bbody\b/i.test(block));
  const selectors = block.slice(block.indexOf('*/') + 2).match(/[^{}]+(?=\{)/g);
  for (const selector of selectors) {
    assert(selector.trim().startsWith(rounded));
    assert(/\.u1-life-actions|\.u1-create-earn/.test(selector));
  }
});
const studio = `${rounded} .u1-native-workspace.u1-studio-pro`;
test('Home brief and activity surfaces explicitly pair rounded gradient with readable ink', () => {
  for (const name of ['u1-home-brief', 'u1-activity-card']) {
    const rule = groupDeclarations(`${rounded} .card.${name}`);
    assert.equal(rule.background, 'linear-gradient(135deg,var(--u1r-raised),var(--u1r-surface))!important');
    assert.equal(rule.color, 'var(--u1r-text)');
    assert.equal(rule['border-color'], 'var(--u1r-edge)');
  }
});
test('Home information-card override has exactly two surface selectors and no descendants', () => {
  const rule = rules.find(rule => rule.selector.includes(`${rounded} .card.u1-home-brief`));
  assert.deepEqual(rule.selector.split(',').map(selector => selector.trim()), [
    `${rounded} .card.u1-home-brief`, `${rounded} .card.u1-activity-card`
  ]);
  assert.deepEqual(Object.keys(rule.declarations).sort(), ['background', 'border-color', 'color']);
});
test('Studio interface tokens follow rounded themes without replacing artwork accent', () => {
  const rule = declarations(studio);
  for (const [local, shared] of [['paper', 'bg'], ['ink', 'text'], ['muted', 'muted'], ['line', 'edge'], ['ui-accent', 'accent'], ['surface', 'surface'], ['raised', 'raised']]) {
    assert.equal(rule[`--sp-${local}`], `var(--u1r-${shared})`);
  }
  assert.equal(rule['--sp-accent'], undefined);
  assert.equal(rule['color-scheme'], 'inherit');
  assert.equal(declarations(`${rounded}[data-u1-widget-theme="daylight"] .u1-native-workspace.u1-studio-pro :is(input,textarea,select)`)['color-scheme'], 'light');
});
test('Studio secondary controls have matching base and enabled hover/focus colors', () => {
  const base = declarations(`${studio} button:not(.sp-primary)`);
  const interaction = declarations(`${studio} button:not(.sp-primary)${enabled}${interactive}`);
  assert.equal(base.background, 'linear-gradient(135deg,var(--u1r-raised),var(--u1r-surface))');
  assert.equal(base.color, 'var(--u1r-text)');
  assert.equal(interaction.background, 'var(--u1r-raised)');
  assert.equal(interaction.color, 'var(--u1r-text)');
  assert.equal(interaction['-webkit-text-fill-color'], 'currentColor');
});
test('Studio panel and normal status backgrounds no longer retain navy literals', () => {
  const panel = declarations(`${studio} .sp-workbench`);
  const status = declarations(`${studio} .sp-status:not([data-error="true"])`);
  assert.equal(panel.background, 'linear-gradient(135deg,var(--u1r-surface),var(--u1r-raised))');
  assert.equal(status.background, 'var(--u1r-raised)');
  assert.equal(status.color, 'var(--u1r-text)');
  assert.equal(status['border-left-color'], 'var(--u1r-accent)');
});
test('Studio selected outline retains a distinct selection indicator', () => {
  const selected = declarations(`${studio} .sp-outline li>button[aria-current="true"]`);
  assert.equal(selected['box-shadow'], 'inset 3px 0 var(--u1r-accent)');
  assert.equal(selected.color, 'var(--u1r-text)');
});
test('Studio empty placeholder overrides legacy important text without targeting documents', () => {
  const empty = `${studio} .sp-preview-empty[data-empty]`;
  assert.equal(declarations(empty).color, 'var(--u1r-text)!important');
  assert.equal(declarations(`${empty} b`).color, 'var(--u1r-text)!important');
  assert.equal(declarations(`${empty} p`).color, 'var(--u1r-muted)!important');
  assert.equal(declarations(`${empty} p`)['-webkit-text-fill-color'], 'currentColor!important');
});
test('Studio repair does not change layout, motion, disabled states, artwork or viewer selectors', () => {
  const block = css.split('/* Rounded Studio chrome:')[1].split('/* End rounded Studio chrome. */')[0];
  assert(!/\.sp-art|\.sp-pdf-page|\[data-pdf\]|\biframe\b|\bcanvas\b|#boot|safety|\.navitem/.test(block));
  assert(!/(?:opacity|cursor|pointer-events|display|animation|transition|width|height|overflow)\s*:/.test(block));
  assert(!/\.sp-status\[data-error/.test(block));
  for (const rule of rules.filter(rule => rule.selector.startsWith(studio))) {
    if (Object.values(rule.declarations).some(value => value.includes('!important'))) {
      assert(rule.selector.includes('.sp-preview-empty[data-empty]'));
    }
  }
});
const phoneBlock = css.split('/* Compact phone utilities;')[1].split('/* End compact phone utilities. */')[0];
test('compact utilities are phone-only and do not modify dock or positioning ownership', () => {
  assert(phoneBlock.includes('@media(max-width:600px){'));
  assert(!/\.dock|z-index\s*:|(?:^|[;{\s])(?:top|bottom|position|height|max-height)\s*:|animation\s*:|transition\s*:/.test(phoneBlock));
  assert(!/\.rail|#boot|safety/i.test(phoneBlock));
});
test('phone shelf places usage and the Media opener on one row', () => {
  const shelf = declarations(`${rounded} #u1-utility-shelf`);
  const usage = declarations(`${rounded} #u1-usage-chips`);
  const media = declarations(`${rounded} #u1-utility-shelf>#u1-player-entry[aria-label^="Media"]`);
  assert.equal(shelf.display, 'grid');
  assert.equal(shelf['grid-template-columns'], 'minmax(0,1fr) auto');
  assert.equal(usage['grid-row'], '1');
  assert.equal(media['grid-row'], '1');
  assert.equal(media['grid-column'], '2');
  assert.equal(declarations(`${rounded} #u1-utility-shelf>.u1-utility-controls`).display, 'none');
});
test('compact visible Media label is gated by the existing full accessible Media name', () => {
  const media = `${rounded} #u1-utility-shelf>#u1-player-entry[aria-label^="Media"]`;
  assert.equal(declarations(media)['font-size'], '0');
  assert.equal(declarations(`${media}::after`).content, '"Media"');
  assert.equal(declarations(`${media}::after`)['font-size'], '11px');
  assert(!/aria-hidden|data-u1-redundant-entry|\[hidden\]/.test(phoneBlock));
});
test('only closed Spotify summary is compacted and active local media is not hidden', () => {
  const summary = `${rounded} aside[aria-label="Spotify account playback"]>details:not([open])>summary`;
  assert.equal(declarations(summary).display, 'list-item');
  assert.equal(declarations(summary)['white-space'], 'nowrap');
  assert.equal(declarations(summary)['list-style-position'], 'inside');
  assert.equal(declarations(`${summary}>span`).display, 'inline');
  const player = declarations(`${rounded} #u1-utility-shelf>#u1-player-mini`);
  assert.equal(player['grid-column'], '1/-1');
  assert.equal(player.display, undefined);
  assert(!/data-spotify-content|data-spotify-message|#u1-local-media|details\[open\]/.test(phoneBlock));
});
const daylight = `${rounded}[data-u1-widget-theme="daylight"]`;
const aiHeader = `${daylight} #body-ai>header.u1-core-header`;
const aiSource = `${daylight} #body-ai>div.u1-core-source[data-ai-provider]`;
const mediaHeader = `${daylight} .u1-mr .u1-mr-heading`;
const mediaNav = `${daylight} .u1-mr .u1-mr-nav`;
test('Daylight AI header has explicit readable title, subtitle and eyebrow colors', () => {
  assert.equal(declarations(`${aiHeader} h2`).color, 'var(--u1r-text)');
  assert.equal(declarations(`${aiHeader} p`).color, 'var(--u1r-muted)');
  assert.equal(declarations(`${aiHeader} .u1-core-eyebrow`).color, 'var(--u1r-accent)');
  for (const suffix of [' h2', ' p', ' .u1-core-eyebrow']) {
    assert.equal(declarations(aiHeader + suffix)['-webkit-text-fill-color'], 'currentColor');
  }
});
test('Daylight AI provider notice pairs native semantic ink with a matching surface', () => {
  const source = groupDeclarations(aiSource);
  assert.equal(source['--u1-core-ink'], 'var(--u1r-text)');
  assert.equal(source['--u1-core-muted'], 'var(--u1r-muted)');
  assert.equal(source.background, 'var(--u1r-raised)');
  assert.equal(source.color, 'var(--u1r-text)');
});
test('Media palette bridge is local to header and sidebar, not the dark work area', () => {
  const bridge = rules.find(rule => rule.selector === `${mediaHeader},\n${mediaNav}`);
  assert(bridge);
  for (const [local, shared] of [['ink', 'text'], ['muted', 'muted'], ['accent', 'accent'], ['line', 'edge']]) {
    assert.equal(bridge.declarations[`--mr-${local}`], `var(--u1r-${shared})`);
  }
  assert.equal(declarations(`${daylight} .u1-mr`)['--mr-ink'], undefined);
});
test('Daylight Media title, subtitle and eyebrow explicitly use semantic colors', () => {
  assert.equal(declarations(`${mediaHeader} h1`).color, 'var(--u1r-text)');
  assert.equal(declarations(`${mediaHeader}>p`).color, 'var(--u1r-muted)');
  assert.equal(declarations(`${mediaHeader}>p.u1-mr-eyebrow`).color, 'var(--u1r-accent)');
});
test('Daylight Media sidebar subtitles and selected controls retain readable state distinctions', () => {
  assert.equal(declarations(`${mediaNav} button`).background, 'var(--u1r-raised)');
  assert.equal(declarations(`${mediaNav} button`).color, 'var(--u1r-text)');
  assert.equal(declarations(`${mediaNav} button span`).color, 'var(--u1r-muted)');
  assert.equal(declarations(`${mediaNav} button${enabled}${interactive}`)['border-color'], 'var(--u1r-accent)');
  const selected = declarations(`${mediaNav} button[aria-current]:not([aria-current="false"])`);
  assert.equal(selected.color, 'var(--u1r-text)');
  assert.equal(selected['box-shadow'], 'inset 3px 0 var(--u1r-accent)');
});
test('native route correction stays Daylight-only and excludes work panels and media content', () => {
  const block = css.split('/* Daylight native route chrome;')[1].split('/* End Daylight native route chrome. */')[0];
  const selectors = block.slice(block.indexOf('*/') + 2).match(/[^{}]+(?=\{)/g);
  for (const selector of selectors) {
    for (const item of selector.trim().split(',\n')) assert(item.startsWith(daylight));
  }
  assert(!/\.u1-ai-layout|\.u1-ai-composer|\.u1-ai-message|\.u1-mr-card|\.u1-mr-player|#u1-local-media|\bvideo\b|\bcanvas\b|\biframe\b|\.sp-art/.test(block));
  assert(!/(?:opacity|cursor|pointer-events|display|animation|transition|z-index)\s*:/.test(block));
  assert(!/!important|#boot|safety|\.dock|\.rail/.test(block));
});
