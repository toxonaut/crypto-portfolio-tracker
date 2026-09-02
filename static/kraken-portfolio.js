function krakenNumber(value, digits=8) { return Number.isFinite(value) ? value.toLocaleString('en-US',{maximumFractionDigits:digits}).replace(/,/g,"'") : 'Unavailable'; }
function krakenMoney(value) { return Number.isFinite(value) ? (value<0?'-$':'$')+Math.abs(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).replace(/,/g,"'") : 'Unavailable'; }
function krakenApy(value) { return Number.isFinite(value) ? value.toFixed(2) : 'Unavailable'; }
function editorStatus(message,type='secondary'){const status=document.getElementById('newPortfolioFormStatus');status.hidden=false;status.className=`alert alert-${type} mt-3`;status.textContent=message;}
function manualInput(position,field,type,value,options={}){const input=document.createElement('input');input.type=type;input.value=value;input.classList.add('form-control','form-control-sm');input.setAttribute('aria-label',options.label||field);if(options.step)input.step=options.step;if(options.min!==undefined)input.min=String(options.min);if(options.max!==undefined)input.max=String(options.max);input.addEventListener('change',async()=>{try{input.disabled=true;const updated={origin:position.origin,amount:position.balance,apy:position.apy,[field]:type==='number'?Number(input.value):input.value.trim()};await updateManualEntry(position.entry_id,updated);editorStatus('Entry updated.','success');await loadKrakenPortfolio(true);}catch(error){editorStatus(error.message,'warning');await loadKrakenPortfolio(true);}finally{input.disabled=false;}});return input;}
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
        const originCell=document.createElement('td');if(position.editable)originCell.appendChild(manualInput(position,'origin','text',position.origin,{label:`${position.asset} origin`}));else originCell.textContent=position.origin||'Unknown';row.appendChild(originCell);
        const balanceCell=document.createElement('td');if(position.editable)balanceCell.appendChild(manualInput(position,'amount','number',String(position.balance),{label:`${position.asset} total balance`,step:'any'}));else balanceCell.textContent=krakenNumber(position.balance);row.appendChild(balanceCell);
        const apyCell=document.createElement('td');if(position.editable)apyCell.appendChild(manualInput(position,'apy','number',krakenApy(position.apy),{label:`${position.asset} APY yield percent`,step:'0.01',min:0,max:10000}));else{apyCell.textContent=krakenApy(position.apy);apyCell.title=position.apy_source||'';if(!Number.isFinite(position.apy))apyCell.classList.add('text-muted');}row.appendChild(apyCell);
        const priceCell=document.createElement('td');priceCell.textContent=krakenMoney(position.price_usd);if(position.status==='unpriced')priceCell.classList.add('text-warning');row.appendChild(priceCell);
        const valueCell=document.createElement('td');valueCell.textContent=krakenMoney(position.value_usd);if(position.status==='unpriced')valueCell.classList.add('text-warning');row.appendChild(valueCell);
        const actionCell=document.createElement('td');
        if(position.editable&&Number.isInteger(position.entry_id)){const remove=document.createElement('button');remove.type='button';remove.classList.add('btn','btn-sm','btn-outline-danger');remove.textContent='Remove';remove.addEventListener('click',async()=>{try{await removeManualEntry(position.entry_id);}catch(error){const status=document.getElementById('newPortfolioFormStatus');status.hidden=false;status.className='alert alert-warning mt-3';status.textContent=error.message;}});actionCell.appendChild(remove);}else actionCell.textContent='—';
        row.appendChild(actionCell);
        body.appendChild(row);
    }
}
async function removeManualEntry(entryId) {
    if(typeof window!=='undefined'&&!window.confirm('Remove this manual portfolio entry?'))return;
    const response=await fetch(`/api/new-portfolio/manual/${entryId}`,{method:'DELETE',headers:{Accept:'application/json'}}),payload=await response.json();
    if(!response.ok||!payload.success)throw new Error(payload.error||'Entry could not be removed.');
    await loadKrakenPortfolio(true);
}
async function updateManualEntry(entryId,body) {
    const response=await fetch(`/api/new-portfolio/manual/${entryId}`,{method:'PATCH',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(body)}),payload=await response.json();
    if(!response.ok||!payload.success)throw new Error(payload.error||'Entry could not be updated.');
}
async function addManualEntry(event) {
    event.preventDefault();const form=event.currentTarget,button=document.getElementById('newPortfolioAdd'),status=document.getElementById('newPortfolioFormStatus');
    button.disabled=true;status.hidden=false;status.className='alert alert-secondary mt-3';status.textContent='Saving entry…';
    try {
        const body={coin_id:document.getElementById('newCoinId').value.trim(),origin:document.getElementById('newOrigin').value.trim(),amount:Number(document.getElementById('newAmount').value),apy:Number(document.getElementById('newApy').value)};
        const response=await fetch('/api/new-portfolio/manual',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(body)}),payload=await response.json();
        if(!response.ok||!payload.success)throw new Error(payload.error||'Entry could not be saved.');
        form.reset();document.getElementById('newApy').value='0';status.className='alert alert-success mt-3';status.textContent='Entry added.';await loadKrakenPortfolio(true);
    } catch(error){status.className='alert alert-warning mt-3';status.textContent=error.message;} finally{button.disabled=false;}
}
let krakenRequest=0;
async function loadKrakenPortfolio(force=false) {
    const id=++krakenRequest,button=document.getElementById('krakenRefresh'),status=document.getElementById('krakenStatus');
    button.disabled=true;status.className='alert alert-secondary';status.textContent='Loading Kraken balances…';
    try {const response=await fetch('/api/experimental/kraken-portfolio'+(force?'?refresh=1':''),{headers:{Accept:'application/json'}});const payload=await response.json();if(!response.ok||!payload.success)throw new Error(payload.error||'Kraken request failed.');if(id!==krakenRequest)return;renderKrakenPortfolio(payload.data);status.className=payload.data.complete?'alert alert-info':'alert alert-warning';status.textContent=`${payload.data.positions.length} position(s) shown.${payload.data.hidden_small_positions?` ${payload.data.hidden_small_positions} position(s) below $10 hidden.`:''}${payload.data.complete?'':' Some positions could not be valued.'}`;}
    catch(error){if(id!==krakenRequest)return;status.className='alert alert-warning';status.textContent=error.message;}
    finally{if(id===krakenRequest)button.disabled=false;}
}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{document.getElementById('krakenRefresh').addEventListener('click',()=>loadKrakenPortfolio(true));document.getElementById('newPortfolioForm').addEventListener('submit',addManualEntry);loadKrakenPortfolio();});
if(typeof module!=='undefined'&&module.exports)module.exports={krakenNumber,krakenMoney,krakenApy,renderKrakenPortfolio};
