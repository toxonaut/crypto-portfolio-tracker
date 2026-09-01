const MARKET_OVERVIEW_CHARTS = Object.freeze([
    {id:'marketChartBtc', symbol:'BINANCE:BTCUSD'},
    {id:'marketChartEth', symbol:'BINANCE:ETHUSD'},
    {id:'marketChartSol', symbol:'BINANCE:SOLUSD'},
    {id:'marketChartPaxg', symbol:'KRAKEN:PAXGUSD'},
    {id:'marketChartZec', symbol:'KRAKEN:ZECUSD'},
    {id:'marketChartSpy', symbol:'AMEX:SPY'}
]);
function marketChartConfig(chart) {
    return {autosize:true,symbol:chart.symbol,interval:'D',timezone:'Etc/UTC',theme:'dark',style:'1',locale:'en',
        toolbar_bg:'#121726',enable_publishing:false,allow_symbol_change:false,hide_side_toolbar:true,
        save_image:false,container_id:chart.id};
}
function initializeMarketOverviewCharts(TradingViewApi = typeof TradingView === 'undefined' ? null : TradingView) {
    const grid = document.getElementById('marketChartGrid');
    if (!grid) return [];
    const iosChrome = /iPad|iPhone|iPod/.test(navigator.userAgent) && /CriOS/.test(navigator.userAgent);
    if (iosChrome) {
        grid.replaceChildren();
        const message=document.createElement('p');
        message.className='alert alert-info';
        message.textContent='The six overview charts are disabled on iOS Chrome for performance. Use Safari to view them.';
        grid.appendChild(message);
        return [];
    }
    if (!TradingViewApi || typeof TradingViewApi.widget !== 'function') {
        grid.querySelectorAll('.market-mini-chart').forEach(node => {node.textContent='Chart unavailable.';});
        return [];
    }
    return MARKET_OVERVIEW_CHARTS.map(chart => new TradingViewApi.widget(marketChartConfig(chart)));
}
if (typeof module !== 'undefined' && module.exports) module.exports={MARKET_OVERVIEW_CHARTS,marketChartConfig,initializeMarketOverviewCharts};
