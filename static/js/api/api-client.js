async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.message || `HTTP ${response.status}`);
    }

    return result;
}

// async function loadActiveATOs() {
//     try {
//         const result = await apiCall('/alerts');
//         atos = result.alerts || [];
//         updateActiveATOs();
//     } catch (error) {
//         console.error('Failed to load active ATOs:', error);
//         showNotification('Failed to load active ATOs', 'error');
//     }
// }


async function loadActiveATOs() {
  try {
    const userKey = encodeURIComponent(window.ATO_USER_KEY);
    const result = await apiCall(`/alerts?userKey=${userKey}`, 'GET');  // add userKey
    atos = result.alerts || [];
    updateActiveATOs();
  } catch (error) {
    console.error('Failed to load active ATOs:', error);
    showNotification('Failed to load active ATOs', 'error');
  }
}


async function loadSymbols() {
    try {
        const result = await apiCall('/symbols');
        symbolsData = result.symbols;
        console.log('Symbols loaded:', symbolsData);
    } catch (error) {
        console.error('Failed to load symbols:', error);
        showNotification('Failed to load symbols', 'error');
    }
}

async function loadStrikes(symbol, expiry, instrumentType) {
    if (!symbol || !expiry || !instrumentType) return null;
    
    const cacheKey = `${symbol}_${expiry}_${instrumentType}`;
    
    if (window.apiCache.strikes[cacheKey]) {
        return window.apiCache.strikes[cacheKey];
    }
    
    if (window.apiCache.loading.strikes[cacheKey]) {
        return null;
    }
    
    try {
        window.apiCache.loading.strikes[cacheKey] = true;
        
        const response = await fetch('/option-chain', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                symbol,
                expiry,
                instrument_type: instrumentType
            })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            window.apiCache.strikes[cacheKey] = data;
            return data;
        } else {
            console.error('Error loading strikes:', data.message || 'Unknown error');
            return null;
        }
    } catch (error) {
        console.error('Error in loadStrikes:', error);
        return null;
    } finally {
        window.apiCache.loading.strikes[cacheKey] = false;
    }
}

async function loadExpiries(symbol) {
    try {
        const result = await apiCall(`/expiries/${symbol}`);
        expiriesData[symbol] = result;
        return result;
    } catch (error) {
        console.error('Failed to load expiries:', error);
        showNotification('Failed to load expiries', 'error');
        return null;
    }
}

async function fetchPremiumMockData(leg) {
    const { symbol, expiry, strike, instrumentType } = leg;
    if (instrumentType === 'EQ') {
        if (!symbol || !instrumentType) {
            showNotification('Please select symbol and instrument type for Equity', 'error');
            return;
        }
    } else if (instrumentType === 'FUT') {
        if (!symbol || !expiry || !instrumentType) {
            showNotification('Please select symbol, expiry, and instrument type for Futures', 'error');
            return;
        }
    } else {
        // CE or PE options
        if (!symbol || !expiry || !strike || !instrumentType) {
            showNotification('Please select symbol, expiry, strike, and instrument type for Options', 'error');
            return;
        }
    }

    try {
        return await apiCall('/get-live-data', 'POST', {
            symbol,
            expiry,
            strike,
            instrument_type: instrumentType
        });
    } catch (err) {
        console.error('Premium fetch error:', err);
        showNotification('Error fetching mock premium data', 'error');
        return null;
    }
}

async function fetchAndDisplayLTP(symbol) {
    try {
        showLTPStatus(symbol, 'loading');
        
        const response = await fetch('http://192.168.4.221:9000/api/symbol-live-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                instrument: symbol
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showLTPStatus(symbol, 'success', data.ltp);
        } else {
            showLTPStatus(symbol, 'error', null, data.error);
        }
        
    } catch (error) {
        console.error('LTP fetch error:', error);
        showLTPStatus(symbol, 'error', null, error.message);
    }
}

async function fetchSymbolLTP(basketId, legIndex, symbol) {
    try {
        const response = await fetch('http://192.168.4.221:9000/api/symbol-live-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                instrument: symbol
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.ltp) {
            showSymbolLTP(basketId, legIndex, symbol, data.ltp);
        } else {
            console.log('LTP not available for', symbol);
        }
        
    } catch (error) {
        console.error('Error fetching symbol LTP:', error);
    }
}

window.fetchSymbolLTP = fetchSymbolLTP;
window.fetchAndDisplayLTP = fetchAndDisplayLTP;
window.apiCall = apiCall;
window.loadActiveATOs = loadActiveATOs;
window.loadSymbols = loadSymbols;
window.loadStrikes = loadStrikes;
window.loadExpiries = loadExpiries; 
window.fetchPremiumMockData = fetchPremiumMockData;