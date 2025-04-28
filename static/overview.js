// Global variables
let historyData = [];
let historyChart = null;
let tradingViewWidget = null;
let currentDateRange = '90'; // Default to 3 months
let isLogScale = false;
let isDemoMode = false;

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
        "width": "100%",
        "height": 500,
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
                            minRotation: 45,
                            autoSkip: false, // Prevent Chart.js from automatically skipping labels
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
        
        // Update historical changes after chart is updated
        updateHistoricalChanges();
        
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
            return;
        }
        
        console.log('Portfolio data received:', data);
        
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
            portfolioTable.appendChild(row);
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
        
        // Update history chart
        console.log('Updating history chart...');
        await updateHistoryChart();
        
        // Update historical changes
        updateHistoricalChanges();
        
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
    
    // Update the historical changes
    updateHistoricalChanges();
}

// Calculate historical changes based on history data
function calculateHistoricalChanges() {
    console.log('Calculating historical changes...');
    
    if (!historyData || historyData.length === 0) {
        console.error('No history data available for calculating changes');
        return {
            change24h: { value: 0, percent: 0, date: '' },
            change7d: { value: 0, percent: 0, date: '' },
            change30d: { value: 0, percent: 0, date: '' },
            largestPercentGain: { value: 0, percent: 0, date: '' },
            largestDollarGain: { value: 0, percent: 0, date: '' },
            largestPercentLoss: { value: 0, percent: 0, date: '' },
            largestDollarLoss: { value: 0, percent: 0, date: '' }
        };
    }
    
    console.log('History data available:', historyData.length, 'entries');
    
    // Sort history data by date (newest first)
    const sortedData = [...historyData].sort((a, b) => {
        return new Date(b.datetime) - new Date(a.datetime);
    });
    
    // Get the current value (most recent history entry)
    let currentValue = 0;
    let currentDate = null;
    
    if (sortedData.length > 0) {
        currentValue = sortedData[0].total_value;
        currentDate = new Date(sortedData[0].datetime);
        console.log('Current value from most recent history entry:', currentValue, 'from', currentDate);
    } else {
        console.error('No valid current value available');
        return {
            change24h: { value: 0, percent: 0, date: '' },
            change7d: { value: 0, percent: 0, date: '' },
            change30d: { value: 0, percent: 0, date: '' },
            largestPercentGain: { value: 0, percent: 0, date: '' },
            largestDollarGain: { value: 0, percent: 0, date: '' },
            largestPercentLoss: { value: 0, percent: 0, date: '' },
            largestDollarLoss: { value: 0, percent: 0, date: '' }
        };
    }
    
    // Apply demo mode scaling if needed
    if (isDemoMode) {
        currentValue = currentValue / 15;
    }
    
    // We need at least 2 data points to calculate changes
    if (sortedData.length < 2) {
        console.error('Not enough history data to calculate changes');
        return {
            change24h: { value: 0, percent: 0, date: '' },
            change7d: { value: 0, percent: 0, date: '' },
            change30d: { value: 0, percent: 0, date: '' },
            largestPercentGain: { value: 0, percent: 0, date: '' },
            largestDollarGain: { value: 0, percent: 0, date: '' },
            largestPercentLoss: { value: 0, percent: 0, date: '' },
            largestDollarLoss: { value: 0, percent: 0, date: '' }
        };
    }
    
    // Find values from 24h ago, 7d ago, and 30d ago
    const now = new Date();
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

    // Find the closest data points to our target times
    let value24hAgo = null;
    let value7dAgo = null;
    let value30dAgo = null;
    let date24hAgo = null;
    let date7dAgo = null;
    let date30dAgo = null;

    // Get entries from the last 48 hours to ensure we have enough data
    const twoDaysAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);

    // Log the target times for debugging
    console.log('Target times for comparison:');
    console.log('24h ago:', oneDayAgo);
    console.log('7d ago:', sevenDaysAgo);
    console.log('30d ago:', thirtyDaysAgo);

    // First, check if we have any entries from the past 48 hours
    let hasRecentEntries = false;
    for (let i = 0; i < sortedData.length; i++) {
        const entry = sortedData[i];
        const entryDate = new Date(entry.datetime);
        
        // Skip the current value (most recent entry) for historical comparisons
        if (i === 0) continue;
        
        // Check if this entry is from the past 48 hours
        if (entryDate >= twoDaysAgo) {
            hasRecentEntries = true;
            break;
        }
    }

    // If we don't have any recent entries, log a warning
    if (!hasRecentEntries) {
        console.warn('No entries found from the past 48 hours! The worker process might not be running correctly.');
        console.warn('Please check the worker process and make sure it\'s adding history entries hourly.');
    }

    let closestTimeDiff24h = Infinity;
    let closestTimeDiff7d = Infinity;
    let closestTimeDiff30d = Infinity;

    for (let i = 0; i < sortedData.length; i++) {
        const entry = sortedData[i];
        const entryDate = new Date(entry.datetime);
        
        // Skip the current value (most recent entry) for historical comparisons
        if (i === 0) continue;
        
        // For 24h comparison, only consider entries from the past 48 hours
        // This prevents using very old entries for the 24h comparison
        if (entryDate >= twoDaysAgo) {
            const timeDiff24h = Math.abs(entryDate.getTime() - oneDayAgo.getTime());
            if (timeDiff24h < closestTimeDiff24h) {
                closestTimeDiff24h = timeDiff24h;
                value24hAgo = entry.total_value;
                date24hAgo = entryDate;
            }
        }
        
        // For 7d comparison
        const timeDiff7d = Math.abs(entryDate.getTime() - sevenDaysAgo.getTime());
        if (timeDiff7d < closestTimeDiff7d) {
            closestTimeDiff7d = timeDiff7d;
            value7dAgo = entry.total_value;
            date7dAgo = entryDate;
        }
        
        // For 30d comparison
        const timeDiff30d = Math.abs(entryDate.getTime() - thirtyDaysAgo.getTime());
        if (timeDiff30d < closestTimeDiff30d) {
            closestTimeDiff30d = timeDiff30d;
            value30dAgo = entry.total_value;
            date30dAgo = entryDate;
        }
    }

    // If we couldn't find a 24h entry from the past 48 hours, use the most recent entry after the current one
    if (value24hAgo === null && sortedData.length > 1) {
        console.warn('No suitable entry found for 24h comparison within the past 48 hours. Using the second most recent entry.');
        value24hAgo = sortedData[1].total_value;
        date24hAgo = new Date(sortedData[1].datetime);
    }

    if (date24hAgo) {
        const hoursSince = (now.getTime() - date24hAgo.getTime()) / (60 * 60 * 1000);
        console.log('Using entry from', date24hAgo, 'with value', value24hAgo, 'for 24h comparison');
        console.log('This entry is', (closestTimeDiff24h / (60 * 60 * 1000)).toFixed(2), 'hours away from exactly 24h ago');
        console.log('This entry is', hoursSince.toFixed(2), 'hours old');
        
        // Add a warning if the entry is too old
        if (hoursSince > 48) {
            console.warn(`WARNING: The entry used for 24h comparison is ${hoursSince.toFixed(2)} hours old, which is more than 48 hours!`);
            console.warn('This suggests the worker process might not be adding history entries regularly.');
        }
    }
    
    // Apply demo mode scaling to historical values if needed
    if (isDemoMode) {
        if (value24hAgo !== null) value24hAgo = value24hAgo / 15;
        if (value7dAgo !== null) value7dAgo = value7dAgo / 15;
        if (value30dAgo !== null) value30dAgo = value30dAgo / 15;
    }
    
    // Calculate dollar and percentage changes
    let dollarChange24h = 0;
    let percentChange24h = 0;
    let formattedDate24h = '';
    
    if (value24hAgo !== null && value24hAgo !== 0) {
        dollarChange24h = currentValue - value24hAgo;
        percentChange24h = ((currentValue - value24hAgo) / value24hAgo) * 100;
        
        // Format the date for display
        if (date24hAgo) {
            const month = date24hAgo.toLocaleString('en-US', { month: 'short' });
            const day = date24hAgo.getDate();
            const hours = date24hAgo.getHours().toString().padStart(2, '0');
            const minutes = date24hAgo.getMinutes().toString().padStart(2, '0');
            formattedDate24h = `${month}-${day}, ${hours}:${minutes}`;
        }
        
        console.log('24h change calculation:');
        console.log('Current value:', currentValue);
        console.log('24h ago value:', value24hAgo, 'from', date24hAgo);
        console.log('Dollar change:', dollarChange24h);
        console.log('Percent change:', percentChange24h);
        
        // Check for unreasonable changes (both positive and negative)
        if (Math.abs(percentChange24h) > 100) {
            console.log(`Detected extreme percentage change for 24h (${percentChange24h.toFixed(2)}%), capping at ±100%`);
            if (percentChange24h > 0) {
                percentChange24h = 100;
                dollarChange24h = value24hAgo; // 100% increase
            } else {
                percentChange24h = -100;
                dollarChange24h = -value24hAgo; // 100% decrease
            }
        }
    }
    
    let dollarChange7d = 0;
    let percentChange7d = 0;
    let formattedDate7d = '';
    
    if (value7dAgo !== null && value7dAgo !== 0) {
        dollarChange7d = currentValue - value7dAgo;
        percentChange7d = ((currentValue - value7dAgo) / value7dAgo) * 100;
        
        // Format the date for 7d display
        if (date7dAgo) {
            const month = date7dAgo.toLocaleString('en-US', { month: 'short' });
            const day = date7dAgo.getDate();
            const hours = date7dAgo.getHours().toString().padStart(2, '0');
            const minutes = date7dAgo.getMinutes().toString().padStart(2, '0');
            formattedDate7d = `${month}-${day}, ${hours}:${minutes}`;
        }
        
        console.log('7d change calculation:');
        console.log('Current value:', currentValue);
        console.log('7d ago value:', value7dAgo, 'from', date7dAgo);
        console.log('Dollar change:', dollarChange7d);
        console.log('Percent change:', percentChange7d);
        
        // Check for unreasonable changes
        if (Math.abs(percentChange7d) > 200) {
            console.log(`Detected extreme percentage change for 7d (${percentChange7d.toFixed(2)}%), capping at ±200%`);
            if (percentChange7d > 0) {
                percentChange7d = 200;
                dollarChange7d = value7dAgo * 2; // 200% increase
            } else {
                percentChange7d = -200;
                dollarChange7d = -value7dAgo * 2; // 200% decrease
            }
        }
    }
    
    let dollarChange30d = 0;
    let percentChange30d = 0;
    let formattedDate30d = '';
    
    if (value30dAgo !== null && value30dAgo !== 0) {
        dollarChange30d = currentValue - value30dAgo;
        percentChange30d = ((currentValue - value30dAgo) / value30dAgo) * 100;
        
        // Format the date for 30d display
        if (date30dAgo) {
            const month = date30dAgo.toLocaleString('en-US', { month: 'short' });
            const day = date30dAgo.getDate();
            const hours = date30dAgo.getHours().toString().padStart(2, '0');
            const minutes = date30dAgo.getMinutes().toString().padStart(2, '0');
            formattedDate30d = `${month}-${day}, ${hours}:${minutes}`;
        }
        
        console.log('30d change calculation:');
        console.log('Current value:', currentValue);
        console.log('30d ago value:', value30dAgo, 'from', date30dAgo);
        console.log('Dollar change:', dollarChange30d);
        console.log('Percent change:', percentChange30d);
        
        // Check for unreasonable changes
        if (Math.abs(percentChange30d) > 500) {
            console.log(`Detected extreme percentage change for 30d (${percentChange30d.toFixed(2)}%), capping at ±500%`);
            if (percentChange30d > 0) {
                percentChange30d = 500;
                dollarChange30d = value30dAgo * 5; // 500% increase
            } else {
                percentChange30d = -500;
                dollarChange30d = -value30dAgo * 5; // 500% decrease
            }
        }
    }
    
    // Initialize largest changes
    let largestPercentGain = { value: 0, percent: 0, date: '' };
    let largestDollarGain = { value: 0, percent: 0, date: '' };
    let largestPercentLoss = { value: 0, percent: 0, date: '' };
    let largestDollarLoss = { value: 0, percent: 0, date: '' };
    
    // We need at least 2 data points to calculate changes
    if (sortedData.length >= 2) {
        // Calculate all 24h changes between consecutive data points
        for (let i = 0; i < sortedData.length - 1; i++) {
            const laterDate = new Date(sortedData[i].datetime);
            const earlierDate = new Date(sortedData[i + 1].datetime);
            
            // Check if these entries are roughly 24h apart (between 20-28 hours to account for some variance)
            const hoursDiff = (laterDate - earlierDate) / (1000 * 60 * 60);
            if (hoursDiff >= 20 && hoursDiff <= 28) {
                let laterValue = sortedData[i].total_value;
                let earlierValue = sortedData[i + 1].total_value;
                
                // Apply demo mode scaling if needed
                if (isDemoMode) {
                    laterValue = laterValue / 15;
                    earlierValue = earlierValue / 15;
                }
                
                const dollarChange = laterValue - earlierValue;
                const percentChange = earlierValue !== 0 ? ((laterValue - earlierValue) / earlierValue) * 100 : 0;
                const dateStr = laterDate.toISOString().split('T')[0]; // Just the date part
                
                // Update largest percentage gain
                if (percentChange > 0 && percentChange > largestPercentGain.percent) {
                    largestPercentGain = {
                        value: dollarChange,
                        percent: percentChange,
                        date: dateStr
                    };
                }
                
                // Update largest dollar gain
                if (dollarChange > 0 && dollarChange > largestDollarGain.value) {
                    largestDollarGain = {
                        value: dollarChange,
                        percent: percentChange,
                        date: dateStr
                    };
                }
                
                // Update largest percentage loss (note: percentChange will be negative)
                if (percentChange < 0 && percentChange < largestPercentLoss.percent) {
                    largestPercentLoss = {
                        value: dollarChange,
                        percent: percentChange,
                        date: dateStr
                    };
                }
                
                // Update largest dollar loss (note: dollarChange will be negative)
                if (dollarChange < 0 && dollarChange < largestDollarLoss.value) {
                    largestDollarLoss = {
                        value: dollarChange,
                        percent: percentChange,
                        date: dateStr
                    };
                }
            }
        }
    }
    
    console.log('Historical changes calculation:');
    console.log('Current value:', currentValue);
    console.log('24h ago:', value24hAgo, 'Change:', dollarChange24h, 'Percent:', percentChange24h);
    console.log('7d ago:', value7dAgo, 'Change:', dollarChange7d, 'Percent:', percentChange7d);
    console.log('30d ago:', value30dAgo, 'Change:', dollarChange30d, 'Percent:', percentChange30d);
    console.log('Largest percent gain:', largestPercentGain);
    console.log('Largest dollar gain:', largestDollarGain);
    console.log('Largest percent loss:', largestPercentLoss);
    console.log('Largest dollar loss:', largestDollarLoss);
    
    return {
        change24h: { value: dollarChange24h, percent: percentChange24h, date: formattedDate24h },
        change7d: { value: dollarChange7d, percent: percentChange7d, date: formattedDate7d },
        change30d: { value: dollarChange30d, percent: percentChange30d, date: formattedDate30d },
        largestPercentGain: largestPercentGain,
        largestDollarGain: largestDollarGain,
        largestPercentLoss: largestPercentLoss,
        largestDollarLoss: largestDollarLoss
    };
}

