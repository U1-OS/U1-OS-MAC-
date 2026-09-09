"""Offline Discovery regression tests. No public requests or credentials."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from utils import u1_discovery as discovery


def rss(title='A real headline', url='https://www.theguardian.com/sport/story', date='Tue, 08 Sep 2026 08:00:00 GMT'):
    return ('<rss><channel><item><title>' + title + '</title><link>' + url + '</link><pubDate>' + date + '</pubDate></item></channel></rss>').encode()


class DiscoveryTests(unittest.TestCase):
    def test_catalogue_does_not_fetch(self):
        with patch.object(discovery, 'fetch_feed', side_effect=AssertionError('network')):
            result = discovery.handle_get({})
        self.assertTrue(result['read_only'])
        self.assertEqual(len(result['sources']), 6)

    def test_no_arbitrary_source_or_query(self):
        for query in ({'url': ['http://127.0.0.1']}, {'source': ['https://evil.test']}, {'source': ['afl', 'mma']}, {'source': 'afl'}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                discovery.handle_get(query)

    def test_parses_attribution_and_timestamp(self):
        result = discovery.parse_feed('afl', rss())
        self.assertEqual(result['items'][0]['source'], 'The Guardian / AFL')
        self.assertIsInstance(result['items'][0]['published_at'], float)
        self.assertNotIn('fetched_at', result)

    def test_missing_date_is_unknown(self):
        self.assertIsNone(discovery.parse_feed('afl', rss(date='not a date'))['items'][0]['published_at'])

    def test_xml_and_size_bounds(self):
        for body in (b'<!DOCTYPE rss><rss><channel/></rss>', b'<!ENTITY x "bad">', rss().decode().encode('utf-16'), b'x' * (discovery.MAX_BYTES + 1), b'<html/>'):
            with self.subTest(body=body[:20]), self.assertRaises((ValueError, UnicodeError)):
                discovery.parse_feed('afl', body)

    def test_links_reject_credentials_and_unsafe_hosts(self):
        for url in ('javascript:alert(1)', 'https://theguardian.com.evil.test/x', 'http://127.0.0.1', 'https://secret@www.theguardian.com/x', 'https://www.theguardian.com:1234/x', 'https://www.theguardian.com:bad/x'):
            with self.subTest(url=url):
                self.assertIsNone(discovery.safe_link(url, ('theguardian.com',)))

    def test_empty_is_not_live_match_status(self):
        result = discovery.parse_feed('afl', b'<rss><channel/></rss>')
        self.assertEqual(result['items'], [])
        self.assertNotIn('live', result)
        self.assertNotIn('match_status', result)

    def test_old_ufc_feed_is_flagged(self):
        result = discovery.parse_feed('mma', rss(date='Tue, 04 Aug 2026 20:15:58 GMT'))
        self.assertTrue(result['feed_age_warning'])
        self.assertIn('not all MMA', result['coverage'])

    def test_deduplicates_and_caps_items(self):
        item = '<item><title>Headline</title><link>https://www.theguardian.com/sport/{}</link></item>'
        body = ('<rss><channel>' + ''.join(item.format(i) for i in range(70)) + '</channel></rss>').encode()
        self.assertEqual(len(discovery.parse_feed('afl', body)['items']), 24)
        self.assertEqual(len(discovery.parse_feed('afl', rss().replace(b'</channel>', b'<item><title>Duplicate</title><link>https://www.theguardian.com/sport/story</link></item></channel>'))['items']), 1)

    def test_reuses_shared_snapshot(self):
        with patch.object(discovery.news_markets, 'snapshot', return_value={'success': False, 'stale': False}) as cache:
            result = discovery.handle_get({'source': ['boxing']})
        self.assertEqual(cache.call_args.args[:2], ('discovery:boxing', 300))
        self.assertEqual(result['items'], [])
        self.assertEqual(result['source'], 'The Guardian / Boxing')

    def test_cache_retains_actual_observation_on_failure(self):
        with patch.object(discovery.news_markets, 'CACHE', {}), patch.object(discovery.news_markets, 'KEY_LOCKS', {}), patch.object(discovery, 'fetch_feed', return_value=rss()):
            first = discovery.handle_get({'source': ['afl']})
            discovery.news_markets.CACHE['discovery:afl']['attempted_at'] = 0
            with patch.object(discovery, 'fetch_feed', side_effect=OSError('offline')):
                failed = discovery.handle_get({'source': ['afl']})
        self.assertFalse(failed['success'])
        self.assertTrue(failed['stale'])
        self.assertEqual(failed['fetched_at'], first['fetched_at'])
        self.assertEqual(failed['items'], first['items'])

    def test_redirects_are_rejected(self):
        with self.assertRaises(ValueError):
            discovery.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1')

    def test_javascript_pure_contract(self):
        root = Path(__file__).resolve().parents[1]
        script = """
