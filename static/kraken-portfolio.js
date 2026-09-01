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
        const market=position.market_data||{},assetCell=document.createElement('td'),identity=document.createElement('div');identity.classList.add('kraken-asset');
        if(market.image){const icon=document.createElement('img');icon.src=market.image;icon.alt='';icon.classList.add('coin-logo');identity.appendChild(icon);}
        else {const fallback=document.createElement('span');fallback.classList.add('kraken-asset-fallback');fallback.textContent=position.asset.slice(0,2).toUpperCase();identity.appendChild(fallback);}
        const name=document.createElement('span');name.textContent=position.asset;name.title=`Kraken price: ${position.price_pair||'No USD pair'}${market.coin_id?`; icon: CoinGecko (${market.status||'unknown'})`:'; CoinGecko icon unavailable'}`;identity.appendChild(name);assetCell.appendChild(identity);row.appendChild(assetCell);
        const originCell=document.createElement('td');originCell.textContent=position.origin||'Unknown';row.appendChild(originCell);
        for(const value of [krakenNumber(position.balance),krakenMoney(position.price_usd)]){const cell=document.createElement('td');cell.textContent=value;if(position.status==='unpriced')cell.classList.add('text-warning');row.appendChild(cell);}
        const valueCell=document.createElement('td');valueCell.textContent=krakenMoney(position.value_usd);if(position.status==='unpriced')valueCell.classList.add('text-warning');row.appendChild(valueCell);
        body.appendChild(row);
    }
}
let krakenRequest=0;
async function loadKrakenPortfolio(force=false) {
    const id=++krakenRequest,button=document.getElementById('krakenRefresh'),status=document.getElementById('krakenStatus');
    button.disabled=true;status.className='alert alert-secondary';status.textContent='Loading Kraken balances…';
    try {const response=await fetch('/api/experimental/kraken-portfolio'+(force?'?refresh=1':''),{headers:{Accept:'application/json'}});const payload=await response.json();if(!response.ok||!payload.success)throw new Error(payload.error||'Kraken request failed.');if(id!==krakenRequest)return;renderKrakenPortfolio(payload.data);status.className=payload.data.complete?'alert alert-info':'alert alert-warning';status.textContent=`${payload.data.positions.length} position(s) shown.${payload.data.hidden_small_positions?` ${payload.data.hidden_small_positions} position(s) below $10 hidden.`:''}${payload.data.complete?'':' Some positions could not be valued.'}`;}
    catch(error){if(id!==krakenRequest)return;status.className='alert alert-warning';status.textContent=error.message;}
    finally{if(id===krakenRequest)button.disabled=false;}
}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{document.getElementById('krakenRefresh').addEventListener('click',()=>loadKrakenPortfolio(true));loadKrakenPortfolio();});
if(typeof module!=='undefined'&&module.exports)module.exports={krakenNumber,krakenMoney,renderKrakenPortfolio};
