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
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        
        const portfolioDetails = document.getElementById('portfolioDetails');
        portfolioDetails.innerHTML = '';
        
        for (const [coinId, details] of Object.entries(data.portfolio)) {
            const section = document.createElement('div');
            section.className = 'card mb-3';
            
            const header = document.createElement('div');
            header.className = 'card-header d-flex justify-content-between align-items-center';
            
            const titleDiv = document.createElement('div');
            titleDiv.innerHTML = `
                <h5 class="mb-0">${coinId.charAt(0).toUpperCase() + coinId.slice(1)}</h5>
                <small class="text-muted">Price: $${details.price.toFixed(2)}</small>
            `;
            
            const totalValue = document.createElement('div');
            totalValue.className = 'text-end';
            totalValue.innerHTML = `
                <h6 class="mb-0">Total Value</h6>
                <strong>$${(details.total_amount * details.price).toFixed(2)}</strong>
            `;
            
            header.appendChild(titleDiv);
            header.appendChild(totalValue);
            
            const body = document.createElement('div');
            body.className = 'card-body';
            
            const sourcesList = document.createElement('div');
            sourcesList.className = 'sources-list';
            
            for (const [sourceName, amount] of Object.entries(details.sources)) {
                sourcesList.appendChild(createSourceElement(coinId, sourceName, amount));
            }
            
            body.appendChild(sourcesList);
            section.appendChild(header);
            section.appendChild(body);
            portfolioDetails.appendChild(section);
        }
        
        document.getElementById('totalValue').textContent = data.total_value.toFixed(2);
    } catch (error) {
        console.error('Error:', error);
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
