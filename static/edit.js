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

async function removeSource(coinId, source, element) {
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
        if (data.success) {
            updatePortfolio();
        } else {
            alert('Error removing source.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error removing source');
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
        removeSource(coinId, sourceName, removeBtn);
    };
    
    rightDiv.appendChild(amountSpan);
    rightDiv.appendChild(removeBtn);
    
    sourceRow.appendChild(nameSpan);
    sourceRow.appendChild(rightDiv);
    
    return sourceRow;
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
                
                // Source column
                const sourceCell = document.createElement('td');
                sourceCell.textContent = source;
                
                // Amount column
                const amountCell = document.createElement('td');
                amountCell.textContent = amount.toFixed(8);
                
                // Value column
                const valueCell = document.createElement('td');
                const value = amount * details.price;
                valueCell.textContent = `$${value.toFixed(2)}`;
                
                // Actions column
                const actionsCell = document.createElement('td');
                actionsCell.innerHTML = `
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-sm btn-outline-primary edit-btn">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-danger delete-btn">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `;
                
                // Add event listeners for edit and delete buttons
                const editBtn = actionsCell.querySelector('.edit-btn');
                const deleteBtn = actionsCell.querySelector('.delete-btn');
                
                editBtn.addEventListener('click', () => {
                    // Pre-fill the form with current values
                    document.getElementById('coinId').value = coinId;
                    document.getElementById('source').value = source;
                    document.getElementById('amount').value = amount;
                });
                
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
