// Global variables
let historyData = [];
let historyChart = null;
let tradingViewWidget = null;
let currentDateRange = '90'; // Default to 3 months
let isLogScale = false;
let isDemoMode = false;
let portfolioData = null; // Global portfolio data
let historyChartEnabled = false;

// Detect iOS Chrome browser
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
const isChrome = /CriOS/.test(navigator.userAgent);
const isIOSChrome = isIOS && isChrome;

// Log browser detection
console.log('Browser detection:', { isIOS, isChrome, isIOSChrome });

// Format price change percentage
function formatPriceChange(change) {
    const formattedChange = Math.abs(change).toFixed(2);
    const sign = change >= 0 ? '+' : '-';
    const className = change >= 0 ? 'price-change-positive' : 'price-change-negative';
    
    return `<span class="${className}">${sign}${formattedChange}%</span>`;
}

function formatValueChange(dollarChange, percentChange, historicalValue) {
    const formattedDollar = Math.abs(dollarChange) < 1 ? Math.abs(dollarChange).toFixed(2) : Math.round(Math.abs(dollarChange));
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

// Function to sample data for performance optimization
function sampleHistoryData(data, maxPoints) {
    if (!data || data.length <= maxPoints) return data;
    
    const result = [];
    const step = Math.ceil(data.length / maxPoints);
    
    for (let i = 0; i < data.length; i += step) {
        result.push(data[i]);
    }
    
    // Always include the most recent point
    if (result[result.length - 1] !== data[data.length - 1]) {
        result.push(data[data.length - 1]);
    }
    
    console.log(`Sampled history data from ${data.length} to ${result.length} points`);
    return result;
}

async function updateHistoryChart() {
    try {
        console.log('Fetching history data...');
        const response = await fetch('/history');
        const data = await response.json();
        console.log('History API response:', data);
        
        if (!data.success) {
            console.error('History data error:', data.error);
            return;
        }
        
        // Store the full history data
        historyData = data.data;
        console.log('History data stored:', historyData.length, 'entries');
        
        if (historyData.length === 0) {
            console.warn('No history data available');
            updateHistoryExtremes();
            return;
        }
        
        console.log('First entry:', historyData[0]);
        console.log('Last entry:', historyData[historyData.length - 1]);
        
        // Filter data based on selected date range
        let filteredData = historyData;
        if (currentDateRange !== 'all') {
            const daysToShow = parseInt(currentDateRange);
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - daysToShow);
            
            filteredData = historyData.filter(item => {
                const itemDate = new Date(item.datetime);
                return itemDate >= cutoffDate;
            });
        }
        
        // Apply data sampling for iOS Chrome to prevent crashes
        if (isIOSChrome) {
            // Use more aggressive sampling for iOS Chrome
            const maxDataPoints = 60; // Limit to 60 points for iOS Chrome
            filteredData = sampleHistoryData(filteredData, maxDataPoints);
        }
        
        // Store raw dates for chart formatting
        const rawDates = filteredData.map(item => new Date(item.datetime));
        
        // Format labels for display
        const labels = filteredData.map(item => {
            const date = new Date(item.datetime);
            return date.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });
        });
        
        // Apply demo mode division if active
        const values = filteredData.map(item => {
            let value = item.total_value;
            if (isDemoMode) {
                value = value / 15;
            }
            return value;
        });
        
        // Get BTC values for a secondary dataset
        const btcValues = filteredData.map(item => {
            let value = item.btc || 0;
            if (isDemoMode) {
                value = value / 15;
            }
            return value;
        });

        const hasNonPositiveUsd = values.some(v => v <= 0);
        const hasNonPositiveBtc = btcValues.some(v => v <= 0);
        const effectiveLogScale = isLogScale && !hasNonPositiveUsd && !hasNonPositiveBtc;
        if (isLogScale && !effectiveLogScale) {
            console.warn('Log scale disabled because the dataset contains zero/negative values.');
            isLogScale = false;
            const logScaleToggle = document.getElementById('logScaleToggle');
            if (logScaleToggle) {
                logScaleToggle.checked = false;
            }
            const logScaleSwitch = document.getElementById('logScaleSwitch');
            if (logScaleSwitch) {
                logScaleSwitch.checked = false;
            }
        }

        const hasNegativeUsd = values.some(v => v < 0);
        const hasNegativeBtc = btcValues.some(v => v < 0);
        
        // Check if the chart canvas exists
        const chartCanvas = document.getElementById('historyChart');
        if (!chartCanvas) {
            console.warn('History chart canvas not found');
            return;
        }
        
        if (historyChart) {
            historyChart.destroy();
        }
        
        const ctx = chartCanvas.getContext('2d');
        historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Portfolio Value (USD)',
                        data: values,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        fill: isIOSChrome ? false : true, // Disable fill on iOS Chrome
                        tension: isIOSChrome ? 0 : 0.4, // Disable curve tension on iOS Chrome
                        pointRadius: isIOSChrome ? 0 : 1, // Disable points on iOS Chrome
                        yAxisID: 'y'
                    },
                    {
                        label: 'Portfolio Value (BTC)',
                        data: btcValues,
                        borderColor: '#f7931a',
                        backgroundColor: 'rgba(247, 147, 26, 0.1)',
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y1',
                        pointRadius: isIOSChrome ? 0 : 1, // Disable points for iOS Chrome
                        hidden: isIOSChrome ? true : true // Always hidden on iOS Chrome
                    }
                ]
            },
            options: {
                responsive: true,
                animation: isIOSChrome ? false : true, // Disable animations on iOS Chrome
                responsiveAnimationDuration: isIOSChrome ? 0 : 1000, // Disable animation duration on iOS Chrome
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Portfolio Value History'
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: isIOSChrome ? true : false, // Enable autoSkip for iOS Chrome to improve performance
                            callback: function(value, index) {
                                if (index >= rawDates.length) return '';
                                
                                const date = rawDates[index];
                                const day = date.getDate();
                                const month = date.getMonth();
                                const year = date.getFullYear();
                                const monthName = date.toLocaleString('en-US', { month: 'short' });
                                
                                // Show month name for the first entry of each month
                                if (index === 0) {
                                    return monthName;
                                } else {
                                    const prevDate = rawDates[index - 1];
                                    if (prevDate.getMonth() !== month || 
                                        prevDate.getFullYear() !== year) {
                                        return monthName;
                                    }
                                }
                                
                                // For day numbers, check if this is the first occurrence of this day in this month
                                if (day === 10 || day === 20) {
                                    // Check previous entries in this month to see if we've already shown this day number
                                    let isFirstOccurrence = true;
                                    for (let i = 0; i < index; i++) {
                                        const prevDate = rawDates[i];
                                        if (prevDate.getDate() === day && 
                                            prevDate.getMonth() === month && 
                                            prevDate.getFullYear() === year) {
                                            isFirstOccurrence = false;
                                            break;
                                        }
                                    }
                                    
                                    if (isFirstOccurrence) {
                                        return day;
                                    }
                                }
                                
                                // For shorter ranges, also show 5th, 15th, 25th (with same first-occurrence check)
                                if (filteredData.length <= 60 && (day === 5 || day === 15 || day === 25)) {
                                    let isFirstOccurrence = true;
                                    for (let i = 0; i < index; i++) {
                                        const prevDate = rawDates[i];
                                        if (prevDate.getDate() === day && 
                                            prevDate.getMonth() === month && 
                                            prevDate.getFullYear() === year) {
                                            isFirstOccurrence = false;
                                            break;
                                        }
                                    }
                                    
                                    if (isFirstOccurrence) {
                                        return day;
                                    }
                                }
                                
                                return '';
                            }
                        }
                    },
                    y: {
                        type: effectiveLogScale ? 'logarithmic' : 'linear',
                        position: 'left',
                        beginAtZero: !effectiveLogScale && !hasNegativeUsd,
                        ticks: {
                            callback: function(value) {
                                return '$' + Math.round(value);
                            }
                        },
                        title: {
                            display: true,
                            text: 'USD Value'
                        }
                    },
                    y1: {
                        type: effectiveLogScale ? 'logarithmic' : 'linear',
                        position: 'right',
                        beginAtZero: !effectiveLogScale && !hasNegativeBtc,
                        grid: {
                            drawOnChartArea: false // Only show grid lines for the primary y-axis
                        },
                        ticks: {
                            callback: function(value) {
                                return Math.round(value * 10000) / 10000 + ' BTC';
                            }
                        },
                        title: {
                            display: true,
                            text: 'BTC Value'
                        }
                    }
                }
            }
        });
        
        // Summary values never depend on chart data.
        updateHistoryExtremes();
        
        return true;
    } catch (error) {
        console.error('Error updating history chart:', error);
        return false;
    }
}

