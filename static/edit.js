document.getElementById('addCoinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coinId = document.getElementById('coinId').value.toLowerCase().trim();
    const amount = parseFloat(document.getElementById('amount').value);
    const source = document.getElementById('source').value.trim();
    const apy = parseFloat(document.getElementById('apy')?.value || 0);
    
    if (!coinId || !source || isNaN(amount) || amount <= 0) {
        alert('Please fill all fields correctly');
        return;
    }
    
    try {
        const response = await fetch('/api/add_coin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                coin_id: coinId,
                source: source,
                amount: amount,
                apy: apy
            })
        });
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to add coin');
        }
        
        // Reset form
        document.getElementById('coinId').value = '';
        document.getElementById('source').value = '';
        document.getElementById('amount').value = '';
        if (document.getElementById('apy')) {
            document.getElementById('apy').value = '';
        }
        
        // Update portfolio
        updatePortfolio();
        
    } catch (error) {
        console.error('Error adding coin:', error);
        alert(error.message || 'Error adding coin');
    }
});

async function removeSource(coinId, source) {
    try {
        const response = await fetch('/api/remove_source', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                coin_id: coinId,
                source: source
            })
        });
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to remove source');
        }
        
        updatePortfolio();
    } catch (error) {
        console.error('Error removing source:', error);
        alert(error.message || 'Error removing source');
    }
}

async function updateCoinEntry(coinId, oldSource, newSource, newAmount, newApy, newZerionId) {
    try {
        console.log('Updating coin entry:', { coinId, oldSource, newSource, newAmount, newApy, newZerionId });
        const response = await fetch('/api/update_coin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                coin_id: coinId,
                old_source: oldSource,
                new_source: newSource,
                new_amount: newAmount,
                new_apy: newApy,
                new_zerion_id: newZerionId
            })
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to update entry');
        }

        updatePortfolio();
    } catch (error) {
        console.error('Error updating entry:', error);
        alert(error.message || 'Error updating entry');
    }
}

function makeEditable(element, currentValue, onSave) {
    // Create input field
    const input = document.createElement('input');
    input.type = typeof currentValue === 'number' ? 'number' : 'text';
    input.value = currentValue;
    input.className = 'form-control form-control-sm';
    if (input.type === 'number') {
        input.step = 'any';
        input.min = '0';
    }
    
    // Create save button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-sm btn-success';
    saveBtn.innerHTML = '&#10003;';
    
    // Create container
    const container = document.createElement('div');
    container.className = 'd-flex align-items-center gap-2';
    container.appendChild(input);
    container.appendChild(saveBtn);
    
    // Store original content and replace with input
    const originalContent = element.innerHTML;
    element.innerHTML = '';
    element.appendChild(container);
    
    // Focus input
    input.focus();
    
    // Function to save changes
    function save() {
        const newValue = input.type === 'number' ? parseFloat(input.value) : input.value.trim();
        // Special handling for Zerion ID - allow empty strings
        const isZerionIdField = element.parentElement && element.parentElement.classList.contains('zerion-id-cell');
        
        if ((input.type === 'number' && !isNaN(newValue) && newValue >= 0) || 
            (input.type !== 'number' && (isZerionIdField || newValue !== '')) && 
            newValue !== currentValue) {
            onSave(newValue);
        } else {
            // Restore original content if no changes or invalid input
            element.innerHTML = originalContent;
        }
    }
    
    // Function to cancel editing
    function cancel() {
        element.innerHTML = originalContent;
    }
    
    // Save button click
    saveBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        save();
    });
    
    // Enter key to save, Escape to cancel
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            save();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancel();
        }
    });
    
    // Click outside to cancel
    setTimeout(function() {
        document.addEventListener('click', function handleClickOutside(e) {
            if (!element.contains(e.target)) {
                cancel();
                document.removeEventListener('click', handleClickOutside);
            }
        });
    }, 10);
}

