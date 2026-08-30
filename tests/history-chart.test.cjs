const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const context=vm.createContext({isDemoMode:false});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/history-chart.js'),'utf8'),context);
test('server timestamps have identical coordinates with or without UTC suffix',()=>{
 assert.equal(context.historyTime('2026-08-30T12:00:00'),context.historyTime('2026-08-30T12:00:00Z'));
});
test('gap markers interrupt lines and missing BTC stays null',()=>{
 const points=context.historyCoordinates([{datetime:'2026-08-29T12:00:00',btc:1,segment:0},{datetime:'2026-08-30T12:00:00',btc:null,segment:1}],'btc');
 assert.equal(points.length,3);assert.equal(points[1].y,null);assert.equal(points[2].y,null);
 assert.ok(points[1].x>points[0].x&&points[1].x<points[2].x);
});
test('demo coordinates scale amounts without changing dates',()=>{
 context.isDemoMode=true;
 const point=context.historyCoordinates([{datetime:'2026-08-30T12:00:00',total_value:150,segment:0}],'total_value')[0];
 assert.equal(point.y,10);assert.equal(point.x,Date.parse('2026-08-30T12:00:00Z'));
 context.isDemoMode=false;
});
test('chart currencies use apostrophe grouping',()=>assert.equal(context.historyMoney(123532),"$123'532"));
