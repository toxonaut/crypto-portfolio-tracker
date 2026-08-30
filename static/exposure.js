// Gross positive exposure, calculated from the same source balances and prices
// used by /portfolio. Missing prices and liabilities are never shown as 0% risk.
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
            if (!Number.isFinite(amount) || amount < 0 ||
                !Number.isFinite(price) || price <= 0 || !Number.isFinite(value)) {
                excluded += 1;
                continue;
            }
            if (value <= 0) continue;
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
    const currency = value => '$' + (value / (demoMode ? 15 : 1)).toLocaleString('en-US', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).replace(/,/g, "'");
    const status = document.getElementById('exposureStatus');
    status.textContent = exposure.total > 0
        ? `Allocation of ${currency(exposure.total)} in priced, positive holdings.${demoMode ? ' Demo values shown.' : ''}`
        : 'No priced, positive holdings to display. Add holdings or refresh when prices are available.';
    if (exposure.excluded) {
        status.textContent += ` ${exposure.excluded} position(s) excluded because prices or amounts are unavailable, invalid, or negative. Percentages cover only included holdings.`;
    }
    if (priceError) status.textContent += ' Price provider reported an error; this view may be incomplete or use cached prices.';

    for (const [id, entries] of [['assetExposure', exposure.assets], ['platformExposure', exposure.platforms]]) {
        const container = document.getElementById(id);
        container.replaceChildren();
        if (!entries.length) continue;
        const summary = document.createElement('p');
        summary.className = 'exposure-summary';
        summary.textContent = `Largest: ${entries[0][0]} \u00b7 ${(entries[0][1] / exposure.total * 100).toFixed(1)}%`;
        container.appendChild(summary);
        const list = document.createElement('ul');
        list.className = 'exposure-list';
        for (const [name, value] of entries) {
            const share = value / exposure.total * 100;
            const row = document.createElement('li');
            const label = document.createElement('div');
            label.className = 'exposure-label';
            const title = document.createElement('span');
            title.textContent = name;
            const amount = document.createElement('span');
            amount.className = 'exposure-value';
            amount.textContent = `${share > 0 && share < 0.1 ? '<0.1' : share.toFixed(1)}% \u00b7 ${currency(value)}`;
            label.append(title, amount);
            const track = document.createElement('div');
            track.className = 'exposure-track';
            track.setAttribute('aria-hidden', 'true');
            const bar = document.createElement('div');
            bar.className = 'exposure-bar';
            bar.style.width = `${share}%`;
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
