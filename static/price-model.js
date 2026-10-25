let bitcoinPriceModelChart=null;
let bitcoinPriceModelRequest=0;
let bitcoinPriceModelData=null;
let bitcoinPriceModelProjection=false;

function priceModelMoney(value) {
    if(!Number.isFinite(value)) return 'Unavailable';
    const digits=Math.abs(value)<1?4:0;
    return '$'+value.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}).replace(/,/g,"'");
}
function priceModelPercent(value) { return Number.isFinite(value)?`${value>=0?'+':''}${value.toFixed(2)}%`:'Unavailable'; }
function priceModelPoints(rows) { return (rows||[]).map(row=>({x:row[0],y:row[1]})); }

function renderBitcoinPriceModel(data) {
    bitcoinPriceModelData=data;
    document.getElementById('priceModelActual').textContent=priceModelMoney(data.current_actual);
    document.getElementById('priceModelModeled').textContent=priceModelMoney(data.current_model);
    document.getElementById('priceModelDeviation').textContent=priceModelPercent(data.deviation_percent);
    document.getElementById('priceModelDeviation').className=Number.isFinite(data.deviation_percent)?(data.deviation_percent>=0?'price-change-positive':'price-change-negative'):'';
    document.getElementById('priceModelRatio').textContent=Number.isFinite(data.ratio)?`${data.ratio.toFixed(2)}× actual/model`:'Ratio unavailable';
    if(bitcoinPriceModelChart){bitcoinPriceModelChart.destroy();bitcoinPriceModelChart=null;}
    const log=document.getElementById('priceModelLog').checked;
    bitcoinPriceModelChart=new Chart(document.getElementById('priceModelChart'),{type:'line',data:{datasets:[
        {label:'BTC/USD market price',data:priceModelPoints(data.actual),borderColor:'#f7931a',backgroundColor:'transparent',borderWidth:2,pointRadius:0,pointHitRadius:8},
        {label:'Modeled BTC price',data:priceModelPoints(data.model),borderColor:'#7ea6ff',backgroundColor:'transparent',borderWidth:2,borderDash:[8,5],pointRadius:0,pointHitRadius:8}
    ]},options:{responsive:true,maintainAspectRatio:false,animation:false,parsing:false,interaction:{mode:'nearest',intersect:false},
        plugins:{legend:{labels:{color:'#c7d6f0'}},tooltip:{callbacks:{title:items=>items.length?new Date(items[0].parsed.x).toISOString().slice(0,10):'',label:context=>`${context.dataset.label}: ${priceModelMoney(context.parsed.y)}`}}},
        scales:{x:{type:'linear',ticks:{maxTicksLimit:10,color:'#a7b4cb',callback:value=>new Date(value).toISOString().slice(0,10)},grid:{color:'#263149'}},
            y:{type:log?'logarithmic':'linear',ticks:{color:'#a7b4cb',callback:priceModelMoney},grid:{color:'#263149'}}}}
    });
}

async function loadBitcoinPriceModel() {
    const request=++bitcoinPriceModelRequest;
    const button=document.getElementById('priceModelRefresh');
    const status=document.getElementById('priceModelStatus');
    button.disabled=true;status.textContent='Loading selected Bitcoin history…';
    try {
        const range=document.getElementById('priceModelRange').value;
        const projection=bitcoinPriceModelProjection?'5y':'none';
        const response=await fetch(`/api/bitcoin-price-model?range=${encodeURIComponent(range)}&projection=${projection}`,{headers:{Accept:'application/json'}});
        const payload=await response.json();
        if(!response.ok||!payload.success)throw new Error(payload.error||'Bitcoin price model could not be loaded.');
        if(request!==bitcoinPriceModelRequest)return;
        renderBitcoinPriceModel(payload.data);
        const first=payload.data.actual.length?new Date(payload.data.actual[0][0]).toISOString().slice(0,10):'unavailable';
        status.textContent=`${payload.data.actual.length.toLocaleString()} market observations from ${first}; ${payload.data.model.length.toLocaleString()} modeled daily values${payload.data.projected_through?` through ${payload.data.projected_through}`:''}. Historical source: ${payload.data.historical_source}; latest quote: ${payload.data.latest_source||'historical source'}.`;
    } catch(error) {
        if(request===bitcoinPriceModelRequest)status.textContent=`${error.message} Retry with Refresh.`;
    } finally { if(request===bitcoinPriceModelRequest)button.disabled=false; }
}

function initializeBitcoinPriceModel() {
    const section=document.getElementById('priceModelSection');
    if(!section)return;
    document.getElementById('priceModelRefresh').onclick=loadBitcoinPriceModel;
    document.getElementById('priceModelRange').onchange=loadBitcoinPriceModel;
    document.getElementById('priceModelProjection').onclick=()=>{
        bitcoinPriceModelProjection=!bitcoinPriceModelProjection;
        const button=document.getElementById('priceModelProjection');
        button.setAttribute('aria-pressed',String(bitcoinPriceModelProjection));
        button.classList.toggle('active',bitcoinPriceModelProjection);
        button.textContent=bitcoinPriceModelProjection?'Hide 5-year projection':'Project 5 years';
        loadBitcoinPriceModel();
    };
    document.getElementById('priceModelLog').onchange=()=>{if(bitcoinPriceModelData)renderBitcoinPriceModel(bitcoinPriceModelData);};
    loadBitcoinPriceModel();
}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',initializeBitcoinPriceModel);
if(typeof module!=='undefined'&&module.exports)module.exports={priceModelMoney,priceModelPercent,priceModelPoints};
