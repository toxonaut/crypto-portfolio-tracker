document.getElementById('addCoinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coinId = document.getElementById('coinId').value.toLowerCase();
    const amount = document.getElementById('amount').value;
    const source = document.getElementById('source').value;

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
            alert('Error adding coin. Please check the coin ID.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error adding coin to portfolio');
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
            const parentRow = element.closest('.source-row');
            if (parentRow) {
                parentRow.remove();
            }
            // Check if this was the last source for the coin
            const sourcesCell = element.closest('.sources-cell');
            if (sourcesCell && sourcesCell.children.length <= 1) {
                // Remove the entire row if this was the last source
                const tableRow = sourcesCell.closest('tr');
                if (tableRow) {
                    tableRow.remove();
                }
            }
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
    sourceRow.className = 'source-row d-flex justify-content-between align-items-center mb-1';
    
    const nameSpan = document.createElement('span');
    nameSpan.className = 'source-name';
    nameSpan.textContent = sourceName;
    
    const rightDiv = document.createElement('div');
    
    const amountSpan = document.createElement('span');
    amountSpan.className = 'source-amount';
    amountSpan.textContent = amount.toFixed(8);
    
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-sm btn-danger ms-2 remove-source-btn';
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
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        
        const portfolioTable = document.getElementById('portfolioTable');
        portfolioTable.innerHTML = '';
        
        for (const [coinId, details] of Object.entries(data.portfolio)) {
            const row = document.createElement('tr');
            
            // Create sources list
            const sourcesCell = document.createElement('td');
            sourcesCell.className = 'sources-cell';
            for (const [sourceName, amount] of Object.entries(details.sources)) {
                sourcesCell.appendChild(createSourceElement(coinId, sourceName, amount));
            }
            
            const coinCell = document.createElement('td');
            coinCell.textContent = coinId;
            
            const balanceCell = document.createElement('td');
            balanceCell.textContent = details.total_amount.toFixed(8);
            
            const priceCell = document.createElement('td');
            priceCell.textContent = `$${details.price.toFixed(2)}`;
            
            const valueCell = document.createElement('td');
            valueCell.textContent = `$${(details.total_amount * details.price).toFixed(2)}`;
            
            row.appendChild(coinCell);
            row.appendChild(sourcesCell);
            row.appendChild(balanceCell);
            row.appendChild(priceCell);
            row.appendChild(valueCell);
            
            portfolioTable.appendChild(row);
        }
        
        document.getElementById('totalValue').textContent = data.total_value.toFixed(2);
    } catch (error) {
        console.error('Error:', error);
    }
}

async function loadPortfolio() {
    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        const portfolioDetails = document.getElementById('portfolioDetails');
        portfolioDetails.innerHTML = '';
        
        const coinTemplate = document.getElementById('coinTemplate');
        const sourceRowTemplate = document.getElementById('sourceRowTemplate');
        
        for (const [coinId, details] of Object.entries(data.portfolio)) {
            const coinSection = coinTemplate.content.cloneNode(true);
            coinSection.querySelector('.coin-name').textContent = coinId.charAt(0).toUpperCase() + coinId.slice(1);
            
            const tbody = coinSection.querySelector('tbody');
            
            for (const [source, amount] of Object.entries(details.sources)) {
                const sourceRow = sourceRowTemplate.content.cloneNode(true);
                const locationInput = sourceRow.querySelector('.location-input');
                const amountInput = sourceRow.querySelector('.amount-input');
                
                locationInput.value = source;
                amountInput.value = amount;
                
                // Save original values for comparison
                locationInput.dataset.originalValue = source;
                amountInput.dataset.originalValue = amount;
                
                const saveBtn = sourceRow.querySelector('.save-btn');
                saveBtn.style.display = 'none'; // Hide save button initially
                
                // Show save button when input changes
                locationInput.addEventListener('input', () => {
                    saveBtn.style.display = locationInput.value !== locationInput.dataset.originalValue ? 'inline-block' : 'none';
                });
                
                amountInput.addEventListener('input', () => {
                    saveBtn.style.display = amountInput.value !== amountInput.dataset.originalValue ? 'inline-block' : 'none';
                });
                
                // Handle save
                saveBtn.addEventListener('click', async () => {
                    const newLocation = locationInput.value;
                    const newAmount = parseFloat(amountInput.value);
                    const oldLocation = locationInput.dataset.originalValue;
                    
                    try {
                        // Remove old source if location changed
                        if (newLocation !== oldLocation) {
                            await fetch('/api/remove_source', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    coin_id: coinId,
                                    source: oldLocation
                                })
                            });
                        }
                        
                        // Add new source/amount
                        const response = await fetch('/api/add_coin', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                coin_id: coinId,
                                source: newLocation,
                                amount: newAmount
                            })
                        });
                        
                        const result = await response.json();
                        if (result.success) {
                            // Update original values
                            locationInput.dataset.originalValue = newLocation;
                            amountInput.dataset.originalValue = newAmount.toString();
                            saveBtn.style.display = 'none';
                        } else {
                            alert('Failed to save changes');
                        }
                    } catch (error) {
                        console.error('Error saving changes:', error);
                        alert('Error saving changes');
                    }
                });
                
                // Handle remove
                const removeBtn = sourceRow.querySelector('.remove-btn');
                removeBtn.addEventListener('click', async () => {
                    if (confirm('Are you sure you want to remove this entry?')) {
                        try {
                            const response = await fetch('/api/remove_source', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    coin_id: coinId,
                                    source: source
                                })
                            });
                            
                            const result = await response.json();
                            if (result.success) {
                                removeBtn.closest('tr').remove();
                                // Remove coin section if no sources left
                                if (tbody.children.length === 0) {
                                    tbody.closest('.coin-section').remove();
                                }
                            } else {
                                alert('Failed to remove entry');
                            }
                        } catch (error) {
                            console.error('Error removing entry:', error);
                            alert('Error removing entry');
                        }
                    }
                });
                
                tbody.appendChild(sourceRow);
            }
            
            portfolioDetails.appendChild(coinSection);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Handle adding new coins
document.getElementById('addCoinForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coinId = document.getElementById('coinId').value.toLowerCase();
    const source = document.getElementById('source').value;
    const amount = parseFloat(document.getElementById('amount').value);
    
    try {
        const response = await fetch('/api/add_coin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                coin_id: coinId,
                source: source,
                amount: amount
            })
        });
        
        const result = await response.json();
        if (result.success) {
            // Clear form
            e.target.reset();
            // Reload portfolio
            await loadPortfolio();
        } else {
            alert('Failed to add coin');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error adding coin');
    }
});

// Load portfolio on page load
document.addEventListener('DOMContentLoaded', loadPortfolio);

// Update portfolio every 30 seconds
updatePortfolio();
setInterval(updatePortfolio, 30000);
