let historyChart = null;
let isDemoMode = false; // Track demo mode state
let isLogScale = false; // Track logarithmic scale state
let currentDateRange = '180'; // Default to 6 months
let historyData = []; // Store the full history data

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
        
        // Store the full history data
        historyData = data.data;
        
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
        
        if (historyChart) {
            historyChart.destroy();
        }
        
        const ctx = document.getElementById('historyChart').getContext('2d');
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
                        fill: true,
                        tension: 0.4,
                        pointRadius: 1,
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
                        pointRadius: 1,
                        hidden: true // Hidden by default
                    }
                ]
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
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        type: isLogScale ? 'logarithmic' : 'linear',
                        position: 'left',
                        beginAtZero: !isLogScale, // Only begin at zero for linear scale
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
                        type: isLogScale ? 'logarithmic' : 'linear',
                        position: 'right',
                        beginAtZero: !isLogScale,
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
                btcValueElement.textContent = btcValue.toFixed(2);
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

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');
    
    // Initialize with default pair
    createTradingViewWidget('BTCUSD');
    initializePairSelection();
    
    // Initial portfolio update
    updatePortfolio();
    
    // Set up auto-refresh
    setInterval(updatePortfolio, 60000); // Refresh every minute
    
    // Add event listener for demo mode toggle
    const toggleDemoButton = document.getElementById('toggleDemoButton');
    if (toggleDemoButton) {
        toggleDemoButton.addEventListener('click', toggleDemoMode);
    }
    
    // Add event listener for add history button
    const addHistoryButton = document.getElementById('addHistoryButton');
    if (addHistoryButton) {
        addHistoryButton.addEventListener('click', async function() {
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
                    updateHistoryChart();
                } else {
                    alert('Failed to add history entry: ' + data.error);
                }
            } catch (error) {
                console.error('Error adding history:', error);
                alert('Error adding history: ' + error.message);
            }
        });
    }
    
    // Add event listener for logarithmic scale toggle
    const logScaleToggle = document.getElementById('logScaleToggle');
    if (logScaleToggle) {
        logScaleToggle.addEventListener('change', function() {
            isLogScale = this.checked;
            updateHistoryChart();
        });
    }
    
    // Add event listeners for date range buttons
    const dateRangeButtons = document.querySelectorAll('.date-range-btn');
    if (dateRangeButtons.length > 0) {
        dateRangeButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove active class from all buttons
                dateRangeButtons.forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                this.classList.add('active');
                // Update date range and refresh chart
                currentDateRange = this.dataset.range;
                updateHistoryChart();
            });
        });
    }
    
    // Set up check history status button
    const checkHistoryButton = document.getElementById('checkHistoryButton');
    if (checkHistoryButton) {
        checkHistoryButton.addEventListener('click', async function() {
            try {
                const historyStatusElement = document.getElementById('historyStatus');
                historyStatusElement.style.display = 'block';
                historyStatusElement.textContent = 'Checking history status...';
                
                // Fetch history data
                const response = await fetch('/history');
                const data = await response.json();
                
                if (!data.success) {
                    historyStatusElement.textContent = 'Failed to get history data: ' + data.error;
                    return;
                }
                
                // Get the most recent entries
                const entries = data.data;
                
                if (entries.length === 0) {
                    historyStatusElement.textContent = 'No history entries found in the database.';
                    return;
                }
                
                // Sort entries by date (newest first)
                entries.sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
                
                // Get the most recent entry
                const latestEntry = entries[0];
                const latestDate = new Date(latestEntry.datetime);
                const now = new Date();
                const hoursSinceLatest = (now - latestDate) / (1000 * 60 * 60);
                
                // Format the status message
                let statusMessage = `Latest entry: ${latestDate.toLocaleString()} (${hoursSinceLatest.toFixed(1)} hours ago)\n`;
                statusMessage += `Total entries: ${entries.length}\n`;
                
                if (hoursSinceLatest > 1.5) {
                    statusMessage += `WARNING: No recent entries in the last hour. The scheduler may not be working properly.`;
                } else {
                    statusMessage += `Status: History tracking appears to be working correctly.`;
                }
                
                historyStatusElement.innerHTML = statusMessage.replace(/\n/g, '<br>');
                
                // Update the history chart
                updateHistoryChart();
            } catch (error) {
                const historyStatusElement = document.getElementById('historyStatus');
                historyStatusElement.style.display = 'block';
                historyStatusElement.textContent = 'Error checking history status: ' + error.message;
            }
        });
    }
});
