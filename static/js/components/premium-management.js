function togglePremiumOptions(basketId, legIndex) {
    const dropdownId = `premium-dropdown-${basketId}-${legIndex}`;
    const dropdown = document.getElementById(dropdownId);

    document.querySelectorAll('.premium-dropdown-content').forEach(d => {
        if (d.id !== dropdownId) {
            d.classList.remove('show');
        }
    });

    dropdown.classList.toggle('show');
}

async function selectPremiumOption(basketId, legIndex, option) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !basket.legs[legIndex]) return;
    const leg = basket.legs[legIndex];
    const dropdownId = `premium-dropdown-${basketId}-${legIndex}`;
    document.getElementById(dropdownId).classList.remove('show');

    const premiumInput = document.getElementById(`premium-${basketId}-${legIndex}`);
    
    if (option === 'limit') {
        renderBaskets(); 
        updateLeg(basketId, legIndex, 'premium', '');
        updateLeg(basketId, legIndex, 'premiumType', 'limit');
        if (premiumInput) {
            premiumInput.disabled = false;
            premiumInput.placeholder = "Enter limit price";
            premiumInput.focus();
        }
        showNotification('Enter your limit price in the premium field', 'info');
        return;
    }
    const premiumData = await fetchPremiumMockData(leg);
    console.log('Premium Data:', leg, premiumData);
    if (!premiumData) return;

    let selectedPrice = 0;
    let premiumType = '';
    let message = '';

    switch (option) {
        case 'best_bid':
            selectedPrice = premiumData.best_bid;
            premiumType = 'best_bid';
            message = `Best Bid: ₹${selectedPrice}`;
            break;
        case 'best_ask':
            selectedPrice = premiumData.best_ask;
            premiumType = 'best_ask';
            message = `Best Ask: ₹${selectedPrice}`;
            break;
        case 'market_price':
            selectedPrice = premiumData.mid_price;
            premiumType = 'market_price';
            message = `Market Price: ₹${selectedPrice}`;
            renderBaskets();
            break;
    }

    
    updateLeg(basketId, legIndex, 'premium', selectedPrice);
    updateLeg(basketId, legIndex, 'premiumType', premiumType);
    await renderBaskets();
    if (premiumInput) {
        premiumInput.disabled = true;
        premiumInput.placeholder = `Auto: ₹${selectedPrice}`;
    }
    showNotification(message, 'success');
}

function openDepthModal(basketId, legIndex) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !basket.legs[legIndex]) return;

    const leg = basket.legs[legIndex];
    currentPremiumSelection = {
        basketId,
        legIndex
    };

    const dropdownId = `premium-dropdown-${basketId}-${legIndex}`;
    document.getElementById(dropdownId).classList.remove('show');

    const symbol = leg.symbol || 'OPTION';
    const strike = leg.strike || 'STRIKE';
    const type = leg.instrumentType;
    document.getElementById('depthModalTitle').textContent =
        `Market Depth - ${symbol} ${strike} ${type}`;

    populateMarketDepth(leg);
    document.getElementById('depthModal').style.display = 'block';
}

