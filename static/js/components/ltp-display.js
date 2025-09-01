function showLTPStatus(symbol, status, ltp = null, error = null) {
    const underlyingInput = document.getElementById('underlying');
    const container = underlyingInput.parentElement;
    
    const existingDisplay = container.querySelector('.ltp-info');
    if (existingDisplay) {
        existingDisplay.remove();
    }
    
    const ltpDiv = document.createElement('div');
    ltpDiv.className = 'ltp-info';
    
    if (status === 'loading') {
        ltpDiv.innerHTML = `<small style="color: #74b9ff;">📊 Loading ${symbol} price...</small>`;
    } else if (status === 'success') {
        ltpDiv.innerHTML = `<small style="color: #00b894;">📈 ${symbol}: ₹${ltp.toLocaleString()} <span style="color: #94a3b8;">(Live)</span></small>`;
        
        const triggerInput = document.getElementById('triggerPrice');
        if (triggerInput) {
            triggerInput.placeholder = `Current: ${ltp.toLocaleString()}`;
        }
    } else if (status === 'error') {
        ltpDiv.innerHTML = `<small style="color: #ff6b6b;">⚠️ ${symbol}: Price unavailable</small>`;
    }
    
    ltpDiv.style.marginTop = '5px';
    container.appendChild(ltpDiv);
}

function showSymbolLTP(basketId, legIndex, symbol, ltp) {
    const symbolInput = document.getElementById(`symbol-${basketId}-${legIndex}`);
    if (!symbolInput) return;
    
    const searchContainer = symbolInput.closest('.search-container');
    if (!searchContainer) return;
    
    const existingLTP = searchContainer.querySelector('.symbol-ltp-display');
    if (existingLTP) {
        existingLTP.remove();
    }
    
    const ltpDisplay = document.createElement('div');
    ltpDisplay.className = 'symbol-ltp-display';
    ltpDisplay.style.marginTop = '5px';
    ltpDisplay.innerHTML = `<small style="color: #00b894;">📈 ${symbol}: ₹${ltp.toLocaleString()} <span style="color: #94a3b8;">(Live)</span></small>`;
    
    const dropdown = searchContainer.querySelector('.search-dropdown');
    if (dropdown) {
        dropdown.insertAdjacentElement('afterend', ltpDisplay);
    } else {
        searchContainer.appendChild(ltpDisplay);
    }
}

window.showSymbolLTP = showSymbolLTP;