async function updatePortfolio() {
    try {
        const response = await fetch('/portfolio');
        const data = await response.json();
        
        console.log('Portfolio data:', data);
        
        if (!data.success) {
            console.error('Failed to fetch portfolio:', data.error);
            return;
        }
        
        const portfolioDetails = document.getElementById('portfolioDetails');
        
        if (!data.data || Object.keys(data.data).length === 0) {
            portfolioDetails.innerHTML = `
                <div class="alert alert-info">
                    No portfolio data found. Add some coins using the form above.
                </div>
            `;
            // Update the total value to 0 if no portfolio data
            const totalValueElement = document.getElementById('totalValue');
            if (totalValueElement) {
                totalValueElement.textContent = '0.00';
            }
            return;
        }
        
        let totalPortfolioValue = 0;
        let totalYield = 0;
        let totalDailyYield = 0;
        console.log('Starting total value calculation');
        
        let tableHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Location</th>
                        <th>Amount</th>
                        <th>APY Yield (%)</th>
                        <th>Zerion Id</th>
                        <th>Value (USD)</th>
                        <th>Daily Yield</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="portfolioTableBody"></tbody>
                <tfoot>
                    <tr>
                        <td colspan="4" style="background-color:#121726" class="text-end fw-bold">Total Value:</td>
                        <td id="totalValueCell" style="background-color:#121726"class="fw-bold"></td>
                        <td style="background-color:#121726"></td>
                        <td style="background-color:#121726"></td>
                    </tr>
                    <tr>
                        <td colspan="4" style="background-color:#121726" class="text-end fw-bold">Total Yield:</td>
                        <td id="totalYieldCell" style="background-color:#121726"class="fw-bold"></td>
                        <td style="background-color:#121726"></td>
                        <td style="background-color:#121726"></td>
                    </tr>
                    <tr>
                        <td colspan="4" style="background-color:#121726" class="text-end fw-bold">Monthly Yield:</td>
                        <td id="monthlyYieldCell" style="background-color:#121726"class="fw-bold"></td>
                        <td style="background-color:#121726"></td>
                        <td style="background-color:#121726"></td>
                    </tr>
                    <tr>
                        <td colspan="4" style="background-color:#121726" class="text-end fw-bold">Daily Yield:</td>
                        <td id="dailyYieldCell" style="background-color:#121726" class="fw-bold"></td>
                        <td style="background-color:#121726"></td>
                        <td style="background-color:#121726"></td>
                    </tr>
                </tfoot>
            </table>
        `;
        
        portfolioDetails.innerHTML = tableHTML;
        const tableBody = document.getElementById('portfolioTableBody');
        
        for (const [coinId, details] of Object.entries(data.data)) {
            console.log(`Processing coin: ${coinId}, price: ${details.price}`);
            for (const [source, sourceData] of Object.entries(details.sources)) {
                // Handle both old format (just amount) and new format (object with amount and apy)
                let amount, apy = 0;
                if (typeof sourceData === 'object' && sourceData !== null) {
                    amount = sourceData.amount;
                    apy = sourceData.apy || 0;
                } else {
                    amount = sourceData;
                }
                
                console.log(`  Source: ${source}, amount: ${amount}, apy: ${apy}`);
                const row = document.createElement('tr');
                
                // Asset column with icon
                const assetCell = document.createElement('td');
                assetCell.innerHTML = `
                    <div class="d-flex align-items-center">
                        <img src="${details.image || ''}" alt="${coinId}" class="coin-logo me-2" style="width: 24px; height: 24px;">
                        <span class="text-capitalize">${coinId.replace('-', ' ')}</span>
                    </div>
                `;
                
                // Source column (editable)
                const sourceCell = document.createElement('td');
                sourceCell.className = 'source-cell';
                sourceCell.innerHTML = `<span class="editable">${source}</span>`;
                const sourceSpan = sourceCell.querySelector('.editable');
                
                sourceSpan.addEventListener('click', function(e) {
                    e.stopPropagation();
                    makeEditable(this, source, function(newSource) {
                        updateCoinEntry(coinId, source, newSource, amount, apy);
                    });
                });
                
                // Amount column (editable)
                const amountCell = document.createElement('td');
                amountCell.className = 'amount-cell';
                amountCell.innerHTML = `<span class="editable">${amount.toFixed(8)}</span>`;
                const amountSpan = amountCell.querySelector('.editable');
                
                amountSpan.addEventListener('click', function(e) {
                    e.stopPropagation();
                    makeEditable(this, amount, function(newAmount) {
                        updateCoinEntry(coinId, source, source, newAmount, apy);
                    });
                });
                
                // APY column (editable)
                const apyCell = document.createElement('td');
                apyCell.className = 'apy-cell';
                apyCell.innerHTML = `<span class="editable">${apy.toFixed(2)}</span>`;
                const apySpan = apyCell.querySelector('.editable');
                
                apySpan.addEventListener('click', function(e) {
                    e.stopPropagation();
                    makeEditable(this, apy, function(newApy) {
                        updateCoinEntry(coinId, source, source, amount, newApy);
                    });
                });
                
                // Zerion Id column (editable)
                const zerionIdCell = document.createElement('td');
                zerionIdCell.className = 'zerion-id-cell';
                const zerionId = sourceData.zerion_id || '';
                zerionIdCell.innerHTML = `<span class="editable" style="font-size: 0.8rem;">${zerionId || '<i class="text-muted">Click to add</i>'}</span>`;
                const zerionIdSpan = zerionIdCell.querySelector('.editable');
                
                zerionIdSpan.addEventListener('click', function(e) {
                    e.stopPropagation();
                    makeEditable(this, zerionId, function(newZerionId) {
                        // Update the coin entry with the new Zerion Id
                        updateCoinEntry(coinId, source, source, amount, apy, newZerionId);
                    });
                });
                
                // Value column
                const valueCell = document.createElement('td');
                const value = amount * details.price;
                console.log(`  Calculated value: ${value} (${amount} * ${details.price})`);
                valueCell.textContent = `$${value.toFixed(2)}`;
                
                // Calculate yield for this row
                const rowYield = value * (apy / 100);
                totalYield += rowYield;
                console.log(`  Row yield: $${rowYield.toFixed(2)} (${value} * ${apy / 100})`);
                
                // Daily Yield column
                const dailyYieldCell = document.createElement('td');
                const dailyYield = rowYield / 365;
                totalDailyYield += dailyYield;
                dailyYieldCell.textContent = `$${dailyYield.toFixed(2)}`;
                console.log(`  Daily yield: $${dailyYield.toFixed(2)} (${rowYield} / 365)`);
                
                // Add to total value
                totalPortfolioValue += value;
                console.log(`  Running total: ${totalPortfolioValue}`);
                
                // Actions column
                const actionsCell = document.createElement('td');
                actionsCell.innerHTML = `
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-sm btn-outline-danger delete-btn">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `;
                
                // Add delete button event listener
                const deleteBtn = actionsCell.querySelector('.delete-btn');
                deleteBtn.addEventListener('click', () => {
                    if (confirm(`Are you sure you want to remove ${amount} ${coinId} from ${source}?`)) {
                        removeSource(coinId, source);
                    }
                });
                
                // Add all cells to the row
                row.appendChild(assetCell);
                row.appendChild(sourceCell);
                row.appendChild(amountCell);
                row.appendChild(apyCell);
                row.appendChild(zerionIdCell);
                row.appendChild(valueCell);
                row.appendChild(dailyYieldCell);
                row.appendChild(actionsCell);
                
                tableBody.appendChild(row);
            }
        }
        
        // Update total value cell in table footer
        console.log(`Final total portfolio value: ${totalPortfolioValue}`);
        const totalValueCell = document.getElementById('totalValueCell');
        if (totalValueCell) {
            totalValueCell.textContent = `$${totalPortfolioValue.toFixed(2)}`;
            console.log(`Set total value cell to: $${totalPortfolioValue.toFixed(2)}`);
        } else {
            console.error('Total value cell not found!');
        }
        
        // Update total yield cell in table footer
        console.log(`Final total yield: ${totalYield}`);
        const totalYieldCell = document.getElementById('totalYieldCell');
        if (totalYieldCell) {
            totalYieldCell.textContent = `$${totalYield.toFixed(2)}`;
            console.log(`Set total yield cell to: $${totalYield.toFixed(2)}`);
        } else {
            console.error('Total yield cell not found!');
        }
        
        // Calculate and update monthly yield
        const monthlyYield = totalYield / 12;
        console.log(`Monthly yield: ${monthlyYield}`);
        const monthlyYieldCell = document.getElementById('monthlyYieldCell');
        if (monthlyYieldCell) {
            monthlyYieldCell.textContent = `$${monthlyYield.toFixed(2)}`;
            console.log(`Set monthly yield cell to: $${monthlyYield.toFixed(2)}`);
        } else {
            console.error('Monthly yield cell not found!');
        }
        
        // Update daily yield cell in table footer
        console.log(`Final total daily yield: ${totalDailyYield}`);
        const dailyYieldCell = document.getElementById('dailyYieldCell');
        if (dailyYieldCell) {
            dailyYieldCell.textContent = `$${totalDailyYield.toFixed(2)}`;
            console.log(`Set daily yield cell to: $${totalDailyYield.toFixed(2)}`);
        } else {
            console.error('Daily yield cell not found!');
        }
        
        // Update the total value in the header section
        const totalValueElement = document.getElementById('totalValue');
        if (totalValueElement) {
            totalValueElement.textContent = totalPortfolioValue.toFixed(2);
            console.log(`Set header total value to: ${totalPortfolioValue.toFixed(2)}`);
        } else {
            console.log('Header total value element not found - this is normal for edit_portfolio.html');
        }
        
    } catch (error) {
        console.error('Error updating portfolio:', error);
        const portfolioDetails = document.getElementById('portfolioDetails');
        portfolioDetails.innerHTML = `
            <div class="alert alert-danger">
                Error loading portfolio data: ${error.message}
            </div>
        `;
        
        // Reset total value on error
        const totalValueElement = document.getElementById('totalValue');
        if (totalValueElement) {
            totalValueElement.textContent = '0.00';
        }
    }
}