async function populateMarketDepth(leg) {
    
    const premiumData = await fetchPremiumMockData(leg);
    if (!premiumData || !premiumData.depth) {
        showNotification('Failed to load market depth data', 'error');
        return;
    }

    const bidLevelsContainer = document.getElementById('bidLevels');
    const askLevelsContainer = document.getElementById('askLevels');
    bidLevelsContainer.innerHTML = '';
    askLevelsContainer.innerHTML = '';

    premiumData.depth.bids.forEach(level => {
        const div = document.createElement('div');
        div.className = 'depth-level bid-level';
        div.innerHTML = `
            <div class="depth-price">₹${level.price}</div>
            <div class="depth-qty">${level.quantity}</div>
            <div class="depth-orders">${level.orders} orders</div>
        `;
        div.onclick = () => selectDepthPrice(level.price);
        bidLevelsContainer.appendChild(div);
    });

    premiumData.depth.asks.forEach(level => {
        const div = document.createElement('div');
        div.className = 'depth-level ask-level';
        div.innerHTML = `
            <div class="depth-price">₹${level.price}</div>
            <div class="depth-qty">${level.quantity}</div>
            <div class="depth-orders">${level.orders} orders</div>
       `;
       div.onclick = () => selectDepthPrice(level.price);
       askLevelsContainer.appendChild(div);
   });

   const bestBid = premiumData.best_bid || 0;
   const bestAsk = premiumData.best_ask || 0;
   const midPrice = premiumData.mid_price || 0;
   const spread = (bestAsk - bestBid).toFixed(2);

   document.getElementById('bestBid').textContent = `₹${bestBid}`;
   document.getElementById('bestAsk').textContent = `₹${bestAsk}`;
   document.getElementById('bidAskSpread').textContent = `₹${spread}`;
   document.getElementById('midPrice').textContent = `₹${midPrice}`;

   window.currentDepthData = {
       bestBid,
       bestAsk,
       midPrice,
       spread
   };
}

async function selectDepthPrice(price) {
   const {
       basketId,
       legIndex
   } = currentPremiumSelection;
   if (basketId !== null && legIndex !== null) {
       updateLeg(basketId, legIndex, 'premium', price);
       updateLeg(basketId, legIndex, 'premiumType', 'market_depth');
       await renderBaskets();
       closeDepthModal();
       showNotification(`Premium set to ₹${price} from market depth`, 'success');
   }
}

async function selectFromDepth(type) {
   const {
       basketId,
       legIndex
   } = currentPremiumSelection;
   if (basketId === null || legIndex === null) return;

   const depthData = window.currentDepthData;
   if (!depthData) return;

   let selectedPrice = 0;
   let message = '';
   let premiumType = '';

   switch (type) {
       case 'best_bid':
           selectedPrice = depthData.bestBid;
           message = `Premium set to Best Bid: ₹${selectedPrice}`;
           premiumType = 'best_bid';
           break;
       case 'best_ask':
           selectedPrice = depthData.bestAsk;
           message = `Premium set to Best Ask: ₹${selectedPrice}`;
           premiumType = 'best_ask';
           break;
       case 'mid_price':
           selectedPrice = depthData.midPrice;
           message = `Premium set to Mid Price: ₹${selectedPrice}`;
           premiumType = 'market_price';
           break;
   }
   await renderBaskets();

   if (selectedPrice > 0) {
       updateLeg(basketId, legIndex, 'premium', selectedPrice);
       updateLeg(basketId, legIndex, 'premiumType', premiumType);
       await renderBaskets();
       closeDepthModal();
       showNotification(message, 'success');
   }
}

function closeDepthModal() {
   document.getElementById('depthModal').style.display = 'none';
   currentPremiumSelection = {
       basketId: null,
       legIndex: null
   };
}

async function loadOptionChainPremium(basketId, legIndex) {
   const basket = baskets.find(b => b.id === basketId);
   if (!basket || !basket.legs[legIndex]) return;

   const leg = basket.legs[legIndex];

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
       const result = await apiCall('/get-live-data', 'POST', {
           symbol,
           expiry,
           strike,
           instrument_type: instrumentType
       });

       if (result && result.ltp) {
           updateLeg(basketId, legIndex, 'premium', result.ltp);
           updateLeg(basketId, legIndex, 'premiumType', 'live_market');
           await renderBaskets();
           showNotification(`Live premium loaded: ₹${result.ltp}`, 'success');
       } else {
           showNotification('Premium data not found', 'error');
       }
   } catch (error) {
       showNotification('Failed to load live premium', 'error');
       console.error(error);
   }
}

window.togglePremiumOptions = togglePremiumOptions;
window.selectPremiumOption = selectPremiumOption;
window.openDepthModal = openDepthModal;
window.selectDepthPrice = selectDepthPrice;
window.selectFromDepth = selectFromDepth;
window.closeDepthModal = closeDepthModal;
window.loadOptionChainPremium = loadOptionChainPremium;