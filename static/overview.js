let historyChart = null;

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
        "theme": "light",
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
        
        const values = data.data.map(item => item.total_value);
        
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
            
            // Total Balance column
            const totalBalanceCell = document.createElement('td');
            totalBalanceCell.textContent = details.total_amount.toFixed(8);
            
            // Price column
            const priceCell = document.createElement('td');
            priceCell.textContent = `$${details.price.toFixed(2)}`;
            
            // Price change columns
            const hourlyChangeCell = document.createElement('td');
            hourlyChangeCell.innerHTML = details.hourly_change ? formatPriceChange(details.hourly_change) : '-';
            
            const dailyChangeCell = document.createElement('td');
            dailyChangeCell.innerHTML = details.daily_change ? formatPriceChange(details.daily_change) : '-';
            
            const weeklyChangeCell = document.createElement('td');
            weeklyChangeCell.innerHTML = details.seven_day_change ? formatPriceChange(details.seven_day_change) : '-';
            
            // Value column
            const valueCell = document.createElement('td');
            valueCell.textContent = `$${details.total_value.toFixed(2)}`;
            
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
            totalValueElement.textContent = data.total_value.toFixed(2);
        } else {
            console.error('Could not find totalValue element');
        }
        
        // Update monthly yield
        console.log('Updating monthly yield...');
        const monthlyYieldElement = document.getElementById('monthlyYield');
        if (monthlyYieldElement) {
            monthlyYieldElement.textContent = data.total_monthly_yield.toFixed(2);
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

// Initialize TradingView chart with default pair (BTC/USD) and start updates
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing...');
    createTradingViewWidget('BTCUSD');
    initializePairSelection();
    updatePortfolio();
    
    // Refresh portfolio data every 60 seconds
    setInterval(updatePortfolio, 60000);
});
