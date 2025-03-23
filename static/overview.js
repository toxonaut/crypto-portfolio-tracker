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
        console.log('Fetching portfolio data...');
        const response = await fetch('/portfolio');
        const data = await response.json();
        
        if (!data.success) {
            console.error('Error fetching portfolio data:', data.error);
            return;
        }
        
        console.log('Portfolio data received:', data);
        
        // Update last updated timestamp
        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
            const now = new Date();
            lastUpdatedElement.textContent = now.toLocaleString();
        }
        
        // Calculate monthly yield
        let totalMonthlyYield = 0;
        
        // Clear the table
        const portfolioTable = document.getElementById('portfolioTableBody');
        portfolioTable.innerHTML = '';
        
        // Sort coins by value (descending)
        const sortedCoins = Object.entries(data.data).sort((a, b) => {
            return b[1].total_value - a[1].total_value;
        });
        
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
            priceCell.textContent = `$${details.price.toFixed(2)}`;
            
            const hourlyChangeCell = document.createElement('td');
            hourlyChangeCell.textContent = details.hourly_change ? `${details.hourly_change.toFixed(2)}%` : 'N/A';
            if (details.hourly_change > 0) {
                hourlyChangeCell.className = 'text-success';
            } else if (details.hourly_change < 0) {
                hourlyChangeCell.className = 'text-danger';
            }
            
            const dailyChangeCell = document.createElement('td');
            dailyChangeCell.textContent = details.daily_change ? `${details.daily_change.toFixed(2)}%` : 'N/A';
            if (details.daily_change > 0) {
                dailyChangeCell.className = 'text-success';
            } else if (details.daily_change < 0) {
                dailyChangeCell.className = 'text-danger';
            }
            
            const weeklyChangeCell = document.createElement('td');
            weeklyChangeCell.textContent = details.seven_day_change ? `${details.seven_day_change.toFixed(2)}%` : 'N/A';
            if (details.seven_day_change > 0) {
                weeklyChangeCell.className = 'text-success';
            } else if (details.seven_day_change < 0) {
                weeklyChangeCell.className = 'text-danger';
            }
            
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
            
            // Add to monthly yield
            totalMonthlyYield += details.monthly_yield || 0;
        }
        
        console.log('Updating total value...');
        const totalValueElement = document.getElementById('totalValue');
        if (totalValueElement) {
            // Apply demo mode division if active
            let totalValue = data.total_value;
            if (isDemoMode) {
                totalValue = totalValue / 15;
            }
            totalValueElement.textContent = totalValue.toFixed(0);
            
            // Update BTC value
            const btcValueElement = document.getElementById('btcValue');
            if (btcValueElement && bitcoinPrice > 0) {
                const btcValue = totalValue / bitcoinPrice;
                btcValueElement.textContent = btcValue.toFixed(8);
            } else if (btcValueElement) {
                btcValueElement.textContent = "N/A";
            }
        } else {
            console.error('Could not find totalValue element');
        }
        
        console.log('Updating monthly yield...');
        const monthlyYieldElement = document.getElementById('monthlyYield');
        if (monthlyYieldElement) {
            // Apply demo mode division if active
            if (isDemoMode) {
                totalMonthlyYield = totalMonthlyYield / 15;
            }
            monthlyYieldElement.textContent = totalMonthlyYield.toFixed(2);
        } else {
            console.error('Could not find monthlyYield element');
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
