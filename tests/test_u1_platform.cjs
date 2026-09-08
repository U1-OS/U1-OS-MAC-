const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../static/js/u1-platform-core.js');

test('layout normalisation rejects unknown widgets and duplicates',()=>{
 const p=core.normalize({hidden:['weather','bad','weather'],order:['focus']});
 assert.deepEqual(p.hidden,['weather']);assert.equal(p.order[0],'focus');assert.equal(new Set(p.order).size,core.ids.length);
});
test('malformed preference types fall back safely',()=>{
 const p=core.normalize({hidden:'weather',desktop:'true',quietStart:'25:70',snoozed:{x:Infinity}});
 assert.deepEqual(p.hidden,[]);assert.equal(p.desktop,false);assert.equal(p.quietStart,'22:00');assert.deepEqual(p.snoozed,{});
});
test('overnight quiet hours and matching boundary',()=>{
 const p=core.normalize();assert.equal(core.quiet(p,new Date(2026,8,8,23)),true);assert.equal(core.quiet(p,new Date(2026,8,8,6)),true);assert.equal(core.quiet(p,new Date(2026,8,8,7)),false);
});
test('equal quiet times disable suppression',()=>{
 const p=core.normalize({quietStart:'09:00',quietEnd:'09:00'});assert.equal(core.quiet(p,new Date(2026,8,8,9)),false);
});
test('fresh provider allowance is displayed',()=>{
 assert.equal(core.allowance({success:true},{used_percent:37,resets_at:200},90000,100000),37);
});
test('stale, expired and unavailable values are not quotas',()=>{
 assert.equal(core.allowance({success:true,stale:true},{used_percent:20},90000,100000),null);
 assert.equal(core.allowance({success:true},{used_percent:20,resets_at:90},90000,100000),null);
 assert.equal(core.allowance({success:true},{used_percent:20},1000,200000),null);
 assert.equal(core.allowance({success:false},{used_percent:20},90000,100000),null);
});
test('invalid percentages are not clamped into plausible readings',()=>{
 for(const value of [-1,101,NaN,'20'])assert.equal(core.allowance({success:true},{used_percent:value},90000,100000),null);
});
test('prompt builder preserves the goal and labels source material',()=>{
 const output=core.prompt({goal:'Make my weekly plan',context:'Meeting Monday'});
 assert.match(output,/OBJECTIVE\nMake my weekly plan/);assert.match(output,/CONTEXT AND SOURCE MATERIAL\nMeeting Monday/);assert.match(output,/Require approval before external publication/);
});