async function updatePortfolio() {
    try {
        console.log('Updating portfolio...');
        const response = await fetch('/portfolio');
        const data = await response.json();
        
        if (!data.success) {
            console.error('Portfolio data error:', data.error);
            showHistoricalChangesError();
            if (typeof showExposureError === 'function') showExposureError();
            if (typeof showScenarioError === 'function') showScenarioError();
            return;
        }
        
        console.log('Portfolio data received:', data);

        const priceApiErrorElement = document.getElementById('priceApiError');
        if (priceApiErrorElement) {
            priceApiErrorElement.style.display = 'none';
            priceApiErrorElement.textContent = '';
        }
        
        // Store portfolio data in global variable for use in historical changes calculation
        portfolioData = data;
        if (typeof renderExposure === 'function') renderExposure(data.data, isDemoMode, data.price_error);
        if (typeof updateScenarioLab === 'function') updateScenarioLab(data.data, isDemoMode, data.price_error);
        
        // Update last updated timestamp
        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
            const now = new Date();
            lastUpdatedElement.textContent = now.toLocaleString();
        }
        
        // Get the total monthly yield from the API response
        let totalMonthlyYield = data.total_monthly_yield || 0;
        
        // Clear the table
        const portfolioTable = document.getElementById('portfolioTableBody');
        if (portfolioTable) portfolioTable.innerHTML = '';
        
        // Sort coins by value (descending)
        const sortedCoins = Object.entries(data.data).sort((a, b) => {
            return b[1].total_value - a[1].total_value;
        });

        let hasAnyPositivePrice = false;
        for (const [, details] of sortedCoins) {
            if (typeof details.price === 'number' && details.price > 0) {
                hasAnyPositivePrice = true;
                break;
            }
        }

        // Track bitcoin price for BTC value calculation
        let bitcoinPrice = 0;
        
        // Add rows for each coin
        for (const [coinId, details] of sortedCoins) {
            // Store Bitcoin price for BTC value calculation
            if (coinId === 'bitcoin') {
                bitcoinPrice = details.price;
            }
            
            const row = document.createElement('tr');
            
            // Create coin cell with image and name
            const coinCell = document.createElement('td');
            const coinImage = document.createElement('img');
            coinImage.src = details.image;
            coinImage.alt = coinId;
            coinImage.className = 'coin-icon me-2';
            coinImage.style.width = '24px';
            coinImage.style.height = '24px';
            coinCell.appendChild(coinImage);
            coinCell.appendChild(document.createTextNode(coinId));
            
            // Create other cells
            const totalBalanceCell = document.createElement('td');
            let totalAmount = details.total_amount;
            if (isDemoMode) {
                totalAmount = totalAmount / 15;
            }
            totalBalanceCell.textContent = totalAmount.toFixed(8);
            
            const priceCell = document.createElement('td');
            // Format with apostrophes as thousands separators and 2 decimal places
            priceCell.textContent = '$' + details.price.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).replace(/,/g, "'");
            
            const hourlyChangeCell = document.createElement('td');
            hourlyChangeCell.innerHTML = formatPriceChange(details.hourly_change);
            
            const dailyChangeCell = document.createElement('td');
            dailyChangeCell.innerHTML = formatPriceChange(details.daily_change);
            
            const weeklyChangeCell = document.createElement('td');
            weeklyChangeCell.innerHTML = formatPriceChange(details.seven_day_change);
            
            const valueCell = document.createElement('td');
            let value = details.total_value;
            if (isDemoMode) {
                value = value / 15;
            }
            // Format with apostrophes as thousands separators and 2 decimal places
            valueCell.textContent = '$' + value.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).replace(/,/g, "'");
            
            // Append all cells to the row
            row.appendChild(coinCell);
            row.appendChild(totalBalanceCell);
            row.appendChild(priceCell);
            row.appendChild(hourlyChangeCell);
            row.appendChild(dailyChangeCell);
            row.appendChild(weeklyChangeCell);
            row.appendChild(valueCell);
            
            // Add the row to the table
            if (portfolioTable) portfolioTable.appendChild(row);
        }
        
        // Update total value
        const totalValueElement = document.getElementById('totalValue');
        let totalValue = data.total_value;
        if (isDemoMode) {
            totalValue = totalValue / 15;
        }
        // Format with apostrophes as thousands separators and 2 decimal places
        totalValueElement.textContent = totalValue.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).replace(/,/g, "'");
        
        // Update BTC value
        const btcValueElement = document.getElementById('btcValue');
        if (bitcoinPrice > 0) {
            const btcValue = totalValue / bitcoinPrice;
            btcValueElement.textContent = btcValue.toFixed(8);
        } else {
            btcValueElement.textContent = '0.00';
        }
        
        // Update monthly yield
        const monthlyYieldElement = document.getElementById('monthlyYield');
        if (isDemoMode) {
            totalMonthlyYield = totalMonthlyYield / 15;
        }
        // Format with apostrophes as thousands separators and 2 decimal places
        monthlyYieldElement.textContent = totalMonthlyYield.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).replace(/,/g, "'");
        
        // Refresh only the small summary; chart data loads solely on demand.
        await updateHistorySummary();
        
        // Update historical changes
        updateHistoricalChanges();
        
        console.log('Portfolio update complete');

        if (priceApiErrorElement && sortedCoins.length > 0 && !hasAnyPositivePrice) {
            const reason = data.price_error || 'Price API returned no data.';
            priceApiErrorElement.textContent = `Price data unavailable: ${reason}`;
            priceApiErrorElement.style.display = 'block';
        }
    } catch (error) {
        console.error('Error updating portfolio:', error);
        showHistoricalChangesError();
        if (typeof showExposureError === 'function') showExposureError();
        if (typeof showScenarioError === 'function') showScenarioError();
    }
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
    return map[coinId] || null;
}

