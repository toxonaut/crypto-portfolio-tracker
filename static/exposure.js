// Net exposure: signed balances reduce both asset and platform totals.
// Invalid or missing prices are excluded explicitly.
function calculateExposure(portfolio) {
    const assets = new Map();
    const platforms = new Map();
    let excluded = 0;
    for (const [coin, details] of Object.entries(portfolio || {})) {
        for (const [source, position] of Object.entries(details.sources || {})) {
            const amount = position.amount;
            const price = details.price;
            if (amount === 0) continue;
            const value = amount * price;
            if (!Number.isFinite(amount) ||
                !Number.isFinite(price) || price <= 0 || !Number.isFinite(value)) {
                excluded += 1;
                continue;
            }
            const platform = source.trim() || 'Unspecified';
            assets.set(coin, (assets.get(coin) || 0) + value);
            platforms.set(platform, (platforms.get(platform) || 0) + value);
        }
    }
    const ranked = map => [...map.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    return {
        assets: ranked(assets), platforms: ranked(platforms), excluded,
        total: [...assets.values()].reduce((sum, value) => sum + value, 0)
    };
}

function renderExposure(portfolio, demoMode = false, priceError = null) {
    const root = document.getElementById('exposureMap');
    if (!root) return;
    const exposure = calculateExposure(portfolio);
    const currency = value => (value < 0 ? '-$' : '$') + (Math.abs(value) / (demoMode ? 15 : 1)).toLocaleString('en-US', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).replace(/,/g, "'");
    const status = document.getElementById('exposureStatus');
    const percentage = value => exposure.total > 0
        ? `${(value / exposure.total * 100).toFixed(1)}%` : 'Share unavailable';
    status.textContent = exposure.assets.length
        ? `Net priced holdings: ${currency(exposure.total)}. Negative balances are subtracted. ${exposure.total > 0 ? 'Shares use net value and may exceed 100%.' : 'Percentage shares are unavailable when net value is zero or negative.'} Bars show relative value, with deductions left of zero.${demoMode ? ' Demo values shown.' : ''}`
        : 'No priced holdings to display. Add holdings or refresh when prices are available.';
    if (exposure.excluded) {
        status.textContent += ` ${exposure.excluded} position(s) excluded because prices or amounts are unavailable or invalid. Percentages cover only included holdings.`;
    }
    if (priceError) status.textContent += ' Price provider reported an error; this view may be incomplete or use cached prices.';

    for (const [id, entries] of [['assetExposure', exposure.assets], ['platformExposure', exposure.platforms]]) {
        const container = document.getElementById(id);
        container.replaceChildren();
        if (!entries.length) continue;
        const summary = document.createElement('p');
        summary.className = 'exposure-summary';
        summary.textContent = `Highest net value: ${entries[0][0]} · ${currency(entries[0][1])}`;
        container.appendChild(summary);
        const list = document.createElement('ul');
        list.className = 'exposure-list';
        const scale = Math.max(...entries.map(([, value]) => Math.abs(value)), 1);
        for (const [name, value] of entries) {
            const row = document.createElement('li');
            const label = document.createElement('div');
            label.className = 'exposure-label';
            const title = document.createElement('span');
            title.textContent = name;
            const amount = document.createElement('span');
            amount.className = 'exposure-value';
            amount.textContent = `${percentage(value)} · ${currency(value)}`;
            label.append(title, amount);
            const track = document.createElement('div');
            track.className = 'exposure-track';
            track.setAttribute('aria-hidden', 'true');
            const bar = document.createElement('div');
            bar.className = value < 0 ? 'exposure-bar exposure-negative' : 'exposure-bar';
            const width = Math.abs(value) / scale * 50;
            bar.style.width = `${width}%`;
            bar.style.left = `${value < 0 ? 50 - width : 50}%`;
            track.appendChild(bar);
            row.append(label, track);
            list.appendChild(row);
        }
        container.appendChild(list);
    }
}

function showExposureError() {
    const status = document.getElementById('exposureStatus');
    if (status) status.textContent = 'Portfolio refresh failed. Any allocation shown is from the last successful update.';
}

if (typeof module !== 'undefined' && module.exports) module.exports = {calculateExposure, renderExposure};
