const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {MARKET_OVERVIEW_CHARTS,marketChartConfig,initializeMarketOverviewCharts}=require('../static/market-charts.js');
const expected=[['marketChartBtc','BINANCE:BTCUSD'],['marketChartEth','BINANCE:ETHUSD'],['marketChartSol','BINANCE:SOLUSD'],['marketChartPaxg','KRAKEN:PAXGUSD'],['marketChartZec','KRAKEN:ZECUSD'],['marketChartSpy','AMEX:SPY']];
function environment(userAgent='Desktop') {
    const minis=expected.map(()=>({textContent:''}));
    const grid={children:[],querySelectorAll(){return minis;},replaceChildren(){this.children=[];},appendChild(node){this.children.push(node);}};
    global.document={getElementById:id=>id==='marketChartGrid'?grid:null,createElement:()=>({className:'',textContent:''})};
    Object.defineProperty(global,'navigator',{configurable:true,value:{userAgent}});
    return {grid,minis};
}
test('six fixed charts use the requested markets and fit their own containers',()=>{
    assert.deepEqual(MARKET_OVERVIEW_CHARTS.map(c=>[c.id,c.symbol]),expected);
    const configs=[];function Widget(config){configs.push(config);}
    environment();
    const widgets=initializeMarketOverviewCharts({widget:Widget});
    assert.equal(widgets.length,6);assert.equal(configs.length,6);
    for(let i=0;i<6;i++) {
        assert.deepEqual(configs[i],marketChartConfig(MARKET_OVERVIEW_CHARTS[i]));
        assert.equal(configs[i].autosize,true);assert.equal(configs[i].allow_symbol_change,false);
    }
});
test('missing TradingView fails visibly without breaking the page',()=>{
    const {minis}=environment();
    assert.deepEqual(initializeMarketOverviewCharts(null),[]);
    assert.ok(minis.every(node=>node.textContent==='Chart unavailable.'));
});
test('iOS Chrome receives one performance notice instead of six widgets',()=>{
    const {grid}=environment('Mozilla iPhone CriOS');let calls=0;
    assert.deepEqual(initializeMarketOverviewCharts({widget:function(){calls++;}}),[]);
    assert.equal(calls,0);assert.equal(grid.children.length,1);assert.match(grid.children[0].textContent,/disabled/);
});
test('grid is three by two on desktop and responsive below it',()=>{
    const css=fs.readFileSync(require.resolve('../static/style.css'),'utf8');
    assert.match(css,/grid-template-columns:\s*repeat\(3,/);
    assert.match(css,/max-width:\s*991px[\s\S]*repeat\(2,/);
    assert.match(css,/max-width:\s*575px[\s\S]*grid-template-columns:\s*minmax/);
});
