const test = require('node:test');
const assert = require('node:assert/strict');
const quality = require('../static/price-quality.js');
test('missing values are distinct from real zero and formatted amounts', () => {
    assert.equal(quality.money(null), 'Unavailable');
    assert.equal(quality.money(NaN), 'Unavailable');
    assert.equal(quality.money(0), '0.00');
    assert.equal(quality.money(123532), "123'532.00");
});
test('partial and stale pricing are explained', () => {
    assert.match(quality.summary({complete:false,priced_assets:1,required_assets:2,missing:['eth']}), /Missing: eth/);
    assert.match(quality.summary({complete:true,fresh:false,stale:['btc']}), /Estimated valuation/);
    assert.equal(quality.label({status:'missing'}), 'Price unavailable');
});
