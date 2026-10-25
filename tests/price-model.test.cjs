const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {priceModelMoney,priceModelPercent,priceModelPoints}=require('../static/price-model.js');

test('price model formats values and chart coordinates',()=>{
    assert.equal(priceModelMoney(123532),"$123'532");
    assert.equal(priceModelMoney(.08584),'$0.0858');
    assert.equal(priceModelMoney(null),'Unavailable');
    assert.equal(priceModelPercent(12.345),'+12.35%');
    assert.deepEqual(priceModelPoints([[1000,2]]),[{x:1000,y:2}]);
});
test('Price Model section sits between Market Charts and Portfolio History and offers all ranges',()=>{
    const html=fs.readFileSync(require.resolve('../templates/index.html'),'utf8');
    assert.ok(html.indexOf('Market Charts')<html.indexOf('Price Model'));
    assert.ok(html.indexOf('Price Model')<html.indexOf('Portfolio History'));
    for(const value of ['1y','2y','5y','10y','all'])assert.match(html,new RegExp(`value="${value}"`));
    assert.match(html,/id="priceModelLog"[^>]*checked/);
    assert.match(html,/id="priceModelProjection"[^>]*aria-pressed="false"[^>]*>Project 5 years/);
    const source=fs.readFileSync(require.resolve('../static/price-model.js'),'utf8');
    assert.match(source,/projection=\$\{projection\}/);
    assert.match(source,/Hide 5-year projection/);
});
