let newStatisticsOverview=null;
let newStatisticsSummary=null;

function statisticsMoney(value,demo=false){return Number.isFinite(value)?(value<0?'-$':'$')+(Math.abs(value)/(demo?15:1)).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).replace(/,/g,"'"):'Unavailable';}
function renderNewStatistics(){
    if(!newStatisticsOverview)return;
    const demo=typeof isDemoMode!=='undefined'&&isDemoMode;
    document.getElementById('totalValue').textContent=statisticsMoney(newStatisticsOverview.total_value_usd,demo);
    document.getElementById('btcValue').textContent=Number.isFinite(newStatisticsOverview.btc_value)?newStatisticsOverview.btc_value.toLocaleString('en-US',{maximumFractionDigits:8}):'Unavailable';
    document.getElementById('monthlyYield').textContent=statisticsMoney(newStatisticsOverview.monthly_yield_usd,demo);
    document.getElementById('lastUpdated').textContent=newStatisticsOverview.as_of?new Date(newStatisticsOverview.as_of).toLocaleString():'Unavailable';
    const quality=document.getElementById('priceApiError'),q=newStatisticsOverview.price_quality;
    quality.textContent=typeof newOverviewPriceCoverage==='function'?newOverviewPriceCoverage(q,newStatisticsOverview.unpriced_assets):`Price coverage: ${q.priced_assets}/${q.required_assets} assets.`;
    quality.className=q.complete&&!q.stale.length?'alert alert-info':'alert alert-warning';
    const changes=typeof calculateNewHistoricalChanges==='function'?calculateNewHistoricalChanges(newStatisticsSummary,newStatisticsOverview.total_value_usd):{};
    for(const [id,key] of [['change24h','change24h'],['change7d','change7d'],['change30d','change30d']]){
        const element=document.getElementById(id),change=changes[key];
        if(!change){element.textContent='Unavailable';continue;}
        element.innerHTML=typeof formatValueChange==='function'?formatValueChange(change.value/(demo?15:1),change.percent):`${statisticsMoney(change.value,demo)} (${change.percent.toFixed(2)}%)`;
        element.title=`Compared with snapshot ${change.date.replace('T',' ')} (server time).`;
    }
}
async function updateNewStatistics(){
    const [overviewResponse,summaryResponse]=await Promise.all([fetch('/api/new-portfolio/overview'),fetch('/new-portfolio/history/summary')]);
    const [overview,summary]=await Promise.all([overviewResponse.json(),summaryResponse.json()]);
    if(!overviewResponse.ok||!overview.success)throw new Error(overview.error||'New Portfolio summary unavailable.');
    newStatisticsOverview=overview.data;
    newStatisticsSummary=summaryResponse.ok&&summary.success?summary.data:null;
    renderNewStatistics();
}
if(typeof module!=='undefined'&&module.exports)module.exports={statisticsMoney};