// Format just a percentage value with sign and color
function formatPercentOnly(percent) {
    const formattedPercent = Math.abs(percent).toFixed(2);
    const sign = percent >= 0 ? '+' : '-';
    const className = percent >= 0 ? 'price-change-positive' : 'price-change-negative';
    
    return `<span class="${className}">${sign}${formattedPercent}%</span>`;
}

// Format just a dollar value with sign and color
function formatDollarOnly(value) {
    const formattedValue = Math.abs(value) < 1 ? Math.abs(value).toFixed(2) : Math.round(Math.abs(value));
    const sign = value >= 0 ? '+' : '-';
    const className = value >= 0 ? 'price-change-positive' : 'price-change-negative';
    
    return `<span class="${className}">${sign}$${formattedValue}</span>`;
}

// Update the historical changes display
function updateHistoricalChanges() {
    const changes = calculateHistoricalChanges();
    
    // Find all elements that need to be updated
    const change24hElements = document.querySelectorAll('#change24h');
    const change7dElements = document.querySelectorAll('#change7d');
    const change30dElements = document.querySelectorAll('#change30d');
    
    // Find the extreme change elements
    const largestPercentGainElement = document.getElementById('largestPercentGain');
    const largestDollarGainElement = document.getElementById('largestDollarGain');
    const largestPercentLossElement = document.getElementById('largestPercentLoss');
    const largestDollarLossElement = document.getElementById('largestDollarLoss');
    
    // Update all instances of each element
    change24hElements.forEach(element => {
        let formattedChange = formatValueChange(changes.change24h.value, changes.change24h.percent);
        if (changes.change24h.date) {
            // Make sure the date is clearly visible by using a different approach
            element.innerHTML = `${formattedChange} <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.change24h.date})</span>`;
        } else {
            element.innerHTML = formattedChange;
        }
    });
    
    change7dElements.forEach(element => {
        let formattedChange = formatValueChange(changes.change7d.value, changes.change7d.percent);
        if (changes.change7d.date) {
            // Make sure the date is clearly visible by using a different approach
            element.innerHTML = `${formattedChange} <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.change7d.date})</span>`;
        } else {
            element.innerHTML = formattedChange;
        }
    });
    
    change30dElements.forEach(element => {
        let formattedChange = formatValueChange(changes.change30d.value, changes.change30d.percent);
        if (changes.change30d.date) {
            // Make sure the date is clearly visible by using a different approach
            element.innerHTML = `${formattedChange} <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.change30d.date})</span>`;
        } else {
            element.innerHTML = formattedChange;
        }
    });
    
    // Update largest percentage gain
    if (largestPercentGainElement) {
        let formattedChange = formatPercentOnly(changes.largestPercentGain.percent);
        if (changes.largestPercentGain.date) {
            formattedChange += ` <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.largestPercentGain.date})</span>`;
        }
        largestPercentGainElement.innerHTML = formattedChange;
    }
    
    // Update largest dollar gain
    if (largestDollarGainElement) {
        let formattedChange = formatDollarOnly(changes.largestDollarGain.value);
        if (changes.largestDollarGain.date) {
            formattedChange += ` <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.largestDollarGain.date})</span>`;
        }
        largestDollarGainElement.innerHTML = formattedChange;
    }
    
    // Update largest percentage loss
    if (largestPercentLossElement) {
        let formattedChange = formatPercentOnly(changes.largestPercentLoss.percent);
        if (changes.largestPercentLoss.date) {
            formattedChange += ` <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.largestPercentLoss.date})</span>`;
        }
        largestPercentLossElement.innerHTML = formattedChange;
    }
    
    // Update largest dollar loss
    if (largestDollarLossElement) {
        let formattedChange = formatDollarOnly(changes.largestDollarLoss.value);
        if (changes.largestDollarLoss.date) {
            formattedChange += ` <span class="text-muted" style="display: inline-block; margin-left: 5px;">(${changes.largestDollarLoss.date})</span>`;
        }
        largestDollarLossElement.innerHTML = formattedChange;
    }
}

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM loaded, initializing...');
    
    // Check if we're on the statistics page
    const isStatisticsPage = window.location.pathname === '/statistics';
    console.log('Current page:', isStatisticsPage ? 'Statistics' : 'Overview');
    
    try {
        // Initialize TradingView widget only on the main page
        if (!isStatisticsPage) {
            createTradingViewWidget('BTCUSD');
            initializePairSelection();
        }
        
        // First, load the history data
        console.log('Loading history data first...');
        const historyLoaded = await updateHistoryChart();
        console.log('History data loaded:', historyLoaded);
        
        // Then, load the portfolio data
        console.log('Loading portfolio data...');
        await updatePortfolio();
        console.log('Portfolio data loaded');
        
        // Update historical changes explicitly
        console.log('Explicitly updating historical changes...');
        updateHistoricalChanges();
        
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
                    updateHistoryChart();
                });
            });
        }
        
        // Set up log scale switch
        const logScaleSwitch = document.getElementById('logScaleSwitch');
        if (logScaleSwitch) {
            logScaleSwitch.addEventListener('change', function() {
                isLogScale = this.checked;
                updateHistoryChart();
            });
        }
        
        // Add event listener for demo mode toggle
        const toggleDemoModeBtn = document.getElementById('toggleDemoButton');
        if (toggleDemoModeBtn) {
            toggleDemoModeBtn.addEventListener('click', toggleDemoMode);
        }
        
        // Add event listener for add history button
        const addHistoryBtn = document.getElementById('addHistoryBtn');
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
        
        // Add event listener for check history button
        const checkHistoryBtn = document.getElementById('checkHistoryBtn');
        if (checkHistoryBtn) {
            checkHistoryBtn.addEventListener('click', async function() {
                try {
                    // Fetch history data
                    const response = await fetch('/history');
                    const data = await response.json();
                    
                    if (!data.success) {
                        alert('Failed to get history data: ' + data.error);
                        return;
                    }
                    
                    // Get the most recent entries
                    const entries = data.data;
                    
                    if (entries.length === 0) {
                        alert('No history entries found in the database.');
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
                    
                    alert(statusMessage);
                    
                    // Update the history chart
                    updateHistoryChart();
                } catch (error) {
                    console.error('Error checking history status:', error);
                    alert('Error checking history status: ' + error.message);
                }
            });
        }
        
        // Set up auto-refresh
        setInterval(updatePortfolio, 60000); // Refresh every minute
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});
