const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/scenario.js'), 'utf8'), context);
const {calculateScenario, scenarioPositions} = context;
const positions = [{coin:'bitcoin',value:600,apy:12},{coin:'ether',value:400,apy:6}];

test('unchanged scenario matches portfolio value and dashboard income convention', () => {
    const r = calculateScenario(positions, new Map(), 0, 1);
    assert.equal(r.value,1000);
    assert.equal(r.income,8);
    assert.equal(r.impact,0);
});
test('contributions are allocated before independent price shocks; impact excludes deposits', () => {
    const r = calculateScenario(positions,new Map([['bitcoin',50],['ether',-50]]),1000,0.5);
    assert.equal(r.value,2200);
    assert.equal(r.impact,200);
    assert.equal(r.income,10);
    assert.equal(r.baselineIncome,8);
});
test('total price loss and zero yield are supported', () => {
    const loss = calculateScenario(positions,new Map([['bitcoin',-100],['ether',-100]]),1000,2);
    assert.equal(loss.value,0);
    assert.equal(loss.income,0);
    assert.equal(loss.impact,-2000);
    assert.equal(calculateScenario(positions,new Map(),0,0).income,0);
});
test('multiple locations retain their individual yields and never mutate holdings', () => {
    const data = {bitcoin:{price:100,sources:{Wallet:{amount:2,apy:0},Staking:{amount:1,apy:12}}}};
    const before=JSON.stringify(data);
    const parsed=scenarioPositions(data);
    assert.equal(parsed.positions.length,2);
    assert.equal(calculateScenario(parsed.positions,new Map(),300,1).income,2);
    assert.equal(JSON.stringify(data),before);
});
test('missing prices, debt, zero balances and unknown APYs are explicit', () => {
    const parsed=scenarioPositions({a:{price:100,sources:{x:{amount:1},y:{amount:0},z:{amount:-1}}},b:{price:0,sources:{x:{amount:2}}}});
    assert.equal(parsed.excluded,2);
    assert.equal(parsed.unknownYield,1);
    assert.equal(parsed.positions.length,1);
    assert.equal(calculateScenario(parsed.positions,new Map(),0,1).income,0);
    assert.equal(calculateScenario([],new Map(),0,1).value,0);
});
