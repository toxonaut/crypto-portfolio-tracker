document.getElementById('addCoinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coinId = document.getElementById('coinId').value.toLowerCase().trim();
    const amount = parseFloat(document.getElementById('amount').value);
    const source = document.getElementById('source').value.trim();
    
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
                amount: amount
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

async function updateCoinEntry(coinId, oldSource, newSource, newAmount) {
    try {
        console.log('Updating coin entry:', { coinId, oldSource, newSource, newAmount });
        const response = await fetch('/api/update_coin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                coin_id: coinId,
                old_source: oldSource,
                new_source: newSource,
                new_amount: newAmount
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
    saveBtn.innerHTML = '✓';
    
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
        if (newValue && newValue !== currentValue) {
            onSave(newValue);
        } else {
            // Restore original content if no changes
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
            return;
        }
        
        let tableHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Location</th>
                        <th>Amount</th>
                        <th>Value (USD)</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="portfolioTableBody"></tbody>
            </table>
        `;
        
        portfolioDetails.innerHTML = tableHTML;
        const tableBody = document.getElementById('portfolioTableBody');
        
        for (const [coinId, details] of Object.entries(data.data)) {
            for (const [source, amount] of Object.entries(details.sources)) {
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
                        updateCoinEntry(coinId, source, newSource, amount);
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
                        updateCoinEntry(coinId, source, source, newAmount);
                    });
                });
                
                // Value column
                const valueCell = document.createElement('td');
                const value = amount * details.price;
                valueCell.textContent = `$${value.toFixed(2)}`;
                
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
                row.appendChild(valueCell);
                row.appendChild(actionsCell);
                
                tableBody.appendChild(row);
            }
        }
    } catch (error) {
        console.error('Error updating portfolio:', error);
        const portfolioDetails = document.getElementById('portfolioDetails');
        portfolioDetails.innerHTML = `
            <div class="alert alert-danger">
                Error loading portfolio data: ${error.message}
            </div>
        `;
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

// Initial load
updatePortfolio();
