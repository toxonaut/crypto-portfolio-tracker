function compositionGroups(snapshot, group) {
    const values = new Map();
    for (const position of snapshot.positions) {
        const key = position[group];
        values.set(key, (values.get(key) || 0) + position.value_usd);
    }
    return values;
}
function compositionSeries(rows, group, metric, demo = false) {
    const groups = rows.map(row => compositionGroups(row, group));
    const names = [...new Set(groups.flatMap(map => [...map.keys()]))].sort();
    return names.map(name => ({label:name, data:rows.map((row, i) => {
        const value = groups[i].get(name) || 0;
        return metric === 'share' ? (row.total_value > 0 ? value / row.total_value * 100 : null) : value / (demo ? 15 : 1);
    })}));
}
let compositionPayload = null;
let compositionChart = null;
let compositionRequest = 0;
let compositionAbort = null;
const compositionDemo = () => typeof isDemoMode !== 'undefined' && isDemoMode;
const compositionNumber = value => Number.isFinite(value) ? value.toLocaleString('en-US', {maximumFractionDigits:8}).replace(/,/g, "'") : 'Unavailable';
const compositionMoney = value => Number.isFinite(value) ? (value < 0 ? '-$' : '$') + Math.abs(value).toLocaleString('en-US', {maximumFractionDigits:2}).replace(/,/g, "'") : 'Unavailable';

async function loadComposition(older = false) {
    const version = ++compositionRequest;
    if (compositionAbort) compositionAbort.abort();
    compositionAbort = new AbortController();
    const status = document.getElementById('compositionStatus');
    const load = document.getElementById('loadComposition');
    const previous = document.getElementById('olderComposition');
    const range = document.getElementById('compositionRange').value;
    const cursor = older ? compositionPayload?.next_before : null;
    load.disabled = previous.disabled = true;
    status.textContent = 'Loading composition snapshots…';
    try {
        const response = await fetch(`/history/composition?range=${encodeURIComponent(range)}${cursor ? '&before='+cursor : ''}`, {signal:compositionAbort.signal});
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error();
        if (version !== compositionRequest) return;
        compositionPayload = payload;
        const select = document.getElementById('compositionSnapshot');
        select.replaceChildren();
        payload.data.forEach((row, i) => {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = new Date(row.date).toLocaleString();
            select.appendChild(option);
        });
        select.value = String(payload.data.length-1);
        status.textContent = payload.data.length
            ? `${payload.data.length} recorded snapshots shown, ${new Date(payload.data[0].date).toLocaleString()} – ${new Date(payload.data.at(-1).date).toLocaleString()}.${payload.next_before ? ' Older snapshots available; each page is capped at 200.' : ''}`
            : 'No composition snapshots in this period. Recording starts with the first automatic or manual snapshot after this feature is deployed.';
        renderComposition();
    } catch (error) {
        if (version !== compositionRequest || error.name === 'AbortError') return;
        compositionPayload = null;
        renderComposition();
        status.textContent = 'Composition history could not be loaded. Please retry.';
    } finally {
        if (version === compositionRequest) {
            load.disabled = false;
            previous.disabled = !compositionPayload?.next_before;
        }
    }
}
function renderComposition() {
    const content = document.getElementById('compositionContent');
    if (!content) return;
    if (compositionChart) { compositionChart.destroy(); compositionChart = null; }
    const rows = compositionPayload?.data || [];
    content.hidden = !rows.length;
    if (!rows.length) return;
    const metric = document.getElementById('compositionMetric').value;
    const datasets = compositionSeries(rows, document.getElementById('compositionGroup').value, metric, compositionDemo());
    datasets.forEach((dataset, i) => {dataset.backgroundColor = `hsl(${i*137.508%360}, 65%, 62%)`;});
    compositionChart = new Chart(document.getElementById('compositionChart'), {
        type:'bar',data:{labels:rows.map(row=>new Date(row.date).toLocaleString()),datasets},
        options:{responsive:true,maintainAspectRatio:false,animation:false,
            onClick:(event,elements)=>{if(elements.length){document.getElementById('compositionSnapshot').value=String(elements[0].index);renderCompositionSnapshot();}},
            scales:{x:{stacked:true,ticks:{maxTicksLimit:8}},y:{stacked:true,title:{display:true,text:metric==='share'?'% of net portfolio value':'USD'},ticks:{callback:value=>metric==='share'?value+'%':compositionMoney(value)}}},
            plugins:{tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${metric==='share'?compositionNumber(ctx.raw)+'%':compositionMoney(ctx.raw)}`}}}}
    });
    renderCompositionSnapshot();
}
function renderCompositionSnapshot() {
    const row = compositionPayload?.data[Number(document.getElementById('compositionSnapshot').value)];
    const body = document.getElementById('compositionRows');
    body.replaceChildren();
    if (!row) return;
    const divisor = compositionDemo() ? 15 : 1;
    document.getElementById('compositionTotal').textContent = `Net value: ${compositionMoney(row.total_value/divisor)}${compositionDemo()?' · Demo values shown.':''}`;
    for (const p of row.positions) {
        const tr = document.createElement('tr');
        for (const value of [p.coin_id,p.source,p.amount===null?'':compositionNumber(p.amount/divisor),p.price_usd===null?'':compositionMoney(p.price_usd),compositionMoney(p.value_usd/divisor),row.total_value>0?compositionNumber(p.value_usd/row.total_value*100)+'%':'Unavailable']) {
            const td=document.createElement('td');td.textContent=value;tr.appendChild(td);
        }
        body.appendChild(tr);
    }
}
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('compositionPanel')) return;
    document.getElementById('loadComposition').addEventListener('click',()=>loadComposition());
    document.getElementById('olderComposition').addEventListener('click',()=>loadComposition(true));
    document.getElementById('compositionRange').addEventListener('change',()=>{
        ++compositionRequest;
        if (compositionAbort) compositionAbort.abort();
        compositionPayload=null;renderComposition();
        document.getElementById('olderComposition').disabled=true;
        document.getElementById('loadComposition').disabled=false;
        document.getElementById('compositionStatus').textContent='Period changed. Load latest to retrieve snapshots.';
    });
    for (const id of ['compositionGroup','compositionMetric']) document.getElementById(id).addEventListener('change',renderComposition);
    document.getElementById('compositionSnapshot').addEventListener('change',renderCompositionSnapshot);
});
if (typeof module !== 'undefined' && module.exports) module.exports = {compositionGroups, compositionSeries};
