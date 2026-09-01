function krakenNumber(value, digits=8) { return Number.isFinite(value) ? value.toLocaleString('en-US',{maximumFractionDigits:digits}).replace(/,/g,"'") : 'Unavailable'; }
function krakenMoney(value) { return Number.isFinite(value) ? (value<0?'-$':'$')+Math.abs(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).replace(/,/g,"'") : 'Unavailable'; }
function renderKrakenPortfolio(data) {
    document.getElementById('krakenSummary').hidden=false;
    document.getElementById('krakenTotal').textContent=krakenMoney(data.total_value_usd);
    document.getElementById('krakenKnown').textContent=krakenMoney(data.known_value_usd);
    document.getElementById('krakenAsOf').textContent=new Date(data.as_of).toLocaleString();
    document.getElementById('krakenCoverage').textContent=data.complete?'All nonzero balances priced.':`Total unavailable; missing USD prices for ${data.unpriced_assets.join(', ')}.`;
    const body=document.getElementById('krakenRows');body.replaceChildren();
    for(const position of data.positions) {
        const row=document.createElement('tr');
        const cells=[position.asset,position.raw_asset,krakenNumber(position.balance),krakenMoney(position.price_usd),krakenMoney(position.value_usd),position.price_pair||'No Kraken USD pair'];
        for(const value of cells){const cell=document.createElement('td');cell.textContent=value;if(position.status==='unpriced')cell.classList.add('text-warning');row.appendChild(cell);}
        body.appendChild(row);
    }
}
let krakenRequest=0;
async function loadKrakenPortfolio(force=false) {
    const id=++krakenRequest,button=document.getElementById('krakenRefresh'),status=document.getElementById('krakenStatus');
    button.disabled=true;status.className='alert alert-secondary';status.textContent='Loading Kraken balances…';
    try {const response=await fetch('/api/experimental/kraken-portfolio'+(force?'?refresh=1':''),{headers:{Accept:'application/json'}});const payload=await response.json();if(!response.ok||!payload.success)throw new Error(payload.error||'Kraken request failed.');if(id!==krakenRequest)return;renderKrakenPortfolio(payload.data);status.className=payload.data.complete?'alert alert-info':'alert alert-warning';status.textContent=`${payload.data.positions.length} nonzero Kraken balance(s) loaded.${payload.data.complete?'':' Some positions could not be valued.'}`;}
    catch(error){if(id!==krakenRequest)return;status.className='alert alert-warning';status.textContent=error.message;}
    finally{if(id===krakenRequest)button.disabled=false;}
}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{document.getElementById('krakenRefresh').addEventListener('click',()=>loadKrakenPortfolio(true));loadKrakenPortfolio();});
if(typeof module!=='undefined'&&module.exports)module.exports={krakenNumber,krakenMoney,renderKrakenPortfolio};
