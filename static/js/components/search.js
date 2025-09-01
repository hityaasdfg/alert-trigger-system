const searchSymbol = debounce(function(basketId, legIndex, query) {
    const dropdown = document.getElementById(`symbol-dropdown-${basketId}-${legIndex}`);

    if (!query || query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }

    let results = [];
    const seenSymbols = new Set();
    const queryLower = query.toLowerCase();

    // Get user selected instrument type
    const instrumentTypeSelect = document.getElementById(`instrument-type-${basketId}-${legIndex}`);
    const selectedInstrumentType = instrumentTypeSelect ? instrumentTypeSelect.value : '';

    if (symbolsData.all_symbols) {
        symbolsData.all_symbols.forEach(item => {
            const symbol = item.symbol || '';
            const name = item.name || '';
            const itemInstrumentType = item.instrument_type || '';

            // Determine display value based on selected instrument type
            let displayValue = '';
            if (selectedInstrumentType.toUpperCase() === 'EQ') {
                displayValue = symbol;
            } else {
                displayValue = name;
            }

            if (
                displayValue.toLowerCase().includes(queryLower) &&
                itemInstrumentType.toUpperCase() === selectedInstrumentType.toUpperCase() && // match selected type
                !seenSymbols.has(displayValue)
            ) {
                seenSymbols.add(displayValue);
                results.push({ symbol: displayValue, name, type: itemInstrumentType });
            }
        });
    }

    results.sort((a, b) => {
        const aExact = a.symbol.toLowerCase() === queryLower;
        const bExact = b.symbol.toLowerCase() === queryLower;
        if (aExact && !bExact) return -1;
        if (!aExact && bExact) return 1;
        return a.symbol.localeCompare(b.symbol);
    });

    if (results.length > 0) {
        dropdown.innerHTML = results.slice(0, 10).map(item =>
            `<div class="search-option" onclick="selectSymbol(${basketId}, ${legIndex}, '${item.symbol}')">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${item.symbol}</strong>
                        ${item.name ? `<div style="font-size: 11px; color: #94a3b8;">${item.name}</div>` : ''}
                    </div>
                    <span style="font-size: 10px; color: #667eea; background: rgba(102, 126, 234, 0.1); padding: 2px 6px; border-radius: 3px;">
                        ${item.type}
                    </span>
                </div>
            </div>`
        ).join('');
        dropdown.classList.add('show');
    } else {
        dropdown.innerHTML = '<div class="search-option">No results found</div>';
        dropdown.classList.add('show');
    }
}, 150);


async function selectSymbol(basketId, legIndex, symbol) {
  try {
    // 1) Set the symbol input & hide dropdown
    const symInput = document.getElementById(`symbol-${basketId}-${legIndex}`);
    const symDD    = document.getElementById(`symbol-dropdown-${basketId}-${legIndex}`);
    if (symInput) symInput.value = symbol;
    if (symDD)    symDD.classList.remove('show');

    // 2) Read selected instrument type
    const instTypeEl = document.getElementById(`instrument-type-${basketId}-${legIndex}`);
    const instType   = (instTypeEl?.value || '').toUpperCase();
    console.log(`Selecting symbol: ${symbol} with instrument type: ${instType}`);

    // 3) Core state updates & LTP fetch
    updateLeg(basketId, legIndex, 'symbol', symbol);
    onSymbolChange(basketId, legIndex, symbol);
    fetchSymbolLTP(basketId, legIndex, symbol);

    // 4) Determine lotSize
    let lotSize = null;
    if (instType === 'FUT') {
      // call your endpoint for FUT lot size
      const resp = await fetch('/api/get_lot_size', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, instrument_type: instType })
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      lotSize = data.lot_size ?? null;

    } else if (instType === 'EQ') {
      // equities always 1 share lot
      lotSize = 1;
    }

    // 5) Apply lotSize & update UI if we got one
    if (lotSize != null) {
      updateLeg(basketId, legIndex, 'lotSize', lotSize);

      const lotLabel = document.getElementById(`lot-size-${basketId}-${legIndex}`);
      if (lotLabel) {
        lotLabel.textContent = `(Lot Size: ${lotSize})`;
      }

    }

  } catch (error) {
    console.error('Error selecting symbol:', error);
    showNotification('Error selecting symbol', 'error');
  }
}