const assert = require('node:assert/strict');
const api = require('./static/js/u1-discovery-workspace.js');
const routes = {}; api.register({register: (id, fn) => routes[id] = fn});
assert.deepEqual(Object.keys(routes), ['tech-gaming', 'sports-news']);
assert.equal(api.endpoint(api.topics['tech-gaming'][0]), '/api/workspace/live/news?category=technology');
assert.equal(api.endpoint(api.topics['sports-news'][0]), '/api/workspace/discovery?source=afl');
for (const url of ['javascript:alert(1)', 'data:text/html,bad', '/relative', 'https://key@evil.test']) assert.equal(api.safeURL(url), null);
assert.equal(api.date(null), 'Not supplied');
assert.equal(api.freshness({success: false}, Date.now()), 'Unavailable');
assert.equal(api.freshness({success: true, fetched_at: 1, items: []}, Date.now()), 'Stale snapshot');
assert.equal(api.freshness({success: true, fetched_at: Date.now()/1000, items: []}, Date.now()), 'No headlines returned');
assert.equal(api.freshness({success: true, items: []}, Date.now()), 'Timestamp unavailable');
assert.equal(api.entries({items:[{title:'AFL',url:'https://www.theguardian.com/sport/a'},{title:'bad',url:'javascript:x'}]}, 'afl').length, 1);
"""
        subprocess.run(['node', '-e', script], cwd=root, check=True, timeout=10, capture_output=True, text=True)

    def test_javascript_cached_view_lifecycle(self):
        root = Path(__file__).resolve().parents[1]
        script = r"""
const test = require('node:test'), assert = require('node:assert/strict');
const api = require('./static/js/u1-discovery-workspace.js');
const settle = () => new Promise(resolve => setImmediate(resolve));
const snapshot = (title = 'Fixture headline') => ({success:true,stale:false,fetched_at:Date.now()/1000,
  attempted_at:Date.now()/1000,refresh_seconds:300,source:'BBC News',
  items:[{id:title,title,url:'https://www.bbc.com/news/fixture',published_at:Date.now()/1000}]});
