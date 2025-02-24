document.getElementById('addCoinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coinId = document.getElementById('coinId').value.toLowerCase().trim();
    const amount = parseFloat(document.getElementById('amount').value);
    const source = document.getElementById('source').value.trim();

    if (!coinId || !source || isNaN(amount)) {
        alert('Please fill in all fields correctly');
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
                amount: amount,
                source: source
            })
        });

        const data = await response.json();
        if (data.success) {
            document.getElementById('coinId').value = '';
            document.getElementById('amount').value = '';
            document.getElementById('source').value = '';
            updatePortfolio();
        } else {
            alert(data.error || 'Error adding coin. Please check the coin ID.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error adding coin to portfolio. Please check the browser console for details.');
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
            throw new Error(data.error || 'Failed to remove entry');
        }

        updatePortfolio();
    } catch (error) {
        console.error('Error removing entry:', error);
        alert(error.message || 'Error removing entry');
    }
}

function createSourceElement(coinId, sourceName, amount) {
    const sourceRow = document.createElement('div');
    sourceRow.className = 'source-row d-flex justify-content-between align-items-center mb-2';
    
    const nameSpan = document.createElement('span');
    nameSpan.className = 'source-name';
    nameSpan.textContent = sourceName;
    
    const rightDiv = document.createElement('div');
    rightDiv.className = 'd-flex align-items-center';
    
    const amountSpan = document.createElement('span');
    amountSpan.className = 'source-amount me-3';
    amountSpan.textContent = amount.toFixed(8);
    
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-sm btn-danger remove-source-btn';
    removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
    removeBtn.onclick = (e) => {
        e.preventDefault();
        removeSource(coinId, sourceName);
    };
    
    rightDiv.appendChild(amountSpan);
    rightDiv.appendChild(removeBtn);
    
    sourceRow.appendChild(nameSpan);
    sourceRow.appendChild(rightDiv);
    
    return sourceRow;
}

async function updateCoinEntry(coinId, oldSource, newSource, newAmount) {
    try {
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
    // Create edit container
    const editContainer = document.createElement('div');
    editContainer.className = 'd-flex gap-2';
    
    // Create input
    const input = document.createElement('input');
    input.type = element.classList.contains('amount-cell') ? 'number' : 'text';
    input.value = currentValue;
    input.className = 'form-control form-control-sm';
    if (input.type === 'number') {
        input.step = 'any';
        input.min = '0';
    }
    
    // Create save button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-sm btn-success';
    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
    
    // Create cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-sm btn-outline-secondary';
    cancelBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
    
    // Add elements to container
    editContainer.appendChild(input);
    editContainer.appendChild(saveBtn);
    editContainer.appendChild(cancelBtn);
    
    const originalContent = element.innerHTML;
    element.innerHTML = '';
    element.appendChild(editContainer);
    input.focus();
    
    function handleSave() {
        const newValue = input.value.trim();
        if (newValue !== '' && newValue !== String(currentValue)) {
            onSave(newValue);
        } else {
            handleCancel();
        }
    }
    
    function handleCancel() {
        element.innerHTML = originalContent;
        element.classList.remove('editing');
    }
    
    saveBtn.addEventListener('click', handleSave);
    cancelBtn.addEventListener('click', handleCancel);
    
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSave();
        } else if (e.key === 'Escape') {
            handleCancel();
        }
    });
}

async function updatePortfolio() {
    try {
        const response = await fetch('/portfolio');
        const data = await response.json();
        
        if (!data.success) {
            console.error('Failed to fetch portfolio:', data.error);
            return;
        }
        
        const portfolioDetails = document.getElementById('portfolioDetails');
        portfolioDetails.innerHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Source</th>
                        <th>Amount</th>
                        <th>Value (USD)</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="portfolioTableBody"></tbody>
            </table>
        `;
        
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
                const sourceSpan = document.createElement('span');
                sourceSpan.className = 'editable';
                sourceSpan.textContent = source;
                sourceCell.appendChild(sourceSpan);
                sourceCell.addEventListener('click', () => {
                    if (!sourceSpan.classList.contains('editing')) {
                        sourceSpan.classList.add('editing');
                        makeEditable(sourceSpan, source, (newSource) => {
                            updateCoinEntry(coinId, source, newSource, amount);
                        });
                    }
                });
                
                // Amount column (editable)
                const amountCell = document.createElement('td');
                amountCell.className = 'amount-cell';
                const amountSpan = document.createElement('span');
                amountSpan.className = 'editable';
                amountSpan.textContent = amount.toFixed(8);
                amountCell.appendChild(amountSpan);
                amountCell.addEventListener('click', () => {
                    if (!amountSpan.classList.contains('editing')) {
                        amountSpan.classList.add('editing');
                        makeEditable(amountSpan, amount, (newAmount) => {
                            updateCoinEntry(coinId, source, source, newAmount);
                        });
                    }
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
        
        document.getElementById('totalValue').textContent = data.total_value.toFixed(2);
    } catch (error) {
        console.error('Error updating portfolio:', error);
    }
}

// Add coin search functionality
let coinsList = [];

async function loadCoinsList() {
    try {
        const response = await fetch('/api/valid_coins');
        const data = await response.json();
        if (data.success) {
            coinsList = data.coins;
            setupCoinSearch();
        }
    } catch (error) {
        console.error('Error loading coins list:', error);
    }
}

function setupCoinSearch() {
    const coinInput = document.getElementById('coinId');
    const datalist = document.createElement('datalist');
    datalist.id = 'coinsList';
    
    coinsList.forEach(coin => {
        const option = document.createElement('option');
        option.value = coin.id;
        option.label = `${coin.name} (${coin.symbol.toUpperCase()})`;
        datalist.appendChild(option);
    });
    
    document.body.appendChild(datalist);
    coinInput.setAttribute('list', 'coinsList');
    coinInput.setAttribute('placeholder', 'Start typing coin name...');
}

// Load coins list when page loads
loadCoinsList();

// Initial load
updatePortfolio();
