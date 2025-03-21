let historyChart = null;
let isDemoMode = false; // Track demo mode state

function formatPriceChange(change) {
    const formattedChange = change.toFixed(2);
    const className = change >= 0 ? 'price-change-positive' : 'price-change-negative';
    const sign = change >= 0 ? '+' : '';
    return `<span class="${className}">${sign}${formattedChange}%</span>`;
}

let tradingViewWidget = null;

function createTradingViewWidget(symbol) {
    if (tradingViewWidget) {
        tradingViewWidget.remove();
    }

    tradingViewWidget = new TradingView.widget({
        "width": "100%",
        "height": 500,
        "symbol": `BINANCE:${symbol}`,
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
    const buttons = document.querySelectorAll('.list-group-item');
    buttons.forEach(button => {
        button.addEventListener('click', (e) => {
            // Remove active class from all buttons
            buttons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            e.target.classList.add('active');
            // Update chart
            const pair = e.target.dataset.pair;
            createTradingViewWidget(pair);
        });
    });
}

async function updateHistoryChart() {
    try {
        console.log('Fetching history data...');
        const response = await fetch('/history');
        const data = await response.json();
        console.log('History data:', data);
        
        if (!data.success) {
            console.error('History data error:', data.error);
            return;
        }
        
        const labels = data.data.map(item => {
            const date = new Date(item.datetime);
            return date.toLocaleString();
        });
        
        // Apply demo mode division if active
        const values = data.data.map(item => {
            let value = item.total_value;
            if (isDemoMode) {
                value = value / 15;
            }
            return value;
        });
        
        if (historyChart) {
            historyChart.destroy();
        }
        
        const ctx = document.getElementById('historyChart').getContext('2d');
        historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Portfolio Value (USD)',
                    data: values,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
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
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error updating history chart:', error);
    }
}

async function updatePortfolio() {
    try {
        console.log('Starting portfolio update...');
        const response = await fetch('/portfolio');
        console.log('Portfolio response:', response);
        
        const data = await response.json();
        console.log('Portfolio data:', data);
        
        if (!data.success) {
            console.error('Portfolio data error:', data.error);
            return;
        }
        
        const portfolioTable = document.getElementById('portfolioTableBody');
        if (!portfolioTable) {
            console.error('Could not find portfolioTableBody element');
            return;
        }
        
        console.log('Clearing table...');
        portfolioTable.innerHTML = '';
        
        console.log('Processing portfolio entries...');
        for (const [coinId, details] of Object.entries(data.data)) {
            console.log(`Processing coin: ${coinId}`, details);
            
            const row = document.createElement('tr');
            
            // Asset column with icon and name
            const coinCell = document.createElement('td');
            coinCell.innerHTML = `
                <div class="d-flex align-items-center">
                    <img src="${details.image || ''}" alt="${coinId}" class="coin-logo me-2" style="width: 24px; height: 24px;">
                    <span class="text-capitalize">${coinId.replace('-', ' ')}</span>
                </div>
            `;
            
            // Total Balance column - apply demo mode division if active
            const totalBalanceCell = document.createElement('td');
            let totalAmount = details.total_amount;
            if (isDemoMode) {
                totalAmount = totalAmount / 15;
            }
            totalBalanceCell.textContent = totalAmount.toFixed(4);
            
            // Price column
            const priceCell = document.createElement('td');
            priceCell.textContent = `$${details.price.toFixed(4)}`;
            
            // Price change columns
            const hourlyChangeCell = document.createElement('td');
            hourlyChangeCell.innerHTML = details.hourly_change ? formatPriceChange(details.hourly_change) : '-';
            
            const dailyChangeCell = document.createElement('td');
            dailyChangeCell.innerHTML = details.daily_change ? formatPriceChange(details.daily_change) : '-';
            
            const weeklyChangeCell = document.createElement('td');
            weeklyChangeCell.innerHTML = details.seven_day_change ? formatPriceChange(details.seven_day_change) : '-';
            
            // Value column - apply demo mode division if active
            const valueCell = document.createElement('td');
            let totalValue = details.total_value;
            if (isDemoMode) {
                totalValue = totalValue / 15;
            }
            valueCell.textContent = `$${totalValue.toFixed(2)}`;
            
            // Add all cells to the row
            row.appendChild(coinCell);
            row.appendChild(totalBalanceCell);
            row.appendChild(priceCell);
            row.appendChild(hourlyChangeCell);
            row.appendChild(dailyChangeCell);
            row.appendChild(weeklyChangeCell);
            row.appendChild(valueCell);
            
            portfolioTable.appendChild(row);
        }
        
        console.log('Updating total value...');
        const totalValueElement = document.getElementById('totalValue');
        if (totalValueElement) {
            // Apply demo mode division if active
            let totalValue = data.total_value;
            if (isDemoMode) {
                totalValue = totalValue / 15;
            }
            totalValueElement.textContent = totalValue.toFixed(2);
        } else {
            console.error('Could not find totalValue element');
        }
        
        // Update monthly yield
        console.log('Updating monthly yield...');
        const monthlyYieldElement = document.getElementById('monthlyYield');
        if (monthlyYieldElement) {
            // Apply demo mode division if active
            let monthlyYield = data.total_monthly_yield;
            if (isDemoMode) {
                monthlyYield = monthlyYield / 15;
            }
            monthlyYieldElement.textContent = monthlyYield.toFixed(2);
        } else {
            console.error('Could not find monthlyYield element');
        }
        
        // Update last updated timestamp
        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
            const now = new Date();
            lastUpdatedElement.textContent = now.toLocaleString();
        }
        
        // Update history chart
        console.log('Updating history chart...');
        await updateHistoryChart();
        
        console.log('Portfolio update complete');
    } catch (error) {
        console.error('Error updating portfolio:', error);
    }
}

// Function to toggle demo mode
function toggleDemoMode() {
    isDemoMode = !isDemoMode;
    
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
}

// Initialize TradingView chart with default pair (BTC/USD) and start updates
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing...');
    createTradingViewWidget('BTCUSD');
    initializePairSelection();
    updatePortfolio();
    
    // Set up demo mode toggle button
    const toggleButton = document.getElementById('toggleDemoMode');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleDemoMode);
    }
    
    // Set up add history button
    const addHistoryButton = document.getElementById('addHistory');
    if (addHistoryButton) {
        addHistoryButton.addEventListener('click', async () => {
            try {
                const totalValueElement = document.getElementById('totalValue');
                const totalValue = parseFloat(totalValueElement.textContent.replace('$', ''));
                const response = await fetch('/add_history', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ total_value: totalValue })
                });
                const result = await response.json();
                if (result.success) {
                    alert('History added successfully!');
                } else {
                    alert('Failed to add history: ' + result.error);
                }
            } catch (error) {
                alert('Error adding history: ' + error.message);
            }
        });
    }
    
    // Refresh portfolio data every 60 seconds
    setInterval(updatePortfolio, 60000);
});
