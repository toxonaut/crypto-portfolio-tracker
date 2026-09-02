// Global variables
let historyData = [];
let historyChart = null;
let tradingViewWidget = null;
let isDemoMode = false;
let historyChartEnabled = false;

// Detect iOS Chrome browser
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
const isChrome = /CriOS/.test(navigator.userAgent);
const isIOSChrome = isIOS && isChrome;

// Log browser detection
console.log('Browser detection:', { isIOS, isChrome, isIOSChrome });

// Format price change percentage
function formatPriceChange(change) {
    if (!Number.isFinite(change)) return '<span class="text-muted">—</span>';
    const formattedChange = Math.abs(change).toFixed(2);
    const sign = change >= 0 ? '+' : '-';
    const className = change >= 0 ? 'price-change-positive' : 'price-change-negative';
    
    return `<span class="${className}">${sign}${formattedChange}%</span>`;
}

function formatValueChange(dollarChange, percentChange, historicalValue) {
    const decimalPlaces = Math.abs(dollarChange) < 1 ? 2 : 0;
    const formattedDollar = Math.abs(dollarChange).toLocaleString('en-US', {
        minimumFractionDigits: decimalPlaces, maximumFractionDigits: decimalPlaces
    }).replace(/,/g, "'");
    const formattedPercent = Math.abs(percentChange).toFixed(2);
    
    const className = dollarChange >= 0 ? 'price-change-positive' : 'price-change-negative';
    const dollarSign = dollarChange >= 0 ? '$' : '-$';
    const percentSign = percentChange >= 0 ? '+' : '-';
    
    return `<span class="${className}">${dollarSign}${formattedDollar} (${percentSign}${formattedPercent}%)</span>`;
}

function createTradingViewWidget(symbol) {
    if (tradingViewWidget) {
        tradingViewWidget.remove();
    }

    tradingViewWidget = new TradingView.widget({
        "autosize": true,
        "symbol": `${symbol}`,
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": false,
        "container_id": "tradingview_chart"
    });
}

function initializePairSelection() {
    const buttons = document.querySelectorAll('#pairButtons .list-group-item');
    buttons.forEach(button => {
        if (button.dataset.ready) return;
        button.dataset.ready = 'true';
        button.addEventListener('click', (e) => {
            // Remove active class from all buttons
            buttons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            e.target.classList.add('active');
            // Update chart
            const pair = e.target.dataset.pair;
            if (!isIOSChrome) {
                createTradingViewWidget(pair);
            }
        });
    });
}

// Map CoinGecko coin_id to common ticker symbols (extend as needed)
function getTickerFromCoinId(coinId) {
    const map = {
        'bitcoin': 'BTC',
        'ethereum': 'ETH',
        'solana': 'SOL',
        'binancecoin': 'BNB',
        'ripple': 'XRP',
        'dogecoin': 'DOGE',
        'cardano': 'ADA',
        'polkadot': 'DOT',
        'chainlink': 'LINK',
        'litecoin': 'LTC',
        'tron': 'TRX',
        'avalanche-2': 'AVAX',
        'matic-network': 'MATIC',
        'uniswap': 'UNI',
        'monero': 'XMR',
        'wrapped-bitcoin': 'WBTC',
        'staked-ether': 'STETH',
        'internet-computer': 'ICP',
        'near': 'NEAR',
        'aptos': 'APT',
        'arbitrum': 'ARB',
        'optimism': 'OP',
        'cosmos': 'ATOM',
        'vechain': 'VET',
        'render-token': 'RNDR',
        'fantom': 'FTM',
        'sui': 'SUI',
        'hedera-hashgraph': 'HBAR',
        'algorand': 'ALGO',
        'aave': 'AAVE',
        'the-graph': 'GRT',
    };
    if (map[coinId]) return map[coinId];
    const ticker=String(coinId).toUpperCase();
    return Object.values(map).includes(ticker) ? ticker : null;
}

