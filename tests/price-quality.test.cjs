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
const vm = require('node:vm');
const fs = require('node:fs');
test('overview renders partial prices without zero totals, including demo mode', async () => {
    const nodes = new Map();
    function element() { return {style:{},children:[],textContent:'',innerHTML:'',appendChild(child){this.children.push(child);}}; }
    const document = {getElementById(id){if(!nodes.has(id)) nodes.set(id,element());return nodes.get(id);},
        createElement:element,createTextNode(text){return {textContent:text};},addEventListener(){}};
    let result = {success:true,data:{unknown:{price:null,total_amount:2,total_value:null,monthly_yield:null,
        hourly_change:null,daily_change:0,seven_day_change:null,price_quality:{status:'missing'}}},
        total_value:null,total_monthly_yield:null,bitcoin_price:null,price_error:'Missing',
        price_quality:{complete:false,fresh:false,missing:['unknown'],priced_assets:0,required_assets:1}};
    const context = vm.createContext({document,navigator:{userAgent:''},window:{},console:{log(){},error(){}},PriceQuality:quality,
        fetch:async()=>({json:async()=>result}),updateWorkerHealth:async()=>{},updateHistorySummary:async()=>{},
        updateHistoricalChanges(){},showHistoricalChangesError(){}});
    vm.runInContext(fs.readFileSync(require.resolve('../static/overview.js'),'utf8'),context);
    await vm.runInContext('isDemoMode=true; updatePortfolio()',context);
    assert.equal(nodes.get('totalValue').textContent,'Unavailable');
    assert.equal(nodes.get('monthlyYield').textContent,'Unavailable');
    assert.equal(nodes.get('btcValue').textContent,'Unavailable');
    const cells=nodes.get('portfolioTableBody').children[0].children;
    assert.equal(cells[2].textContent,'Unavailable');
    assert.match(cells[3].innerHTML,/—/);
    assert.match(cells[4].innerHTML,/0.00%/);
    assert.equal(cells[6].textContent,'Unavailable');
    assert.match(nodes.get('priceApiError').textContent,/Incomplete pricing/);
});
