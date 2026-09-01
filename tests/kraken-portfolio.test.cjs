const test=require('node:test');const assert=require('node:assert/strict');
const {krakenNumber,krakenMoney,renderKrakenPortfolio}=require('../static/kraken-portfolio.js');
test('formatting distinguishes missing values, zero and negative amounts',()=>{assert.equal(krakenMoney(null),'Unavailable');assert.equal(krakenMoney(0),'$0.00');assert.equal(krakenMoney(-1234),"-$1'234.00");assert.equal(krakenNumber(1.234567891),'1.23456789');});
test('renderer uses text only and marks unpriced positions',()=>{
 const nodes=new Map();const el=()=>({hidden:true,textContent:'',children:[],classList:{values:[],add(v){this.values.push(v);}},replaceChildren(){this.children=[];},appendChild(c){this.children.push(c);}});
 global.document={getElementById(id){if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);},createElement:el};
 try{renderKrakenPortfolio({total_value_usd:null,known_value_usd:3,complete:false,unpriced_assets:['<bad>'],as_of:'2026-09-01T00:00:00Z',positions:[{asset:'<img>',raw_asset:'<raw>',balance:2,price_usd:null,value_usd:null,price_pair:null,status:'unpriced'}]});
 assert.equal(nodes.get('krakenTotal').textContent,'Unavailable');assert.match(nodes.get('krakenCoverage').textContent,/<bad>/);const cells=nodes.get('krakenRows').children[0].children;assert.equal(cells[0].textContent,'<img>');assert.ok(cells.every(c=>c.classList.values.includes('text-warning')));
 }finally{delete global.document;}
});