function renderPairButtons() {
    const container = document.getElementById('pairButtons');
    if (!container) return;

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
        // Build list from portfolioData if available
        const entries = portfolioData && portfolioData.data ? Object.entries(portfolioData.data) : [];
        const sorted = entries.sort((a, b) => b[1].total_value - a[1].total_value);

        // Group 1: USD pairs of the top 5 by holdings (robust to unknown mappings)
        let usdCount = 0;
        for (let i = 0; i < sorted.length && usdCount < 5; i++) {
            const [coinId] = sorted[i];
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
            const [coinId] = sorted[i];
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
}

// Function to toggle demo mode
function toggleDemoMode() {
    isDemoMode = !isDemoMode;
    if (portfolioData && typeof renderExposure === 'function') {
        renderExposure(portfolioData.data, isDemoMode, portfolioData.price_error);
    }
    
    if (portfolioData && typeof updateScenarioLab === 'function') {
        updateScenarioLab(portfolioData.data, isDemoMode, portfolioData.price_error);
    }

    // Update the status message
    const statusElement = document.getElementById('demoModeStatus');
    if (statusElement) {
        if (isDemoMode) {
            statusElement.style.display = 'block';
        } else {
            statusElement.style.display = 'none';
        }
    }
    
    // Update the portfolio with the new mode
    updatePortfolio();
    
    // Update the historical changes
    updateHistoricalChanges();
    if (historyData.length) updateHistoryExtremes();
}

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM loaded, initializing...');
    
    // Check if we're on the statistics page
    const isStatisticsPage = window.location.pathname === '/statistics';
    console.log('Current page:', isStatisticsPage ? 'Statistics' : 'Overview');
    historyChartEnabled = false;
    
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
        await updatePortfolio();
        console.log('Portfolio data loaded');
        
        // Update historical changes explicitly
        console.log('Explicitly updating historical changes...');
        updateHistoricalChanges();
        
        // Render dynamic TradingView pair buttons and initialize selection
        if (!isStatisticsPage) {
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
        
        // Set up event listeners for date range buttons
        const dateRangeButtons = document.querySelectorAll('[data-range]');
        if (dateRangeButtons.length > 0) {
            dateRangeButtons.forEach(button => {
                button.addEventListener('click', function() {
                    // Remove active class from all buttons
                    dateRangeButtons.forEach(btn => btn.classList.remove('active'));
                    // Add active class to clicked button
                    this.classList.add('active');
                    // Update date range and refresh chart
                    currentDateRange = this.dataset.range;
                    if (historyChartEnabled) {
                        updateHistoryChart();
                    }
                });
            });
        }
        
        // Set up log scale switch
        const logScaleToggle = document.getElementById('logScaleToggle');
        if (logScaleToggle) {
            logScaleToggle.addEventListener('change', function() {
                isLogScale = this.checked;
                if (historyChartEnabled) {
                    updateHistoryChart();
                }
            });
        }
        const logScaleSwitch = document.getElementById('logScaleSwitch');
        if (logScaleSwitch) {
            logScaleSwitch.addEventListener('change', function() {
                isLogScale = this.checked;
                if (historyChartEnabled) {
                    updateHistoryChart();
                }
            });
        }

        const loadHistoryDataBtn = document.getElementById('loadHistoryDataBtn');
        if (loadHistoryDataBtn) {
            loadHistoryDataBtn.addEventListener('click', async function() {
                const placeholder = document.getElementById('historyChartPlaceholder');
                const container = document.getElementById('historyChartContainer');

                if (container) {
                    container.style.display = '';
                }
                if (placeholder) {
                    placeholder.style.display = 'none';
                }

                loadHistoryDataBtn.disabled = true;
                try {
                    historyChartEnabled = true;
                    const loaded = await updateHistoryChart();
                    if (!loaded) {
                        historyChartEnabled = false;
                        if (container) container.style.display = 'none';
                        if (placeholder) placeholder.style.display = '';
                        loadHistoryDataBtn.textContent = 'No chart data loaded — retry';
                    }
                    updateHistoricalChanges();
                } finally {
                    loadHistoryDataBtn.disabled = false;
                }
            });
        }
        
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
                    const response = await fetch('/add_history', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            total_value: parseFloat(document.getElementById('totalValue').innerText)
                        })
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        alert('History entry added successfully!');
                        await updateHistorySummary();
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
                    await updateHistorySummary();
                    alert(historySummaryError ? 'History summary unavailable.' :
                        'Comparison snapshots available: ' + Object.values(historySummary.comparisons).filter(Boolean).length + ' of 3.');
                } catch (error) {
                    console.error('Error checking history status:', error);
                    alert('Error checking history status: ' + error.message);
                }
            });
        }
        
        // Set up auto-refresh with different intervals based on browser
        const refreshInterval = isIOSChrome ? 300000 : 120000; // 5 minutes for iOS Chrome, 2 minutes for others
        setInterval(updatePortfolio, refreshInterval);
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});
