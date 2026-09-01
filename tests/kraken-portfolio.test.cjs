const test=require('node:test');const assert=require('node:assert/strict');
const {krakenNumber,krakenMoney,renderKrakenPortfolio}=require('../static/kraken-portfolio.js');
test('formatting distinguishes missing values, zero and negative amounts',()=>{assert.equal(krakenMoney(null),'Unavailable');assert.equal(krakenMoney(0),'$0.00');assert.equal(krakenMoney(-1234),"-$1'234.00");assert.equal(krakenNumber(1.234567891),'1.23456789');});
test('renderer uses text only and marks unpriced positions',()=>{
 const nodes=new Map();const el=()=>({hidden:true,textContent:'',title:'',src:'',alt:'',children:[],classList:{values:[],add(v){this.values.push(v);}},replaceChildren(){this.children=[];},appendChild(c){this.children.push(c);}});
 global.document={getElementById(id){if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);},createElement:el};
 try{renderKrakenPortfolio({total_value_usd:null,known_value_usd:3,complete:false,unpriced_assets:['<bad>'],as_of:'2026-09-01T00:00:00Z',hidden_small_positions:0,positions:[{asset:'<img>',origin:'Kraken',balance:2,price_usd:null,value_usd:null,price_pair:null,status:'unpriced'}]});
 assert.equal(nodes.get('krakenTotal').textContent,'Unavailable');assert.match(nodes.get('krakenCoverage').textContent,/<bad>/);const cells=nodes.get('krakenRows').children[0].children;assert.equal(cells[0].children[0].children[1].textContent,'<img>');assert.equal(cells[1].textContent,'Kraken');assert.equal(cells.length,5);assert.ok(cells[2].classList.values.includes('text-warning'));assert.ok(cells[4].classList.values.includes('text-warning'));
 }finally{delete global.document;}
});
test('renderer adds CoinGecko icon and origin',()=>{
 const nodes=new Map();const el=()=>({hidden:true,textContent:'',title:'',src:'',alt:'',children:[],classList:{values:[],add(v){this.values.push(v);}},replaceChildren(){this.children=[];},appendChild(c){this.children.push(c);}});global.document={getElementById(id){if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);},createElement:el};
 try{renderKrakenPortfolio({total_value_usd:100,known_value_usd:100,complete:true,unpriced_assets:[],as_of:'2026-09-01T00:00:00Z',positions:[{asset:'BTC',origin:'Kraken',balance:1,price_usd:100,value_usd:100,price_pair:'XBTUSD',status:'priced',market_data:{coin_id:'bitcoin',image:'https://example.test/btc.png',status:'fresh'}}]});const cells=nodes.get('krakenRows').children[0].children;assert.equal(cells[0].children[0].children[0].src,'https://example.test/btc.png');assert.equal(cells[1].textContent,'Kraken');assert.equal(cells.length,5);}finally{delete global.document;}
});
