let historyChartPayload = null;
let historyRequest = null;
let historyRequestVersion = 0;
let historyMutationPending = false;
let historyFlowRequestId = null;

// Treat naive server timestamps consistently as coordinates, not browser-local dates.
function historyTime(value) { return Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z'); }
function historyMoney(value) { return '$' + value.toLocaleString('en-US', {maximumFractionDigits: 2}).replace(/,/g, "'"); }
function historyCoordinates(rows, field) {
    const points=[];
    for (let i=0; i<rows.length; i++) {
        const row=rows[i];
        points.push({x:historyTime(row.datetime), y:Number.isFinite(row[field]) ? row[field]/(isDemoMode?15:1) : null});
    }
    return points;
}

async function updateHistoryChart() {
    const panel=document.getElementById('historyPanel');
    if(!panel) return false;
    historyChartEnabled=true;
    const version=++historyRequestVersion;
    if(historyRequest) historyRequest.abort();
    historyRequest=new AbortController();
    const period=document.getElementById('historyRange').value;
    const button=document.getElementById('loadHistoryDataBtn');
    button.textContent='Loading…';
    panel.setAttribute('aria-busy','true');
    document.getElementById('historyChartStatus').textContent='Loading selected history…';
    try {
        const response=await fetch(`/new-portfolio/history?range=${encodeURIComponent(period)}&max_points=${isIOSChrome?240:600}`,{signal:historyRequest.signal});
        const payload=await response.json();
        if(!response.ok || !payload.success || !Array.isArray(payload.data)) throw new Error(payload.error || 'Could not load chart history.');
        if(version!==historyRequestVersion) return false;
        historyChartPayload=payload;
        historyData=payload.data;
        const meta=payload.meta;
        let status=`${meta.returned_count} of ${meta.source_count} snapshots shown for ${meta.range === 'all' ? 'all history' : meta.range+' days'}. Latest record: ${meta.latest?.replace('T',' ') || 'none'} (server time).`;
        if(meta.sampled) status+=' Sampled by time bucket, preserving peaks, drops and endpoints.';
        if(meta.stale) status+=' History is stale: no recent snapshot.';
        if(meta.gap_count) status+=` ${meta.gap_count} recording gap(s) over ${meta.gap_threshold_hours} hours; straight lines connect the available points across gaps.`;
        if(meta.invalid_count) status+=` ${meta.invalid_count} invalid snapshot(s) excluded.`;
        if(!payload.data.length) status+=' No usable snapshots in this period. Choose a longer period or refresh later.';
        if(meta.flows_truncated) status+=' More than 500 annotations in this range: showing the first 500, with adjusted view disabled. Choose a shorter period.';
        document.getElementById('historyChartStatus').textContent=status;
        document.getElementById('historyLedger').hidden=false;
        const when=document.querySelector('#historyFlowForm [name="datetime"]');
        when.max=meta.server_now.split('.')[0];
        if(!when.value) when.value=when.max;
        renderHistoryChart();
        renderHistoryFlows();
        updateHistoryExtremes();
        return true;
    } catch(error) {
        if(error.name==='AbortError' || version!==historyRequestVersion) return false;
        document.getElementById('historyChartStatus').textContent=`${error.message} Retry with Refresh. ${historyChartPayload ? 'The displayed chart is the last successful result ('+historyChartPayload.meta.range+').' : ''}`;
        return false;
    } finally {
        if(version===historyRequestVersion) { button.textContent=historyChartPayload?'Refresh':'Retry'; panel.setAttribute('aria-busy','false'); }
    }
}

function renderHistoryChart() {
    if(!historyChartPayload) return;
    const rows=historyChartPayload.data;
    const container=document.getElementById('historyChartContainer');
    container.hidden=!rows.length;
    if(historyChart) { historyChart.destroy(); historyChart=null; }
    if(!rows.length) return;
    const usd=document.getElementById('historyUsd').checked;
    const btc=document.getElementById('historyBtc').checked;
    const adjustedInput=document.getElementById('historyAdjusted');
    adjustedInput.disabled=historyChartPayload.meta.flows_truncated;
    if(adjustedInput.disabled) adjustedInput.checked=false;
    const adjusted=adjustedInput.checked;
    const datasets=[
        {label:'Portfolio USD',data:historyCoordinates(rows,'total_value'),borderColor:'#7ea6ff',hidden:!usd,yAxisID:'usd'},
        {label:'Portfolio BTC',data:historyCoordinates(rows,'btc'),borderColor:'#ffb55b',hidden:!btc,yAxisID:'btc'},
        {label:'USD minus recorded flows',data:historyCoordinates(rows,'adjusted_usd'),borderColor:'#5eddb6',hidden:!adjusted,yAxisID:'usd'}
    ].map(d=>({...d,spanGaps:true,tension:0,pointRadius:rows.length===1?4:0,pointHitRadius:8,borderWidth:2}));
    const visible=datasets.filter(d=>!d.hidden);
    const logRequested=document.getElementById('historyLog').checked;
    const log=logRequested && visible.every(d=>d.data.every(p=>p.y===null || p.y>0));
    document.getElementById('historyScaleStatus').textContent=logRequested&&!log ? 'Linear scale used: a visible series contains zero or negative values.' : (!visible.length ? 'Select USD, BTC or the adjusted view to display a series.' : '');
    const markerPlugin={id:'cashFlowMarkers',afterDraw(chart){
        const {ctx,chartArea,scales}=chart;
        ctx.save(); ctx.strokeStyle='#c5a8ff';ctx.setLineDash([3,4]);ctx.fillStyle='#c5a8ff';ctx.font='11px sans-serif';
        for(const flow of historyChartPayload.flows) {
            const x=scales.x.getPixelForValue(historyTime(flow.datetime));
            if(x<chartArea.left || x>chartArea.right) continue;
            ctx.beginPath();ctx.moveTo(x,chartArea.top);ctx.lineTo(x,chartArea.bottom);ctx.stroke();
            ctx.fillText(flow.amount_usd>0?'+':'−',x+3,chartArea.top+12);
        }
        ctx.restore();
    }};
    historyChart=new Chart(document.getElementById('historyChart'),{type:'line',data:{datasets},plugins:[markerPlugin],options:{
        responsive:true,maintainAspectRatio:false,animation:false,parsing:false,
        interaction:{mode:'nearest',intersect:false},
        plugins:{legend:{labels:{color:'#c7d6f0'},onClick(event,item,legend){
            const ids=['historyUsd','historyBtc','historyAdjusted']; const input=document.getElementById(ids[item.datasetIndex]);
            if(input.disabled) return;input.checked=!input.checked;renderHistoryChart();
        }},tooltip:{callbacks:{title:items=>items.length?new Date(items[0].parsed.x).toISOString().replace('T',' ').slice(0,19)+' (server time)':'',label:ctx=>ctx.dataset.label+': '+(ctx.dataset.yAxisID==='btc'?ctx.parsed.y.toFixed(6)+' BTC':historyMoney(ctx.parsed.y))}}},
        scales:{x:{type:'linear',min:rows.length>1 ? historyTime(rows[0].datetime) : undefined,max:rows.length>1 && rows[0].datetime!==rows.at(-1).datetime ? historyTime(rows.at(-1).datetime) : undefined,ticks:{maxTicksLimit:8,color:'#a7b4cb',callback:v=>new Date(v).toISOString().slice(0,10)},grid:{color:'#263149'}},
            usd:{type:log?'logarithmic':'linear',display:usd||adjusted,position:'left',ticks:{color:'#a7b4cb',callback:historyMoney},grid:{color:'#263149'}},
            btc:{type:log?'logarithmic':'linear',display:btc,position:'right',ticks:{color:'#a7b4cb'},grid:{drawOnChartArea:false}}}
    }});
}

function renderHistoryFlows() {
    const list=document.getElementById('historyFlowList');
    list.replaceChildren();
    for(const flow of historyChartPayload.flows) {
        const item=document.createElement('li');
        const label=document.createElement('span');
        label.textContent=`${flow.datetime.replace('T',' ')} — ${flow.amount_usd>0?'Deposit':'Withdrawal'} ${historyMoney(Math.abs(flow.amount_usd)/(isDemoMode?15:1))}${isDemoMode?' (demo)':''}${flow.note?' — '+flow.note:''}`;
        const remove=document.createElement('button'); remove.type='button';remove.className='btn btn-sm btn-outline-danger';remove.textContent='Delete annotation';remove.disabled=historyMutationPending;
        remove.onclick=async()=>{
            if(historyMutationPending || !confirm('Delete this cash-flow annotation? Holdings will not change.')) return;
            await mutateHistoryFlow(`/new-portfolio/history/flows/${flow.id}`,'DELETE');
        };
        item.append(label,remove);list.appendChild(item);
    }
}

async function mutateHistoryFlow(url,method,body) {
    if(historyMutationPending) return false;
    historyMutationPending=true;
    const form=document.getElementById('historyFlowForm');
    for(const field of form.elements) field.disabled=true;
    renderHistoryFlows();
    const status=document.getElementById('historyFlowStatus');status.textContent='Saving annotation…';
    try {
        const response=await fetch(url,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':historyChartPayload.csrf_token},body:body?JSON.stringify(body):undefined});
        const result=await response.json();
        if(!response.ok || !result.success) throw Error(result.error || 'Could not save annotation.');
        status.textContent=method==='DELETE'?'Annotation deleted.':'Annotation saved. Holdings were not changed.';
        await updateHistoryChart();
        return true;
    } catch(error) { status.textContent=error.message+' Refresh the ledger before retrying if the result is uncertain.';return false; }
    finally {historyMutationPending=false;for(const field of form.elements) field.disabled=false;renderHistoryFlows();}
}

function initializeHistoryPanel() {
    const button=document.getElementById('loadHistoryDataBtn');
    if(!button || button.dataset.ready) return;
    button.dataset.ready='true';
    button.onclick=updateHistoryChart;
    document.getElementById('historyRange').onchange=()=>{if(historyChartEnabled) updateHistoryChart();};
    for(const id of ['historyUsd','historyBtc','historyAdjusted','historyLog']) document.getElementById(id).onchange=renderHistoryChart;
    document.getElementById('historyFlowForm').oninput=()=>{historyFlowRequestId=null;};
    document.getElementById('historyFlowForm').onsubmit=async event=>{
        event.preventDefault();
        const data=Object.fromEntries(new FormData(event.target));
        historyFlowRequestId ||= crypto.randomUUID();
        data.request_id=historyFlowRequestId;
        if(await mutateHistoryFlow('/new-portfolio/history/flows','POST',data)) { historyFlowRequestId=null; event.target.elements.amount_usd.value=''; event.target.elements.note.value=''; }
    };
}
