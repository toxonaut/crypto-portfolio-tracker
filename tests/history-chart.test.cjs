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
test('recording gaps retain only the actual endpoints for a straight connection',()=>{
 const points=context.historyCoordinates([{datetime:'2026-08-29T12:00:00',total_value:100,segment:0},{datetime:'2026-08-30T12:00:00',total_value:120,segment:1}],'total_value');
 assert.equal(points.length,2);assert.equal(points[0].y,100);assert.equal(points[1].y,120);
 assert.equal(points[1].x-points[0].x,86400000);
});
test('missing BTC values remain null instead of becoming zero',()=>{
 const points=context.historyCoordinates([{datetime:'2026-08-29T12:00:00',btc:1,segment:0},{datetime:'2026-08-30T12:00:00',btc:null,segment:1}],'btc');
 assert.equal(points.length,2);assert.equal(points[1].y,null);
});
test('demo coordinates scale amounts without changing dates',()=>{
 context.isDemoMode=true;
 const point=context.historyCoordinates([{datetime:'2026-08-30T12:00:00',total_value:150,segment:0}],'total_value')[0];
 assert.equal(point.y,10);assert.equal(point.x,Date.parse('2026-08-30T12:00:00Z'));
 context.isDemoMode=false;
});
test('chart currencies use apostrophe grouping',()=>assert.equal(context.historyMoney(123532),"$123'532"));