function fixture(deferred = false) {
  const routes = {}, requests = [], timers = new Set(), doc = {}; let timerID = 0;
  api.register({register(id, render, hooks) { routes[id] = {render,hooks}; }});
  class Element {
    constructor(tag) { this.tag=tag;this.ownerDocument=doc;this.children=[];this.dataset={};this.value='';this.attrs={};this.handlers={};this._text=''; }
    set textContent(value) { this._text=String(value);this.children=[]; }
    get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
    append(...nodes) { this.children.push(...nodes);if(this.tag==='select'&&!this.value&&nodes[0])this.value=nodes[0].value; }
    replaceChildren(...nodes) { this.children=nodes;this._text=''; }
    setAttribute(key,value) { this.attrs[key]=String(value); }
    addEventListener(type,handler) { this.handlers[type]=handler; }
  }
  doc.createElement=tag=>new Element(tag);
  doc.defaultView={AbortController,setTimeout(){timers.add(++timerID);return timerID;},clearTimeout(id){timers.delete(id);},fetch(url,options){
    let resolve;const promise=new Promise(done=>{resolve=done;});
    const request={url,signal:options.signal,complete(value){resolve({ok:true,json:async()=>value});}};
    requests.push(request);if(!deferred)request.complete(snapshot());return promise;
  }};
  const host=new Element('host');
  function flat(node=host) { return [node,...node.children.flatMap(flat)]; }
  return {routes,requests,timers,host,flat};
}
test('both Discovery routes register host-scoped lifecycle hooks',()=>{
  const f=fixture();for(const id of ['tech-gaming','sports-news']) {
    assert.equal(typeof f.routes[id].hooks.activate,'function');assert.equal(typeof f.routes[id].hooks.deactivate,'function');
  }
});
test('cached reentry preserves root, topic and filter while updating freshness without another request',async()=>{
  const f=fixture(), route=f.routes['tech-gaming'];route.render(f.host);await settle();
  const root=f.host.children[0], select=f.flat().find(n=>n.tag==='select'), search=f.flat().find(n=>n.tag==='input');
  select.value='xbox';await select.handlers.change();search.value='Fixture';search.handlers.input();
  route.hooks.deactivate(f.host);const calls=f.requests.length, original=Date.now, later=Date.now()+601000;
  try { Date.now=()=>later;await route.hooks.activate(f.host); } finally { Date.now=original; }
  assert.equal(f.host.children[0],root);assert.equal(f.flat().find(n=>n.tag==='select'),select);assert.equal(select.value,'xbox');
  assert.equal(f.flat().find(n=>n.tag==='input'),search);assert.equal(search.value,'Fixture');
  assert.match(f.host.textContent,/Stale snapshot/);assert.equal(f.requests.length,calls);
});
test('exit or Safety-lock deactivation aborts pending work, clears loading and ignores late completion',async()=>{
  const f=fixture(true), route=f.routes['tech-gaming'];route.render(f.host);
  assert.equal(f.timers.size,1);route.hooks.deactivate(f.host);
  assert.equal(f.requests[0].signal.aborted,true);assert.equal(f.timers.size,0);
  assert.equal(f.flat().find(n=>n.tag==='button').disabled,false);
  assert.equal(f.flat().find(n=>n.className==='u1-discovery-grid').attrs['aria-busy'],'false');
  f.requests[0].complete(snapshot('Discard this late result'));await settle();
  assert.doesNotMatch(f.host.textContent,/Discard this late result/);assert.equal(f.requests.length,1);
});
test('reentry resumes only interrupted work and repeated activation cannot duplicate it',async()=>{
  const f=fixture(true), route=f.routes['sports-news'];route.render(f.host);route.hooks.deactivate(f.host);
  const activation=route.hooks.activate(f.host);route.hooks.activate(f.host);assert.equal(f.requests.length,2);
  f.requests[1].complete(snapshot('Current fixture'));await activation;
  f.requests[0].complete(snapshot('Old fixture'));await settle();
  assert.match(f.host.textContent,/Current fixture/);assert.doesNotMatch(f.host.textContent,/Old fixture/);assert.equal(f.timers.size,0);
});
test('hooks do not deactivate a different cached host',async()=>{
  const f=fixture(true), first=f.host, second=new first.constructor('host');
  const tech=f.routes['tech-gaming'], sports=f.routes['sports-news'];tech.render(first);sports.render(second);
  tech.hooks.deactivate(first);assert.equal(f.requests[0].signal.aborted,true);assert.equal(f.requests[1].signal.aborted,false);
  sports.hooks.deactivate(second);assert.equal(f.requests[1].signal.aborted,true);assert.equal(f.timers.size,0);
  f.requests.forEach(request=>request.complete(snapshot()));await settle();
});
"""
        subprocess.run(['node', '-e', script], cwd=root, check=True, timeout=10, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
