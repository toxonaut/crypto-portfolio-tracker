/* Keep unavailable observations distinct from measured zero values. */
(function(root) {
    function money(value) {
        return Number.isFinite(value) ? value.toLocaleString('en-US', {
            minimumFractionDigits:2, maximumFractionDigits:2
        }).replace(/,/g, "'") : 'Unavailable';
    }
    function label(quote) {
        if (!quote || quote.status === 'missing') return 'Price unavailable';
        return `${quote.status === 'stale' ? 'Stale / last known' : quote.cached ? 'Cached' : 'Current'} · ${quote.source} · As of ${new Date(quote.as_of).toLocaleString()}`;
    }
    function summary(quality) {
        if (!quality) return '';
        if (!quality.complete) return `Incomplete pricing (${quality.priced_assets}/${quality.required_assets} assets). Missing: ${quality.missing.join(', ')}. Portfolio totals and historical comparisons are unavailable.`;
        if (!quality.fresh) return `Estimated valuation using last-known prices: ${quality.stale.join(', ')}. Historical comparisons are unavailable until prices recover.`;
        return `Price coverage: ${quality.priced_assets}/${quality.required_assets} assets. Crypto quotes are at most 15 minutes old; CHF uses the latest available daily reference rate.`;
    }
    const api = {money, label, summary};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.PriceQuality = api;
})(typeof window === 'undefined' ? globalThis : window);
