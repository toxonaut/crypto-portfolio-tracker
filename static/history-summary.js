// Summary data is independent of the on-demand chart and never contains full history.
let historySummary = null;
let historySummaryError = false;

async function updateHistorySummary() {
    try {
        const response = await fetch('/history/summary');
        const payload = await response.json();
        if (!response.ok || !payload.success || !payload.data?.comparisons) throw new Error('Summary unavailable');
        historySummary = payload.data;
        historySummaryError = false;
    } catch (error) {
        historySummary = null;
        historySummaryError = true;
        console.error('History summary unavailable:', error);
    }
    updateHistoricalChanges();
}

function calculateSummaryChanges(summary, currentValue, demoMode = false) {
    const changes = {};
    for (const name of ['change24h', 'change7d', 'change30d']) {
        const sample = summary?.comparisons?.[name];
        changes[name] = sample && Number.isFinite(sample.total_value) && sample.total_value > 0 && Number.isFinite(currentValue) && currentValue >= 0
            ? {value: (currentValue - sample.total_value) / (demoMode ? 15 : 1),
                percent: (currentValue - sample.total_value) / sample.total_value * 100,
                date: sample.datetime}
            : null;
    }
    return changes;
}

function updateHistoricalChanges() {
    const currentValue = portfolioData?.price_error ? null : portfolioData?.total_value;
    const changes = calculateSummaryChanges(historySummary, currentValue, isDemoMode);
    for (const [name, change] of Object.entries(changes)) {
        document.querySelectorAll(`#${name}`).forEach(element => {
            if (!change) {
                element.textContent = 'Unavailable';
                element.title = historySummaryError ? 'History summary could not be loaded.' : 'Current value or a valid historical snapshot within 12 hours of the target is unavailable.';
                return;
            }
            element.innerHTML = formatValueChange(change.value, change.percent);
            // Preserve the server timestamp without pretending naive stored dates have a timezone.
            element.title = `Compared with snapshot ${change.date.replace('T', ' ')} (server time). Portfolio value change includes deposits and withdrawals.`;
        });
    }
}

// Only called after chart data is explicitly requested, or when changing demo mode.
function updateHistoryExtremes() {
    const ids = ['largestPercentGain', 'largestDollarGain', 'largestPercentLoss', 'largestDollarLoss'];
    if (!ids.some(id => document.getElementById(id))) return;
    const best = historyChartPayload?.extremes || {};
    for (const id of ids) {
        const element=document.getElementById(id);
        if(!element) continue;
        const original=best[id];
        const change=original ? {...original, value: original.value/(isDemoMode ? 15 : 1)} : null;
        element.textContent=change ? `${id.includes('Percent') ? change.percent.toFixed(2)+'%' : '$'+change.value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}).replace(/,/g, "'")} (${change.date})` : 'Unavailable';
    }
}

function showHistoricalChangesError() {
    for (const id of ['change24h', 'change7d', 'change30d']) {
        document.querySelectorAll(`#${id}`).forEach(element => {
            element.textContent = 'Unavailable';
            element.title = 'Current portfolio value could not be refreshed.';
        });
    }
}

async function updateWorkerHealth() {
    const element = document.getElementById('workerHealth');
    if (!element) return;
    try {
        const response = await fetch('/worker_status');
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error();
        const data = payload.data;
        const success = data.last_success ? new Date(data.last_success).toLocaleString() : 'not yet recorded';
        const attempt = data.last_attempt ? new Date(data.last_attempt).toLocaleString() : 'none';
        const issue = !data.configured || data.overdue || data.last_error;
        element.className = issue ? 'alert alert-warning' : 'alert alert-success';
        element.textContent = `Automatic history: last success ${success}; last attempt ${attempt}. Scheduled every ${data.interval_seconds / 60} minutes.`;
        if (!data.configured) element.textContent += ' Configure the same dedicated WORKER_KEY on the web and worker services.';
        else if (data.overdue) element.textContent += ' Updates are overdue; check the Railway worker.';
        if (data.last_error) element.textContent += ` Last error: ${data.last_error}`;
    } catch (_) {
        element.className = 'alert alert-warning';
        element.textContent = 'Automatic history status is unavailable. Check Railway service health.';
    }
}
