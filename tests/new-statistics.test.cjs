const test=require('node:test');
const assert=require('node:assert/strict');
const {statisticsMoney}=require('../static/new-statistics.js');
test('new statistics formats normal, negative, demo and unavailable values',()=>{
    assert.equal(statisticsMoney(123532),"$123'532.00");
    assert.equal(statisticsMoney(-30),'-$30.00');
    assert.equal(statisticsMoney(150,true),'$10.00');
    assert.equal(statisticsMoney(null),'Unavailable');
});
test('statistics reads only New Portfolio overview and summary endpoints',()=>{
    const source=require('node:fs').readFileSync(require.resolve('../static/new-statistics.js'),'utf8');
    assert.match(source,/fetch\('\/api\/new-portfolio\/overview'/);
    assert.match(source,/fetch\('\/new-portfolio\/history\/summary'/);
    assert.doesNotMatch(source,/fetch\('\/portfolio'/);
});
