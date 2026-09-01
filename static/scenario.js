// Pure calculations: never mutate portfolio data or write to the server.
function scenarioPositions(portfolio) {
    const positions = [];
    let excluded = 0;
    let unknownYield = 0;
    for (const [coin, details] of Object.entries(portfolio || {})) {
        for (const position of Object.values(details.sources || {})) {
            if (position.amount === 0) continue;
            const value = position.amount * details.price;
            if (!Number.isFinite(position.amount) ||
                !Number.isFinite(details.price) || details.price <= 0 || !Number.isFinite(value)) {
                excluded++;
                continue;
            }
            const validYield = Number.isFinite(position.apy) && position.apy >= 0;
            if (!validYield) unknownYield++;
            positions.push({coin, value, apy: validYield ? position.apy : 0});
        }
    }
    return {positions, excluded, unknownYield};
}

function calculateScenario(positions, changes, contribution, yieldMultiplier) {
    const baseline = positions.reduce((sum, p) => sum + p.value, 0);
    const grossPositive = positions.reduce((sum, p) => sum + Math.max(p.value, 0), 0);
    const contributionApplied = grossPositive > 0 ? contribution : 0;
    let value = 0;
    let income = 0;
    let baselineIncome = 0;
    for (const p of positions) {
        // Contributions buy positive holdings proportionally; they never increase
        // a liability or use the (potentially small/negative) net value as a weight.
        const allocation = p.value > 0 && grossPositive > 0 ? contribution * p.value / grossPositive : 0;
        const projected = (p.value + allocation) * (1 + (changes.get(p.coin) || 0) / 100);
        value += projected;
        income += projected * p.apy / 100 * yieldMultiplier / 12;
        baselineIncome += p.value * p.apy / 100 / 12;
    }
    return {baseline, grossPositive, contributionApplied, baselineIncome, value, income,
        impact: value - baseline - contributionApplied, positionCount: positions.length};
}

const scenarioState = {latest: null, baseline: null, demo: false, changes: new Map(), contribution: 0, yieldMultiplier: 1, stale: false};

function updateScenarioLab(portfolio, demoMode = false, priceError = null) {
    if (!document.getElementById('scenarioLab')) return;
    scenarioState.latest = {data: scenarioPositions(portfolio), priceError, time: new Date().toLocaleTimeString()};
    scenarioState.stale = false;
    const modeChanged = scenarioState.demo !== demoMode;
    scenarioState.demo = demoMode;
    if (!scenarioState.baseline) resetScenarioLab();
    else {
        if (modeChanged) document.getElementById('scenarioContribution').value = scenarioState.contribution / (demoMode ? 15 : 1);
        renderScenarioResults();
    }
}

function resetScenarioLab() {
    if (!scenarioState.latest) return;
    scenarioState.baseline = scenarioState.latest;
    scenarioState.changes.clear();
    scenarioState.contribution = 0;
    scenarioState.yieldMultiplier = 1;
    const contribution = document.getElementById('scenarioContribution');
    contribution.value = 0;
    contribution.removeAttribute('aria-invalid');
    document.getElementById('scenarioInputError').textContent = '';
    const yieldInput = document.getElementById('scenarioYield');
    yieldInput.value = 100;
    document.getElementById('scenarioYieldLabel').textContent = '100%';
    document.getElementById('scenarioReset').disabled = false;
    const container = document.getElementById('scenarioAssets');
    container.replaceChildren();
    const coins = [...new Set(scenarioState.baseline.data.positions.map(p => p.coin))].sort();
    coins.forEach((coin, index) => {
        const row = document.createElement('div');
        row.className = 'scenario-control';
        const label = document.createElement('label');
        label.htmlFor = `scenarioAsset${index}`;
        label.append(document.createTextNode(`${coin}: `));
        const output = document.createElement('output');
        output.htmlFor = label.htmlFor;
        output.textContent = '0%';
        label.appendChild(output);
        const input = document.createElement('input');
        Object.assign(input, {type: 'range', min: '-100', max: '200', step: '1', value: '0', id: label.htmlFor, className: 'form-range'});
        input.addEventListener('input', () => {
            const change = Number(input.value);
            scenarioState.changes.set(coin, change);
            output.textContent = `${change > 0 ? '+' : ''}${change}%`;
            renderScenarioResults();
        });
        row.append(label, input);
        container.appendChild(row);
    });
    contribution.oninput = () => {
        const amount = contribution.valueAsNumber;
        if (!Number.isFinite(amount) || amount < 0 || amount > 1000000000) {
            contribution.setAttribute('aria-invalid', 'true');
            document.getElementById('scenarioInputError').textContent = 'Enter a contribution from 0 to 1,000,000,000. Results retain the last valid amount.';
            return;
        }
        contribution.removeAttribute('aria-invalid');
        document.getElementById('scenarioInputError').textContent = '';
        scenarioState.contribution = amount * (scenarioState.demo ? 15 : 1);
        renderScenarioResults();
    };
    yieldInput.oninput = () => {
        scenarioState.yieldMultiplier = Number(yieldInput.value) / 100;
        document.getElementById('scenarioYieldLabel').textContent = `${yieldInput.value}%`;
        renderScenarioResults();
    };
    document.getElementById('scenarioReset').onclick = resetScenarioLab;
    renderScenarioResults();
}

function renderScenarioResults() {
    const baseline = scenarioState.baseline;
    if (!baseline) return;
    const result = calculateScenario(baseline.data.positions, scenarioState.changes, scenarioState.contribution, scenarioState.yieldMultiplier);
    const money = value => (value < 0 ? '-$' : '$') + (Math.abs(value) / (scenarioState.demo ? 15 : 1)).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}).replace(/,/g, "'");
    const text = (id, value) => { document.getElementById(id).textContent = value; };
    document.getElementById('scenarioContent').hidden = result.positionCount === 0;
    let status = result.positionCount ? `Signed baseline captured at ${baseline.time}. Negative balances are deductions.` : 'No priced holdings available. Reset after portfolio data becomes available.';
    if (scenarioState.demo) status += ' Demo values shown (divided by 15).';
    if (baseline.data.excluded) status += ` ${baseline.data.excluded} position(s) excluded due to missing prices or invalid amounts.`;
    if (scenarioState.contribution > 0 && result.grossPositive <= 0) status += ' The contribution is not applied because there are no positive holdings to allocate it to.';
    if (baseline.data.unknownYield) status += ` ${baseline.data.unknownYield} position(s) have missing or invalid APY; assumed 0%.`;
    if (baseline.priceError) status += ' Baseline price provider reported an error; prices may be incomplete or cached.';
    if (scenarioState.stale) status += ' Portfolio refresh failed; baseline and reset data may be stale.';
    text('scenarioStatus', status);
    text('scenarioValue', money(result.value));
    text('scenarioBaseline', `Baseline ${money(result.baseline)} + contribution ${money(result.contributionApplied)}`);
    text('scenarioImpact', `${result.impact > 0 ? '+' : ''}${money(result.impact)}`);
    text('scenarioIncome', money(result.income));
    text('scenarioIncomeChange', `Baseline ${money(result.baselineIncome)} / month`);
}

function showScenarioError() {
    if (!document.getElementById('scenarioLab')) return;
    scenarioState.stale = true;
    if (scenarioState.baseline) renderScenarioResults();
    else document.getElementById('scenarioStatus').textContent = 'Portfolio unavailable. The lab will load after a successful refresh.';
}
