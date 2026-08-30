const test = require('node:test');
const assert = require('node:assert/strict');
const {calculateExposure, renderExposure} = require('../static/exposure.js');
const holdings = {
    bitcoin:{price:100,sources:{Wallet:{amount:10},Loan:{amount:-3}}},
    ethereum:{price:20,sources:{Wallet:{amount:5},Loan:{amount:-2}}}
};
test('negative balances subtract from asset, platform and portfolio totals', () => {
    const result=calculateExposure(holdings);
    assert.equal(result.total,760);
    assert.deepEqual(result.assets,[['bitcoin',700],['ethereum',60]]);
    assert.deepEqual(result.platforms,[['Wallet',1100],['Loan',-340]]);
    assert.equal(result.excluded,0);
    for (const entries of [result.assets,result.platforms]) {
        assert.equal(entries.reduce((sum,[,value])=>sum+value,0),result.total);
    }
});
test('zero and negative net holdings remain signed, missing prices are excluded', () => {
    assert.equal(calculateExposure({btc:{price:100,sources:{A:{amount:1},B:{amount:-1}}}}).total,0);
    const result=calculateExposure({btc:{price:100,sources:{Loan:{amount:-2}}},missing:{price:null,sources:{Loan:{amount:-3}}}});
    assert.equal(result.total,-200);
    assert.equal(result.excluded,1);
});
test('render keeps deductions negative, bounds bars, and handles nonpositive net totals', () => {
    function element(){return {style:{},children:[],textContent:'',append(...children){this.children.push(...children);},appendChild(child){this.children.push(child);},replaceChildren(){this.children=[];},setAttribute(){}};}
    const nodes=new Map();
    global.document={getElementById(id){if(!nodes.has(id)) nodes.set(id,element());return nodes.get(id);},createElement:element};
    try {
        renderExposure(holdings);
        let rows=nodes.get('platformExposure').children[1].children;
        assert.match(rows[1].children[0].children[1].textContent,/-44.7% · -\$340.00/);
        assert.equal(rows[1].children[1].children[0].className,'exposure-bar exposure-negative');
        assert.ok(parseFloat(rows[0].children[1].children[0].style.width)<=50);
        renderExposure(holdings,true);
        rows=nodes.get('platformExposure').children[1].children;
        assert.match(rows[1].children[0].children[1].textContent,/-44.7% · -\$22.67/);
        for (const amount of [0,-1]) {
            renderExposure({btc:{price:100,sources:{A:{amount:1},B:{amount:amount-1}}}});
            assert.match(nodes.get('exposureStatus').textContent,/shares are unavailable/);
            assert.match(nodes.get('assetExposure').children[1].children[0].children[0].children[1].textContent,/Share unavailable/);
        }
    } finally {delete global.document;}
});