function renderPairButtons() {
    const container = document.getElementById('pairButtons');
    if (!container) return;
    const selectedPair=container.querySelector('.active')?.dataset.pair;

    // Helper to create a button element
    const createBtn = (label, pair) => {
        const btn = document.createElement('button');
        btn.className = 'list-group-item list-group-item-action';
        btn.dataset.pair = pair;
        btn.textContent = label;
        btn.style.backgroundColor = '#1c243e';
        btn.style.border = '1px solid #050b16';
        btn.style.color = '#e0e0e0';
        return btn;
    };

    // Helper to create a thin divider between groups
    const createDivider = () => {
        const div = document.createElement('div');
        div.style.height = '8px';
        return div;
    };

    container.innerHTML = '';

    try {
        // Build from the New Portfolio Overview's aggregated, signed values.
        const sorted = (typeof newOverviewCurrent!=='undefined'&&newOverviewCurrent?.assets ? newOverviewCurrent.assets : [])
            .filter(asset=>!asset.is_xstocks&&Number.isFinite(asset.total_value))
            .sort((a,b)=>b.total_value-a.total_value);

        // Group 1: USD pairs of the top 5 by holdings (robust to unknown mappings)
        let usdCount = 0;
        for (let i = 0; i < sorted.length && usdCount < 5; i++) {
            const coinId = sorted[i].asset;
            const ticker = getTickerFromCoinId(coinId);
            if (!ticker) continue; // skip unknown mapping
            container.appendChild(createBtn(`${ticker}/USD`, `BINANCE:${ticker}USD`));
            usdCount++;
        }

        // Always offer PAX Gold and Zcash against US dollars.
        container.appendChild(createBtn('PAXG/USD', 'KRAKEN:PAXGUSD'));
        container.appendChild(createBtn('ZEC/USD', 'KRAKEN:ZECUSD'));

        container.appendChild(createDivider());

        // Group 2: BTC pairs of the 5 biggest non-BTC cryptos by dollar value
        let btcCount = 0;
        for (let i = 0; i < sorted.length && btcCount < 5; i++) {
            const coinId = sorted[i].asset;
            const ticker = getTickerFromCoinId(coinId);
            if (!ticker || ticker === 'BTC') continue;
            container.appendChild(createBtn(`${ticker}/BTC`, `BINANCE:${ticker}BTC`));
            btcCount++;
        }

        container.appendChild(createDivider());

        // Group 3: static extras
        container.appendChild(createBtn('SOL/ETH', 'BINANCE:SOLETH'));
        container.appendChild(createBtn('SPY', 'SPY'));
        container.appendChild(createBtn('BTC.D', 'CRYPTOCAP:BTC.D'));

        // If nothing was added (empty portfolio or unknown mappings), fallback to defaults
        if (container.querySelectorAll('.list-group-item').length === 0) {
            ['BINANCE:BTCUSD','BINANCE:ETHUSD','BINANCE:SOLUSD','KRAKEN:PAXGUSD','KRAKEN:ZECUSD','BINANCE:ETHBTC','BINANCE:SOLBTC','BINANCE:SOLETH','SPY','CRYPTOCAP:BTC.D']
                .forEach(sym => {
                    const label = sym === 'CRYPTOCAP:BTC.D' ? 'BTC.D' :
                                  sym === 'SPY' ? 'SPY' :
                                  sym.split(':')[1].replace('USD','/USD').replace('BTC','/BTC');
                    container.appendChild(createBtn(label, sym));
                });
        }
    } catch (e) {
        console.error('Error rendering pair buttons, falling back to defaults', e);
        container.innerHTML = '';
        ['BINANCE:BTCUSD','BINANCE:ETHUSD','BINANCE:SOLUSD','KRAKEN:PAXGUSD','KRAKEN:ZECUSD','BINANCE:ETHBTC','BINANCE:SOLBTC','BINANCE:SOLETH','SPY','CRYPTOCAP:BTC.D']
            .forEach(sym => {
                const label = sym === 'CRYPTOCAP:BTC.D' ? 'BTC.D' :
                              sym === 'SPY' ? 'SPY' :
                              sym.split(':')[1].replace('USD','/USD').replace('BTC','/BTC');
                container.appendChild(createBtn(label, sym));
            });
    }
    initializePairSelection();
    const selected=[...container.querySelectorAll('.list-group-item')].find(button=>button.dataset.pair===selectedPair);
    (selected||container.querySelector('.list-group-item'))?.classList.add('active');
}