const searchUnderlying = debounce(function(query) {
    const dropdown = document.getElementById('underlying-dropdown');

    if (!query || query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }

    let results = [];
    const seenSymbols = new Set();
    const queryLower = query.toLowerCase();

    if (symbolsData.all_symbols) {
        symbolsData.all_symbols.forEach(item => {
            const symbol = item.symbol || '';
            const name = item.name || '';
            if (
                (symbol.toLowerCase().includes(queryLower) || 
                name.toLowerCase().includes(queryLower)) &&
                !seenSymbols.has(symbol)
            ) {
                seenSymbols.add(symbol);
                results.push({ symbol, name, type: item.segment});
            }
        });
    }

    

    results.sort((a, b) => {
        const aExact = a.symbol.toLowerCase() === queryLower;
        const bExact = b.symbol.toLowerCase() === queryLower;
        if (aExact && !bExact) return -1;
        if (!aExact && bExact) return 1;
        return a.symbol.localeCompare(b.symbol);
    });

    if (results.length > 0) {
        dropdown.innerHTML = results.slice(0, 10).map(item =>
            `<div class="search-option" onclick="selectUnderlying('${item.symbol}')">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${item.symbol}</strong>
                        ${item.name ? `<div style="font-size: 11px; color: #94a3b8;">${item.name}</div>` : ''}
                    </div>
                    <span style="font-size: 10px; color: #667eea; background: rgba(102, 126, 234, 0.1); padding: 2px 6px; border-radius: 3px;">
                        ${item.type}
                    </span>
                </div>
            </div>`
        ).join('');
        dropdown.classList.add('show');
    } else {
        dropdown.innerHTML = '<div class="search-option">No results found</div>';
        dropdown.classList.add('show');
    }
}, 150);

function selectUnderlying(symbol) {
    try {
        document.getElementById('underlying').value = symbol;
        document.getElementById('underlying-dropdown').classList.remove('show');
        fetchAndDisplayLTP(symbol);
    } catch (error) {
        console.error('Error selecting underlying:', error);
    }
}

async function searchExpiry(basketId, legIndex, query) {
    const dropdown = document.getElementById(`expiry-dropdown-${basketId}-${legIndex}`);
    const leg = baskets.find(b => b.id === basketId)?.legs[legIndex];

    if (!leg?.symbol) {
        dropdown.innerHTML = '<div class="search-option">Select symbol first</div>';
        return dropdown.classList.add('show');
    }

    // cache by symbol and type
    const cacheKey = `${leg.symbol}_${leg.instrumentType}`;
    let expiryData = window.apiCache.expiries[cacheKey];

    if (!expiryData && !window.apiCache.loading.expiries[cacheKey]) {
        dropdown.innerHTML = '<div class="search-option">Loading expiries...</div>';
        dropdown.classList.add('show');

        window.apiCache.loading.expiries[cacheKey] = true;
        try {
            const url = new URL(`http://192.168.4.221:9000/api/expiries/${leg.symbol}`);
            url.searchParams.set('instrument_type', leg.instrumentType);
            const response = await fetch(url);
            const data = await response.json();

            if (response.ok && data.status === 'success') {
                expiryData = data;
                window.apiCache.expiries[cacheKey] = expiryData;
            }
        } catch (error) {
            console.error('Error loading expiries:', error);
        } finally {
            window.apiCache.loading.expiries[cacheKey] = false;
        }
    }

    if (!expiryData?.expiries?.length) {
        dropdown.innerHTML = '<div class="search-option">No expiries found</div>';
        return dropdown.classList.add('show');
    }

    const today = new Date();
    const filtered = (query || '').trim()
        ? expiryData.expiries.filter(e => e.toLowerCase().includes(query.toLowerCase()))
        : expiryData.expiries;

    if (!filtered.length) {
        dropdown.innerHTML = '<div class="search-option">No expiries match your search</div>';
        return dropdown.classList.add('show');
    }

    dropdown.innerHTML = filtered.map(expiry => {
        let label = expiry;
        const ed = new Date(expiry);
        if (!isNaN(ed)) {
            const days = Math.ceil((ed - today) / (1000*60*60*24));
            if (days > 0)      label = dateTimeHandler.formatExpiryLabel(ed);
            else if (days < 0) label = `Expired ${Math.abs(days)} day${Math.abs(days)>1?'s':''} ago`;
            else               label = 'Expires today';
        }
        return `
            <div class="search-option" onclick="selectExpiry(${basketId}, ${legIndex}, '${expiry}')">
                <div style="display:flex;justify-content:space-between">
                    <strong>${expiry}</strong>
                    <span style="color:#94a3b8;font-size:11px">${label}</span>
                </div>
            </div>`;
    }).join('');
    dropdown.classList.add('show');
}