// Add coin search functionality
let coinsList = [];

async function loadCoinsList() {
    try {
        const response = await fetch('/api/coins');
        const data = await response.json();
        if (data.success) {
            coinsList = data.data;
        }
    } catch (error) {
        console.error('Error loading coins list:', error);
    }
}

// Load coins list when page loads
loadCoinsList();

// Add event listener for Update Zerion Data button
document.getElementById('updateZerionDataBtn').addEventListener('click', async () => {
    try {
        // Show loading state
        const button = document.getElementById('updateZerionDataBtn');
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = 'Updating...';
        
        // Make API request to fetch Zerion data
        const response = await fetch('/api/update_zerion_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        // Create a modal to display the detailed information
        const modalId = 'zerionDebugModal';
        let modal = document.getElementById(modalId);
        
        // Remove existing modal if it exists
        if (modal) {
            document.body.removeChild(modal);
        }
        
        // Create modal HTML
        modal = document.createElement('div');
        modal.id = modalId;
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        modal.style.zIndex = '1000';
        modal.style.display = 'flex';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';
        
        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.style.backgroundColor = '#121726';
        modalContent.style.padding = '20px';
        modalContent.style.borderRadius = '5px';
        modalContent.style.maxWidth = '90%';
        modalContent.style.maxHeight = '90%';
        modalContent.style.overflow = 'auto';
        modalContent.style.color = '#e0e0e0';
        
        // Create title
        const title = document.createElement('h3');
        title.textContent = 'Zerion Data Update Results';
        title.style.marginBottom = '15px';
        
        // Create close button
        const closeButton = document.createElement('button');
        closeButton.textContent = 'Close';
        closeButton.className = 'btn btn-secondary';
        closeButton.style.marginBottom = '15px';
        closeButton.onclick = () => {
            document.body.removeChild(modal);
        };
        
        // Create result message
        const message = document.createElement('p');
        if (data.success) {
            if (data.updated_entries && data.updated_entries.length > 0) {
                const updatedCount = data.updated_entries.length;
                message.innerHTML = `<strong>Success:</strong> Updated ${updatedCount} portfolio entries with Zerion data.`;
                
                // Add Bitcoin difference information if available
                if (data.bitcoin_before !== undefined && data.bitcoin_after !== undefined && data.bitcoin_difference !== undefined) {
                    const bitcoinInfo = document.createElement('div');
                    bitcoinInfo.style.marginTop = '10px';
                    bitcoinInfo.style.marginBottom = '15px';
                    bitcoinInfo.style.padding = '10px';
                    bitcoinInfo.style.backgroundColor = '#1c243e';
                    bitcoinInfo.style.borderRadius = '5px';
                    
                    const diffColor = data.bitcoin_difference >= 0 ? '#2ecc71' : '#e74c3c';
                    const diffSign = data.bitcoin_difference >= 0 ? '+' : '';
                    
                    // Format USD value
                    let usdValueDisplay = '';
                    if (data.bitcoin_price && data.bitcoin_difference_usd !== undefined) {
                        const usdDiffFormatted = Math.abs(data.bitcoin_difference_usd).toLocaleString('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        });
                        const usdSign = data.bitcoin_difference_usd >= 0 ? '+' : '-';
                        usdValueDisplay = ` (${usdSign}${usdDiffFormatted})`;
                    }
                    
                    bitcoinInfo.innerHTML = `
                        <h4>Bitcoin Balance Change</h4>
                        <p><strong>Before update:</strong> ${data.bitcoin_before.toFixed(8)} BTC</p>
                        <p><strong>After update:</strong> ${data.bitcoin_after.toFixed(8)} BTC</p>
                        <p><strong>Difference:</strong> <span style="color: ${diffColor};">${diffSign}${data.bitcoin_difference.toFixed(8)} BTC${usdValueDisplay}</span></p>
                        ${data.bitcoin_price ? `<p><strong>Current BTC Price:</strong> $${data.bitcoin_price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>` : ''}
                    `;
                    
                    message.appendChild(bitcoinInfo);
                }
                
                // Add updated entries details
                const updatedList = document.createElement('ul');
                data.updated_entries.forEach(entry => {
                    const item = document.createElement('li');
                    item.innerHTML = `<strong>${entry.coin_id}</strong> (${entry.source}): ${entry.old_amount} → ${entry.new_amount}`;
                    updatedList.appendChild(item);
                });
                
                message.appendChild(updatedList);
            } else {
                message.innerHTML = `<strong>No Updates:</strong> ${data.message}`;
                
                // Add details about entries that weren't found
                if (data.not_found_entries && data.not_found_entries.length > 0) {
                    const notFoundTitle = document.createElement('p');
                    notFoundTitle.innerHTML = '<strong>Entries with Zerion IDs that weren\'t found:</strong>';
                    message.appendChild(notFoundTitle);
                    
                    const notFoundList = document.createElement('ul');
                    data.not_found_entries.forEach(entry => {
                        const item = document.createElement('li');
                        item.innerHTML = `<strong>${entry.coin_id}</strong> (${entry.source}): ${entry.zerion_id}`;
                        notFoundList.appendChild(item);
                    });
                    
                    message.appendChild(notFoundList);
                    
                    const helpText = document.createElement('p');
                    helpText.innerHTML = '<strong>Possible issues:</strong><br>- The Zerion ID might be incorrect<br>- The asset might not be in the wallet<br>- The asset might be in a different format in Zerion';
                    message.appendChild(helpText);
                }
            }
        } else {
            message.innerHTML = `<strong>Error:</strong> ${data.message || data.error || 'Unknown error'}`;
        }
        
        // Create JSON preview section
        const jsonSection = document.createElement('div');
        jsonSection.style.marginTop = '20px';
        
        const jsonTitle = document.createElement('h4');
        jsonTitle.textContent = 'Zerion API Response (Full JSON)';
        jsonTitle.style.marginBottom = '10px';
        
        const jsonContent = document.createElement('pre');
        jsonContent.style.backgroundColor = '#1e1e1e';
        jsonContent.style.padding = '10px';
        jsonContent.style.borderRadius = '5px';
        jsonContent.style.overflow = 'auto';
        jsonContent.style.maxHeight = '400px';
        jsonContent.style.fontSize = '12px';
        jsonContent.style.whiteSpace = 'pre-wrap';
        jsonContent.textContent = data.json_preview || 'No JSON preview available';
        
        jsonSection.appendChild(jsonTitle);
        jsonSection.appendChild(jsonContent);
        
        // Assemble modal content
        modalContent.appendChild(title);
        modalContent.appendChild(closeButton);
        modalContent.appendChild(message);
        modalContent.appendChild(jsonSection);
        modal.appendChild(modalContent);
        
        // Add modal to body
        document.body.appendChild(modal);
        
        // Refresh the portfolio display if updates were made
        if (data.success && data.updated_entries && data.updated_entries.length > 0) {
            updatePortfolio();
        }
        
        // Reset button state
        button.disabled = false;
        button.textContent = originalText;
        
    } catch (error) {
        console.error('Error updating Zerion data:', error);
        alert('Error updating Zerion data. See console for details.');
        
        // Reset button state
        const button = document.getElementById('updateZerionDataBtn');
        button.disabled = false;
        button.textContent = 'Update Zerion Data';
    }
});

// Initial load
updatePortfolio();