// Function to toggle demo mode
function toggleDemoMode() {
    isDemoMode = !isDemoMode;
    if (typeof renderComposition === 'function') renderComposition();
    if (typeof newOverviewCurrent!=='undefined'&&newOverviewCurrent&&typeof renderNewPortfolioOverview==='function') renderNewPortfolioOverview(newOverviewCurrent);

    // Update the status message
    const statusElement = document.getElementById('demoModeStatus');
    if (statusElement) {
        if (isDemoMode) {
            statusElement.style.display = 'block';
        } else {
            statusElement.style.display = 'none';
        }
    }
    
    // Update the active portfolio view with the new mode.
    if (window.location.pathname === '/statistics' && typeof renderNewStatistics === 'function') renderNewStatistics();
    else if (typeof renderNewHistoricalChanges === 'function') renderNewHistoricalChanges();
    if (historyChartPayload) { renderHistoryChart(); renderHistoryFlows(); updateHistoryExtremes(); }
}

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM loaded, initializing...');
    
    // Check if we're on the statistics page
    const isStatisticsPage = window.location.pathname === '/statistics';
    console.log('Current page:', isStatisticsPage ? 'Statistics' : 'Overview');
    historyChartEnabled = false;
    initializeHistoryPanel();
    
    try {
        // For iOS Chrome, show a message instead of loading TradingView
        if (!isStatisticsPage && isIOSChrome) {
            const tvContainer = document.getElementById('tradingview_chart');
            if (tvContainer) {
                tvContainer.innerHTML = '<div class="alert alert-info">Charts are disabled on iOS Chrome for better performance. Please use Safari for full functionality.</div>';
            }
        }
        
        // Load the portfolio data
        console.log('Loading portfolio data...');
        if (isStatisticsPage && typeof updateNewStatistics === 'function') { await updateWorkerHealth(); await updateNewStatistics(); }
        // The Portfolio Overview module owns its initial load and refresh timer.
        console.log('Portfolio data loaded');
        
        // Render dynamic TradingView pair buttons and initialize selection
        if (!isStatisticsPage) {
            initializeMarketOverviewCharts();
            renderPairButtons();
            initializePairSelection();
            // Activate the first button and load its chart by default
            const firstBtn = document.querySelector('#pairButtons .list-group-item');
            if (firstBtn) {
                document.querySelectorAll('#pairButtons .list-group-item').forEach(b => b.classList.remove('active'));
                firstBtn.classList.add('active');
                const firstPair = firstBtn.dataset.pair;
                if (!isIOSChrome) {
                    createTradingViewWidget(firstPair);
                }
            }
        }
        
        console.log('Initialization complete');
        
        // Add event listener for demo mode toggle
        const toggleDemoModeBtn = document.getElementById('toggleDemoButton') || document.getElementById('toggleDemoModeBtn');
        if (toggleDemoModeBtn) {
            toggleDemoModeBtn.addEventListener('click', toggleDemoMode);
        }
        
        // Add event listener for add history button
        const addHistoryBtn = document.getElementById('addHistoryButton') || document.getElementById('addHistoryBtn');
        if (addHistoryBtn) {
            addHistoryBtn.addEventListener('click', async function() {
                try {
                    const response = await fetch('/new-portfolio/add_history', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({})
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        alert('History entry added successfully!');
                        if (isStatisticsPage && typeof updateNewStatistics === 'function') await updateNewStatistics();
                        else if (typeof loadNewPortfolioHistory === 'function') await loadNewPortfolioHistory();
                        if (historyChartEnabled) {
                            updateHistoryChart();
                        }
                    } else {
                        alert('Failed to add history entry: ' + data.error);
                    }
                } catch (error) {
                    console.error('Error adding history:', error);
                    alert('Error adding history: ' + error.message);
                }
            });
        }
        
        // Add event listener for check history button
        const checkHistoryBtn = document.getElementById('checkHistoryButton') || document.getElementById('checkHistoryBtn');
        if (checkHistoryBtn) {
            checkHistoryBtn.addEventListener('click', async function() {
                try {
                    if (isStatisticsPage && typeof updateNewStatistics === 'function') await updateNewStatistics();
                    else if (typeof loadNewPortfolioHistory === 'function') await loadNewPortfolioHistory();
                    const summary=isStatisticsPage?newStatisticsSummary:newOverviewHistory;
                    alert(summary ? 'Comparison snapshots available: ' + Object.values(summary.comparisons).filter(Boolean).length + ' of 3.' : 'History summary unavailable.');
                } catch (error) {
                    console.error('Error checking history status:', error);
                    alert('Error checking history status: ' + error.message);
                }
            });
        }
        
        // Set up auto-refresh with different intervals based on browser
        const refreshInterval = isIOSChrome ? 300000 : 120000; // 5 minutes for iOS Chrome, 2 minutes for others
        if (isStatisticsPage&&typeof updateNewStatistics==='function') setInterval(updateNewStatistics,refreshInterval);
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});