// --- handler when user picks an expiry ---
async function selectExpiry(basketId, legIndex, expiry) {
    try {
        console.log(`Selecting expiry: ${expiry} for basket ${basketId}, leg ${legIndex}`);
        
        const input    = document.getElementById(`expiry-${basketId}-${legIndex}`);
        const dropdown = document.getElementById(`expiry-dropdown-${basketId}-${legIndex}`);
        if (input)    input.value    = expiry;
        if (dropdown) dropdown.classList.remove('show');
        updateLeg(basketId, legIndex, 'expiry', expiry);
        const leg = baskets.find(b => b.id === basketId)?.legs[legIndex];
        if (!leg) return;
        
        // Invalidate strikes cache always
        if (leg.symbol) {
            const key = `${leg.symbol}_${expiry}`;
            delete window.apiCache.strikes[key];
            delete window.apiCache.loading.strikes[key];
        }
        
        
        // Option legs: load strikes etc.
        if (leg.instrumentType === 'CE' || leg.instrumentType === 'PE') {
            onExpiryChange(basketId, legIndex, expiry);
        
        // Equity/Futures: fetch lot size instead
        renderBaskets();
        } 
        
    } catch (error) {
        console.error('Error selecting expiry:', error);
        showNotification('Error selecting expiry', 'error');
    }
}


