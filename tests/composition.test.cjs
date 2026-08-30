const test=require('node:test');
const assert=require('node:assert/strict');
const {compositionGroups,compositionSeries}=require('../static/composition.js');
const rows=[{total_value:80,positions:[{coin_id:'btc',source:'Wallet',value_usd:100},{coin_id:'btc',source:'Loan',value_usd:-20}]},
    {total_value:200,positions:[{coin_id:'eth',source:'Wallet',value_usd:200}]}];
test('composition preserves signed assets and platform deductions',()=>{
    assert.equal(compositionGroups(rows[0],'coin_id').get('btc'),80);
    assert.equal(compositionGroups(rows[0],'source').get('Loan'),-20);
    const data=compositionSeries(rows,'source','share');
    assert.deepEqual(data.find(d=>d.label==='Loan').data,[-25,0]);
    assert.deepEqual(data.find(d=>d.label==='Wallet').data,[125,100]);
});
test('removed assets become zero only in complete recorded snapshots',()=>{
    assert.deepEqual(compositionSeries(rows,'coin_id','usd'),[{label:'btc',data:[80,0]},{label:'eth',data:[0,200]}]);
});
test('demo scales dollars, not shares; nonpositive net shares are unavailable',()=>{
    assert.equal(compositionSeries(rows,'coin_id','usd',true)[0].data[0],80/15);
    assert.deepEqual(compositionSeries(rows,'source','share',true),compositionSeries(rows,'source','share'));
    assert.equal(compositionSeries([{...rows[0],total_value:0}],'coin_id','share')[0].data[0],null);
    assert.equal(compositionSeries([{...rows[0],total_value:-1}],'coin_id','share')[0].data[0],null);
});
const vm=require('node:vm');
const fs=require('node:fs');
test('UI loads composition only on demand and inspects saved signed quantities',async()=>{
    const nodes=new Map();
    const element=()=>({value:'',hidden:false,disabled:false,children:[],addEventListener(){},replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);}});
    const document={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element,addEventListener(){}};
    document.getElementById('compositionRange').value='30';
    document.getElementById('compositionGroup').value='coin_id';
    document.getElementById('compositionMetric').value='usd';
    let requests=0;
    const payload={success:true,next_before:null,data:[{history_id:1,date:'2026-08-30T12:00:00Z',total_value:-20,positions:[{coin_id:'btc',source:'Loan',amount:-2,price_usd:10,value_usd:-20}]}]};
    const context=vm.createContext({document,AbortController,Chart:function(){this.destroy=()=>{};},fetch:async()=>{requests++;return {ok:true,json:async()=>payload};}});
    vm.runInContext(fs.readFileSync(require.resolve('../static/composition.js'),'utf8'),context);
    assert.equal(requests,0);
    await vm.runInContext('loadComposition()',context);
    assert.equal(requests,1);
    assert.equal(nodes.get('compositionContent').hidden,false);
    const cells=nodes.get('compositionRows').children[0].children;
    assert.equal(cells[2].textContent,'-2');
    assert.equal(cells[4].textContent,'-$20');
    assert.equal(cells[5].textContent,'Unavailable');
    assert.equal(nodes.get('olderComposition').disabled,true);
    vm.runInContext('renderComposition()',context);
    assert.equal(requests,1);
});
