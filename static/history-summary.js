// Summary data is independent of the on-demand chart and never contains full history.
let historySummary = null;
let historySummaryError = false;

async function updateHistorySummary() {
    try {
        const response = await fetch('/history/summary');
        const payload = await response.json();
        if (!response.ok || !payload.success || !payload.data?.comparisons) throw new Error('Summary unavailable');
        historySummary = payload.data;
        historySummaryError = false;
    } catch (error) {
        historySummary = null;
        historySummaryError = true;
        console.error('History summary unavailable:', error);
    }
    updateHistoricalChanges();
}

function calculateSummaryChanges(summary, currentValue, demoMode = false) {
    const changes = {};
    for (const name of ['change24h', 'change7d', 'change30d']) {
        const sample = summary?.comparisons?.[name];
        changes[name] = sample && Number.isFinite(sample.total_value) && sample.total_value > 0 && Number.isFinite(currentValue) && currentValue >= 0
            ? {value: (currentValue - sample.total_value) / (demoMode ? 15 : 1),
                percent: (currentValue - sample.total_value) / sample.total_value * 100,
                date: sample.datetime}
            : null;
    }
    return changes;
}

function updateHistoricalChanges() {
    const currentValue = portfolioData?.price_error ? null : portfolioData?.total_value;
    const changes = calculateSummaryChanges(historySummary, currentValue, isDemoMode);
    for (const [name, change] of Object.entries(changes)) {
        document.querySelectorAll(`#${name}`).forEach(element => {
            if (!change) {
                element.textContent = 'Unavailable';
                element.title = historySummaryError ? 'History summary could not be loaded.' : 'Current value or a valid historical snapshot within 12 hours of the target is unavailable.';
                return;
            }
            element.innerHTML = formatValueChange(change.value, change.percent);
            // Preserve the server timestamp without pretending naive stored dates have a timezone.
            element.title = `Compared with snapshot ${change.date.replace('T', ' ')} (server time). Portfolio value change includes deposits and withdrawals.`;
        });
    }
}

// Only called after chart data is explicitly requested, or when changing demo mode.
function updateHistoryExtremes() {
    const ids = ['largestPercentGain', 'largestDollarGain', 'largestPercentLoss', 'largestDollarLoss'];
    if (!ids.some(id => document.getElementById(id))) return;
    const rows = historyData.filter(r => Number.isFinite(r.total_value) && r.total_value >= 0)
        .map(r => ({time: new Date(r.datetime).getTime(), value: r.total_value}))
        .filter(r => Number.isFinite(r.time)).sort((a,b) => a.time-b.time);
    const best = Object.fromEntries(ids.map(id => [id, null]));
    // Nearest earlier sample around 24h, via binary search (hourly data is supported).
    for (let i=1; i<rows.length; i++) {
        const target = rows[i].time-86400000;
        let lo=0, hi=i;
        while(lo<hi) { const mid=(lo+hi)>>1; if(rows[mid].time<target) lo=mid+1; else hi=mid; }
        const candidates=[lo-1,lo].filter(j => j>=0 && j<i);
        const j=candidates.sort((a,b)=>Math.abs(rows[a].time-target)-Math.abs(rows[b].time-target))[0];
        if(j === undefined || Math.abs(rows[j].time-target)>4*3600000 || rows[j].value<=0) continue;
        const value=(rows[i].value-rows[j].value)/(isDemoMode?15:1);
        const percent=(rows[i].value-rows[j].value)/rows[j].value*100;
        const change={value,percent,date:new Date(rows[i].time).toLocaleString()};
        for(const id of ids) {
            const metric=id.includes('Percent')?'percent':'value';
            const gain=id.includes('Gain');
            if ((gain ? change[metric]>0 : change[metric]<0) && (!best[id] || (gain ? change[metric]>best[id][metric] : change[metric]<best[id][metric]))) best[id]=change;
        }
    }
    for (const id of ids) {
        const element=document.getElementById(id);
        if(!element) continue;
        const change=best[id];
        element.textContent=change ? `${id.includes('Percent') ? change.percent.toFixed(2)+'%' : '$'+change.value.toFixed(2)} (${change.date})` : 'Unavailable';
    }
}

function showHistoricalChangesError() {
    for (const id of ['change24h', 'change7d', 'change30d']) {
        document.querySelectorAll(`#${id}`).forEach(element => {
            element.textContent = 'Unavailable';
            element.title = 'Current portfolio value could not be refreshed.';
        });
    }
}
