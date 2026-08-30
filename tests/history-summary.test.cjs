const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/history-summary.js'),'utf8'),ctx);
const summary={comparisons:{change24h:{total_value:100,datetime:'2026-08-29T15:45:00'}}};
test('summary alone produces uncapped returns without chart history',()=>{
 const r=ctx.calculateSummaryChanges(summary,500);
 assert.equal(r.change24h.percent,400);
 assert.equal(r.change24h.value,400);
 assert.equal(r.change7d,null);
});
test('demo scales dollars but never percentages',()=>{
 const r=ctx.calculateSummaryChanges(summary,250,true);
 assert.equal(r.change24h.value,10);
 assert.equal(r.change24h.percent,150);
});
test('no history or price data is unavailable rather than zero',()=>{
 assert.equal(ctx.calculateSummaryChanges(null,100).change24h,null);
 assert.equal(ctx.calculateSummaryChanges(summary,null).change24h,null);
 assert.equal(ctx.calculateSummaryChanges({comparisons:{change24h:{total_value:0}}},100).change24h,null);
});
test('actual zero current value represents a total loss',()=>{
 assert.equal(ctx.calculateSummaryChanges(summary,0).change24h.percent,-100);
});