async function searchStrike(basketId, legIndex, query) {
   const dropdown = document.getElementById(`strike-dropdown-${basketId}-${legIndex}`);
   const leg = baskets.find(b => b.id === basketId)?.legs[legIndex];

    if (leg?.instrumentType === 'EQ' || leg?.instrumentType === 'FUT') {
        dropdown.innerHTML = '';
        dropdown.classList.remove('show');
        return;
    }

   if (!leg?.symbol || !leg?.expiry || !leg?.instrumentType) {
       dropdown.innerHTML = '<div class="search-option">Select symbol, expiry, and instrument type first</div>';
       dropdown.classList.add('show');
       return;
   }

   const cacheKey = `${leg.symbol}_${leg.expiry}_${leg.instrumentType}`;
   let strikesInfo = window.apiCache.strikes[cacheKey];

   if (!strikesInfo && !window.apiCache.loading.strikes[cacheKey]) {
       dropdown.innerHTML = '<div class="search-option">Loading strikes...</div>';
       dropdown.classList.add('show');

       window.apiCache.loading.strikes[cacheKey] = true;
       try {
           const response = await fetch('http://192.168.4.221:9000/api/option-chain', {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json',
               },
               body: JSON.stringify({
                   symbol: leg.symbol,
                   expiry: leg.expiry,
                   instrument_type: leg.instrumentType
               })
           });
           
           const data = await response.json();
           if (response.ok && data.status === 'success') {
               strikesInfo = data;
               window.apiCache.strikes[cacheKey] = strikesInfo;
               console.log('Loaded strikes with lot size and OI data:', strikesInfo);
               
               if (strikesInfo.strikes && strikesInfo.strikes.length > 0) {
                   leg.lotSize = strikesInfo.strikes[0].lot_size;
               }
           }
       } catch (error) {
           console.error('Error loading strikes:', error);
       } finally {
           window.apiCache.loading.strikes[cacheKey] = false;
       }
   }

   if (!strikesInfo?.strikes || strikesInfo.strikes.length === 0) {
       dropdown.innerHTML = '<div class="search-option">No strikes found</div>';
       dropdown.classList.add('show');
       return;
   }

   let filteredStrikes = strikesInfo.strikes;
   if (query && query.trim().length > 0) {
       const queryLower = query.toLowerCase();
       filteredStrikes = strikesInfo.strikes.filter(item => {
           const strike = typeof item === 'object' ? item.strikes : item;
           return strike.toString().includes(query);
       });
   }

   filteredStrikes.sort((a, b) => {
       const strikeA = typeof a === 'object' ? parseFloat(a.strikes) : parseFloat(a);
       const strikeB = typeof b === 'object' ? parseFloat(b.strikes) : parseFloat(b);
       return strikeA - strikeB;
   });

   if (filteredStrikes.length > 0) {
       dropdown.innerHTML = filteredStrikes.slice(0, 15).map(item => {
           const strike = typeof item === 'object' ? item.strikes : item;
           const oiChange = typeof item === 'object' ? item.oi_change || 0 : 0;
           const oiChangePercent = typeof item === 'object' ? item.oi_change_percent || 0 : 0;
           
           const oiChangeColor = oiChange > 0 ? '#00b894' : oiChange < 0 ? '#ff6b6b' : '#94a3b8';
           
           return `<div class="search-option" onclick="selectStrike(${basketId}, ${legIndex}, '${strike}')">
               <div style="display: flex; justify-content: space-between; align-items: center;">
                   <strong>${strike}</strong>
                   <div style="display: flex; align-items: center; gap: 10px;">
                       <span style="font-size: 11px; color: ${oiChangeColor};">
                           OI: ${oiChange >= 0 ? '+' : ''}${oiChange.toLocaleString()}
                       </span>
                       <span style="font-size: 11px; color: ${oiChangeColor};">
                           (${oiChangePercent >= 0 ? '+' : ''}${oiChangePercent}%)
                       </span>
                   </div>
               </div>
           </div>`;
       }).join('');
   } else {
       dropdown.innerHTML = '<div class="search-option">No strikes match your search</div>';
   }

   dropdown.classList.add('show');
}

async function selectStrike(basketId, legIndex, strike) {
   try {
       console.log(`Selecting strike: ${strike} for basket ${basketId}, leg ${legIndex}`);
       
       const input = document.getElementById(`strike-${basketId}-${legIndex}`);
       const dropdown = document.getElementById(`strike-dropdown-${basketId}-${legIndex}`);
       
       if (input) {
           input.value = strike;
       }
       
       if (dropdown) {
           dropdown.classList.remove('show');
       }
       
       const scrollPosition = {
           top: window.pageYOffset || document.documentElement.scrollTop,
           left: window.pageXOffset || document.documentElement.scrollLeft
       };
       
       const basket = baskets.find(b => b.id === basketId);
       if (!basket || !basket.legs[legIndex]) return;
       
       const leg = basket.legs[legIndex];
       
       const cacheKey = `${leg.symbol}_${leg.expiry}_${leg.instrumentType}`;
       const strikesInfo = window.apiCache.strikes[cacheKey];
       
       if (strikesInfo && strikesInfo.strikes) {
           const selectedStrikeData = strikesInfo.strikes.find(item => {
               const itemStrike = typeof item === 'object' ? item.strikes : item;
               return itemStrike.toString() === strike.toString();
           });
           
           if (selectedStrikeData) {
               leg.lotSize = selectedStrikeData.lot_size || leg.lotSize;
               console.log(`Lot size for selected strike: ${leg.lotSize}`);
           }
       }
       
       updateLeg(basketId, legIndex, 'strike', strike);
       updateLegInDOM(basketId, legIndex);
       
       
   } catch (error) {
       console.error('Error selecting strike:', error);
       showNotification('Error selecting strike', 'error');
   }
}

window.selectUnderlying = selectUnderlying;
window.selectSymbol = selectSymbol;
window.searchExpiry = searchExpiry;
window.searchStrike = searchStrike;
