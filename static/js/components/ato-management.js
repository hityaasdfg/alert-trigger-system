async function createATOWithProperMargins() {
    try {
        const alertErrors = validateAlert();
        if (alertErrors.length > 0) {
            showNotification(`Alert errors: ${alertErrors.join(', ')}`, 'error');
            return;
        }

        if (baskets.length === 0) {
            showNotification('Please create at least one basket!', 'error');
            return;
        }

        let allBasketErrors = [];
        baskets.forEach((basket, index) => {
            const errors = validateBasket(basket);
            if (errors.length > 0) {
                allBasketErrors.push(`Basket ${index + 1}: ${errors.join(', ')}`);
            }
        });

        if (allBasketErrors.length > 0) {
            showNotification(`Basket errors: ${allBasketErrors.join(' | ')}`, 'error');
            return;
        }

        showNotification('Calculating TOTAL ATO margin with proper offsetting across ALL baskets...', 'info');

        const allLegsFromAllBaskets = [];
        const basketsWithData = [];

        for (const basket of baskets) {
            const validLegs = basket.legs.filter(leg => isLegDataComplete(leg));
            
            const legsWithData = validLegs.map(leg => ({
                action: leg.action,
                instrument_type: leg.instrumentType,
                symbol: leg.symbol,
                strike: leg.instrumentType !== 'EQ' ? parseFloat(leg.strike) || null : null,
                expiry: leg.instrumentType !== 'EQ' ? leg.expiry || null : null,
                quantity: parseInt(leg.quantity) || 0,
                price: (leg.instrumentType === 'EQ' || leg.instrumentType === 'FUT') ? 
                    parseFloat(leg.premium) || null : null,  
                premium: (leg.instrumentType === 'CE' || leg.instrumentType === 'PE') ? 
                        parseFloat(leg.premium) || null : null,
                premium_type: leg.premiumType || null,
                sl: currentRiskMode[basket.id] === 'individual' ? 
                    parseFloat(leg.sl) || null : null,
                tp: currentRiskMode[basket.id] === 'individual' ? 
                    parseFloat(leg.tp) || null : null,
                basket_id: basket.id,
                basket_label: basket.label
            }));

            allLegsFromAllBaskets.push(...legsWithData);

            basketsWithData.push({
                id: basket.id,
                label: basket.label,
                strategy: basket.strategy || 'custom',
                risk_mode: currentRiskMode[basket.id] || 'individual',
                legs: legsWithData,
                risk_management: {
                    primary_mode: currentRiskMode[basket.id],
                    settings: basket.riskSettings
                }
            });
        }

        console.log(`🚀 Calling TOTAL ATO margin API with ${allLegsFromAllBaskets.length} legs from ${baskets.length} baskets:`, allLegsFromAllBaskets);

        const response = await fetch('http://192.168.4.221:9000/api/get-basket-margin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                legs: allLegsFromAllBaskets
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const marginData = await response.json();

        if (marginData.error) {
            throw new Error(marginData.error);
        }

        const totalATOMargin = marginData.required_margin || 0;
        const totalBlockedMargin = marginData.blocked_margin || 0;

        console.log(`✅ TOTAL ATO margin calculated (with offsetting across all baskets): ₹${totalATOMargin.toLocaleString()}`);

        for (const basket of basketsWithData) {
            const basketMargin = await calculateBasketMargin(baskets.find(b => b.id === basket.id));
            basket.margin_required = basketMargin;
            
            basket.legs.forEach(leg => {
                const originalLeg = baskets.find(b => b.id === basket.id)?.legs.find(l => 
                    l.action === leg.action && l.instrumentType === leg.instrument_type && 
                    l.symbol === leg.symbol && l.strike === leg.strike
                );
                if (originalLeg) {
                    leg.margin = marginCache[getMarginCacheKey(originalLeg)] || 0;
                }
            });
        }

        const atoData = {
            symbol: document.getElementById('underlying').value,
            operator: document.getElementById('operator').value,
            threshold: parseFloat(document.getElementById('triggerPrice').value),
            valid_till: document.getElementById('validTill').value,
            status: 'waiting',
            total_margin_required: totalATOMargin,
            total_blocked_margin: totalBlockedMargin,
            baskets: basketsWithData,
            created_at: new Date().toISOString(),
            total_baskets: basketsWithData.length,
            total_legs: allLegsFromAllBaskets.length,
            margin_calculation_method: 'API with cross-basket offsetting'
        };

        console.log('🚀 ATO Data with PROPER TOTAL margin (not sum of baskets):', atoData);
        const userKey = encodeURIComponent(window.ATO_USER_KEY);
        const result = await apiCall(
          `/alerts?userKey=${userKey}`,  // ← backticks here
          'POST',
          atoData
        );

        showNotification('ATO Created Successfully!', 'success');
        console.log('✅ ATO Created with proper total margin:', result.alert);

        resetForm();
        await loadActiveATOs();

    } catch (error) {
        console.error('❌ Error creating ATO:', error);
        showNotification(`Failed to create ATO: ${error.message}`, 'error');
    }
}

async function triggerATO(atoId) {
    try {
        await apiCall(`/alerts/${atoId}/trigger?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`, 'POST');
        showNotification('ATO triggered successfully!', 'success');
        await loadActiveATOs();
    } catch (error) {
        showNotification(`Failed to trigger ATO: ${error.message}`, 'error');
    }
}

async function deleteATO(atoId) {
    if (!confirm('Are you sure you want to delete this ATO?')) {
        return;
    }

    try {
        await apiCall(`/alerts/${atoId}`, 'DELETE');
        showNotification('ATO deleted successfully!', 'success');
        await loadActiveATOs();
    } catch (error) {
        showNotification(`Failed to delete ATO: ${error.message}`, 'error');
    }
}






// Updated showExitForm for single leg exit with partial support
function showExitForm(legData, basketData) {
  return new Promise((resolve) => {
    // 🔁 Fetch LTP dynamically
    fetch('/api/get-live-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: legData.symbol,
        expiry: legData.expiry ? legData.expiry.split('T')[0] : null,
        strike: legData.strike || 0,
        instrument_type: legData.instrument_type
      })
    })
      .then(res => res.json())
      .then(data => {
        const ltpSpan = document.getElementById(`${modalId}-ltp`);
        if (data.mid_price !== undefined) {
          ltpSpan.textContent = `₹${data.mid_price}`;
        } else if (data.error) {
          ltpSpan.textContent = `Error: ${data.error}`;
        } else {
          ltpSpan.textContent = 'Unavailable';
        }
      })
      .catch(err => {
        document.getElementById(`${modalId}-ltp`).textContent = `Error`;
        console.error('Live price fetch failed:', err);
      });
    const modalId = 'exit-form-modal-' + Date.now();
    const modalHtml = `
      <div id="${modalId}" style="
          position: fixed; top: 0; left: 0; width: 100%; height: 100%;
          background: rgba(0,0,0,0.4); z-index: 1000;
          display: flex; align-items: center; justify-content: center;
      ">
        <div style="
            background: #312f38;
            border-radius: 12px;
            width: 95vw; max-width: 420px; max-height: 90vh;
            overflow: hidden; display: flex; flex-direction: column;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
        ">
          <!-- Header -->
          <div style="padding: 12px 16px; background: #26242e; color: white; font-weight: bold; display: flex; justify-content: space-between; align-items: center;">
            <span>Partial Exit Position</span>
            <button id="${modalId}-close" style="background: none; border: none; color: white; font-size: 20px;">&times;</button>
          </div>

          <!-- Body -->
          <div style="padding: 16px; overflow-y: auto;">
            <div style="margin-bottom: 12px; color: #cbd5e1; font-size: 14px;">
              <strong>Basket:</strong> ${basketData.label}<br>
              <strong>Symbol:</strong> ${legData.symbol}<br>
              <strong>Type:</strong> ${legData.instrument_type}<br>
              <strong>Qty:</strong> ${legData.quantity}<br>
              <strong>Entry Price:</strong> ₹${legData.price || legData.premium || '-'}<br>
              <strong>Live LTP:</strong> <span id="${modalId}-ltp">Loading...</span>
            </div>
            <label>Quantity:</label>
            <input id="${modalId}-quantity" type="number" value="${legData.quantity}" min="1" max="${legData.quantity}" style="width: 100%; padding: 8px; margin-bottom: 10px;">

            <label>Price Type:</label>
            <select id="${modalId}-price-type" style="width: 100%; padding: 8px; margin-bottom: 10px;">
              <option value="market">Market</option>
              <option value="best_bid">Best Bid</option>
              <option value="best_ask">Best Ask</option>
              <option value="limit">Limit</option>
            </select>

            <div id="${modalId}-custom-price-section" style="display: none;">
              <label>Custom Price (Limit):</label>
              <input id="${modalId}-custom-price" type="number" step="0.05" placeholder="₹0.00" style="width: 100%; padding: 8px;">
            </div>
          </div>

          <!-- Footer -->
          <div style="padding: 12px 16px; background: #26242e; display: flex; justify-content: flex-end; gap: 8px;">
            <button id="${modalId}-cancel" style="padding: 8px 16px; background: #64748b; color: white; border: none; border-radius: 6px;">Cancel</button>
            <button id="${modalId}-submit" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 6px;">Exit</button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalElement = document.getElementById(modalId);
    const quantityInput = document.getElementById(`${modalId}-quantity`);
    const priceTypeSelect = document.getElementById(`${modalId}-price-type`);
    const customPriceSection = document.getElementById(`${modalId}-custom-price-section`);
    const customPriceInput = document.getElementById(`${modalId}-custom-price`);
    const submitBtn = document.getElementById(`${modalId}-submit`);
    const cancelBtn = document.getElementById(`${modalId}-cancel`);
    const closeBtn = document.getElementById(`${modalId}-close`);

    priceTypeSelect.addEventListener('change', () => {
      customPriceSection.style.display = priceTypeSelect.value === 'limit' ? 'block' : 'none';
    });

    const cleanup = (result) => {
      modalElement.remove();
      resolve(result);
    };

    submitBtn.addEventListener('click', () => {
      const quantity = parseInt(quantityInput.value);
      const priceType = priceTypeSelect.value;
      const customPrice = parseFloat(customPriceInput.value);
      const isPartialExit = quantity < legData.quantity;

      if (!quantity || quantity > legData.quantity) {
        alert('Invalid quantity');
        return;
      }
      if (priceType === 'limit' && (!customPrice || customPrice <= 0)) {
        alert('Invalid price');
        return;
      }

      cleanup({ quantity, priceType, customPrice: priceType === 'limit' ? customPrice : null, isPartialExit });
    });

    cancelBtn.addEventListener('click', () => cleanup(null));
    closeBtn.addEventListener('click', () => cleanup(null));
    modalElement.addEventListener('click', (e) => {
      if (e.target === modalElement) cleanup(null);
    });
  });
}

// New confirmExitBasket for basket-wide immediate exit
async function confirmExitBasket(basket) {
  if (!confirm(`Are you sure you want to exit all legs in basket "${basket.label}"?`)) return;

  const legsExitData = {};
  basket.legs.forEach((leg, idx) => {
    if (leg.status !== 'exited') {
      legsExitData[idx] = {
        exit_price_type: 'market',
        exit_quantity: leg.quantity,
        is_partial_exit: false
      };
    }
  });

  const response = await fetch(`/api/baskets/${basket.id}/exit-legs_all?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exit_all_legs: true, exit_reason: 'Direct Confirm Exit', legs_exit_data: legsExitData })
  });

  const result = await response.json();
  if (result.success) {
    basket.legs.forEach((leg, idx) => {
      if (result.data?.basket?.legs[idx]) {
        Object.assign(leg, result.data.basket.legs[idx]);
      }
    });
    basket.status = 'exited';
    basket.exited_at = new Date().toISOString();
    updateActiveATOs();
    setTimeout(() => loadActiveATOs(), 500);
  } else {
    alert('Failed to exit basket: ' + (result.message || 'Unknown error'));
  }
} 

// original exitBasket used for partial leg exit only
async function exitBasket(basketId) {
  const ato = atos.find(a => a.baskets.some(b => b.id == basketId));
  if (!ato || ato.status !== 'triggered') return;

  const basket = ato.baskets.find(b => b.id == basketId);
  const activeLegs = basket.legs.filter(leg => leg.status !== 'exited');
  if (activeLegs.length === 0) return;

  const allLegsExitData = [];
  for (let i = 0; i < activeLegs.length; i++) {
    const leg = activeLegs[i];
    const exitData = await showExitForm(leg, basket);
    if (!exitData) return;
    allLegsExitData.push({ legIndex: i, exitData });
  }

  try {
    const legsExitData = {};
    allLegsExitData.forEach(item => {
      const originalIndex = getOriginalLegIndex(basket, activeLegs[item.legIndex]);
      legsExitData[originalIndex.toString()] = {
        exit_price: item.exitData.customPrice,
        exit_quantity: item.exitData.quantity,
        exit_price_type: item.exitData.priceType,
        is_partial_exit: item.exitData.isPartialExit
      };
    });

    const response = await fetch(`/api/baskets/${basket.id}/exit-legs_all?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exit_all_legs: true, exit_reason: 'Manual Partial Exit', legs_exit_data: legsExitData })
    });

    const result = await response.json();
    if (!result.success) throw new Error(result.message || 'Exit failed');

    result.data.basket.legs.forEach((apiLeg, idx) => {
      if (!apiLeg) return;
      const legToUpdate = basket.legs[idx];
      Object.assign(legToUpdate, apiLeg);
    });

    if (basket.legs.every(leg => leg.status === 'exited')) {
      basket.status = 'exited';
      basket.exited_at = new Date().toISOString();
    }

    updateActiveATOs();
    setTimeout(() => loadActiveATOs(), 500);
  } catch (err) {
    console.error(err);
  }
} 

// Process individual leg exit

// Updated processLegExit function to work with enhanced API
async function processLegExit(leg, basket, exitData) {
    try {
        // Prepare enhanced exit request for your updated API
        const exitRequest = {
            // Basic fields (existing)
            exit_all_legs: false,
            leg_index: getOriginalLegIndex(basket, leg),
            exit_reason: 'Manual leg exit with form',
            
            // NEW: Enhanced exit form data
            exit_price: exitData.customPrice,
            exit_quantity: exitData.quantity,
            exit_price_type: exitData.priceType,
            is_partial_exit: exitData.isPartialExit
        };
        
        console.log('Sending enhanced leg exit request:', exitRequest);
        
        // Call your enhanced API endpoint
        const response = await fetch(`/api/baskets/${basket.id}/exit-legs_all?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(exitRequest)
        });
        
        const result = await response.json();
        console.log('Enhanced leg exit response:', result);

        if (result.success) {
            // Update leg data with all new exit information from API response
            const originalIndex = getOriginalLegIndex(basket, leg);
            const legToUpdate = basket.legs[originalIndex];
            
            // Always update exit details first
            const exitPrice = exitData.customPrice || result.executed_price || 0;
            legToUpdate.exit_price = exitPrice;
            legToUpdate.exit_price_type = exitData.priceType;
            legToUpdate.exit_timestamp = new Date().toISOString();
            
            if (exitData.isPartialExit) {
                // Partial exit: Update quantities but don't mark as exited
                console.log(`Before partial exit - Quantity: ${legToUpdate.quantity}, Exit Quantity: ${legToUpdate.exit_quantity || 0}`);
                
                // Update remaining quantity
                legToUpdate.quantity = Math.max(0, legToUpdate.quantity - exitData.quantity);
                
                // Accumulate exit quantities for partial exits
                legToUpdate.exit_quantity = (legToUpdate.exit_quantity || 0) + exitData.quantity;
                
                // Keep leg status as active for partial exits
                // legToUpdate.status remains unchanged (should be 'active' or similar)
                
                console.log(`After partial exit - Quantity: ${legToUpdate.quantity}, Exit Quantity: ${legToUpdate.exit_quantity}`);
                
                showNotification(`✅ Partial exit: ${exitData.quantity} units at ₹${exitPrice} (${legToUpdate.quantity} remaining)`, 'success');
                
            } else {
                // Full exit: Mark as exited and update all exit details
                legToUpdate.status = 'exited';
                legToUpdate.exited_at = new Date().toISOString();
                legToUpdate.exit_quantity = exitData.quantity;
                
                console.log(`Full exit - Total quantity exited: ${legToUpdate.exit_quantity}`);
                
                showNotification(`✅ Full exit: ${exitData.quantity} units at ₹${exitPrice}`, 'success');
            }
            
            // Update leg data from API response if available (this should override local updates)
            if (result.data && result.data.basket && result.data.basket.legs) {
                const apiLegData = result.data.basket.legs[originalIndex];
                if (apiLegData) {
                    console.log('Updating from API response:', apiLegData);
                    
                    // Update all fields from API response
                    legToUpdate.status = apiLegData.status || legToUpdate.status;
                    legToUpdate.quantity = apiLegData.quantity !== undefined ? apiLegData.quantity : legToUpdate.quantity;
                    legToUpdate.exited_at = apiLegData.exited_at || legToUpdate.exited_at;
                    legToUpdate.exit_price = apiLegData.exit_price !== undefined ? apiLegData.exit_price : legToUpdate.exit_price;
                    legToUpdate.exit_quantity = apiLegData.exit_quantity !== undefined ? apiLegData.exit_quantity : legToUpdate.exit_quantity;
                    legToUpdate.exit_price_type = apiLegData.exit_price_type || legToUpdate.exit_price_type;
                }
            }
            
            console.log('Final leg state after update:', {
                quantity: legToUpdate.quantity,
                exit_quantity: legToUpdate.exit_quantity,
                exit_price: legToUpdate.exit_price,
                exit_price_type: legToUpdate.exit_price_type,
                status: legToUpdate.status
            });
            
        } else {
            throw new Error(result.message || 'Exit failed');
        }
        
    } catch (error) {
        console.error('Error exiting leg:', error);
        showNotification(`❌ Failed to exit position: ${error.message}`, 'error');
        throw error;
    }
}


// Helper function to get original leg index
function getOriginalLegIndex(basket, targetLeg) {
    return basket.legs.findIndex(leg => 
        leg.id === targetLeg.id || 
        (leg.symbol === targetLeg.symbol && leg.action === targetLeg.action && leg.strike === targetLeg.strike)
    );
}








// Enhanced exitSingleTrade function with proper margin display
async function exitSingleTrade(atoId) {
    alert("calling exitSingleTrade with enhanced API");
    const ato = atos.find(a => a.id == atoId);
    if (!ato || ato.status !== 'triggered') {
        showNotification('ATO must be in triggered status to exit trades', 'error');
        return;
    }

    const activeBasketsWithLegs = ato.baskets.filter(b => {
        return b.legs.some(leg => leg.status !== 'exited');
    });
    
    if (activeBasketsWithLegs.length === 0) {
        showNotification('No active legs to exit', 'info');
        return;
    }
    
    let basketOptions = '';
    let totalMarginAcrossBaskets = 0;
    
    activeBasketsWithLegs.forEach((basket, index) => {
        const activeLegs = basket.legs.filter(leg => leg.status !== 'exited').length;
        const totalLegs = basket.legs.length;
        const margin = basket.margin_required || basket.margin || 0;
        
        // Add to total margin
        totalMarginAcrossBaskets += margin;

        basketOptions += `${index + 1}. ${basket.label} (${activeLegs}/${totalLegs} active legs)\n`;
        basketOptions += `   Strategy: ${basket.strategy.toUpperCase()}`;
        
        // Show margin if available
        if (margin > 0) {
            basketOptions += ` | Margin: ₹${margin.toLocaleString()}`;
        } else {
            basketOptions += ` | Margin: Not calculated`;
        }
        basketOptions += `\n\n`;
    });

    // Add total margin info at the end
    basketOptions += `📊 TOTAL PORTFOLIO MARGIN: ₹${totalMarginAcrossBaskets.toLocaleString()}\n`;
    basketOptions += `💼 ACTIVE BASKETS: ${activeBasketsWithLegs.length}\n`;

    // Enhanced modal with margin details
    const basketSelection = await prompt(`📊 SELECT BASKET TO EXIT:\n\n${basketOptions}Enter basket number (1-${activeBasketsWithLegs.length}):`);

    if (!basketSelection) return;
    
    const basketIndex = parseInt(basketSelection) - 1;
    if (basketIndex < 0 || basketIndex >= activeBasketsWithLegs.length) {
        showNotification('Invalid basket selection!', 'error');
        return;
    }
    
    const selectedBasket = activeBasketsWithLegs[basketIndex];
    
    const activeLegs = selectedBasket.legs.filter(leg => leg.status !== 'exited');
    
    if (activeLegs.length === 0) {
        showNotification('No active legs in this basket', 'info');
        return;
    }
    
    let legOptions = '';
    let basketTotalMargin = 0;
    
    activeLegs.forEach((leg, index) => {
        // Calculate individual leg margin (if available)
        const legMargin = leg.margin_required || leg.margin || 0;
        basketTotalMargin += legMargin;
        
        legOptions += `${index + 1}. ${leg.action} ${leg.symbol} ${leg.instrument_type}`;
        if (leg.strike) legOptions += ` ${leg.strike}`;
        legOptions += `\n   Qty: ${leg.quantity} | Price: ₹${leg.price || leg.premium || '0'}`;
        
        // Show individual leg margin if available
        if (legMargin > 0) {
            legOptions += ` | Margin: ₹${legMargin.toLocaleString()}`;
        } else {
            legOptions += ` | Margin: N/A`;
        }
        legOptions += `\n\n`;
    });
    
    legOptions += `${activeLegs.length + 1}. 🚨 EXIT ALL LEGS IN THIS BASKET\n\n`;
    
    // Enhanced leg selection with margin summary
    legOptions += `📈 BASKET MARGIN SUMMARY:\n`;
    legOptions += `   • Individual Legs Total: ₹${basketTotalMargin.toLocaleString()}\n`;
    legOptions += `   • Basket Required Margin: ₹${(selectedBasket.margin_required || selectedBasket.margin || 0).toLocaleString()}\n`;
    legOptions += `   • Strategy: ${selectedBasket.strategy.toUpperCase()}\n`;
    
    const legSelection = await prompt(`🔄 SELECT LEG TO EXIT FROM "${selectedBasket.label}":\n\n${legOptions}Enter leg number (1-${activeLegs.length + 1}):`);
    
    if (!legSelection) return;
    
    const legIndex = parseInt(legSelection) - 1;
    if (legIndex < 0 || legIndex > activeLegs.length) {
        showNotification('Invalid leg selection!', 'error');
        return;
    }
    
    const exitAllLegs = legIndex === activeLegs.length;
    
    let confirmMessage;
    if (exitAllLegs) {
        const basketMargin = selectedBasket.margin_required || selectedBasket.margin || 0;
        confirmMessage = `🚨 CONFIRM EXIT ALL LEGS:\n\n`;
        confirmMessage += `📋 BASKET: ${selectedBasket.label}\n`;
        confirmMessage += `📈 STRATEGY: ${selectedBasket.strategy.toUpperCase()}\n`;
        confirmMessage += `🔢 LEGS: ${activeLegs.length} legs will be exited\n`;

        confirmMessage += `This will exit ALL active legs in this basket.\n`;
        confirmMessage += `Continue with full basket exit?`;
    } else {
        const selectedLeg = activeLegs[legIndex];
        const legMargin = selectedLeg.margin_required || selectedLeg.margin || 0;
        const basketMargin = selectedBasket.margin_required || selectedBasket.margin || 0;
        
        confirmMessage = `🚨 CONFIRM EXIT SINGLE LEG:\n\n`;
        confirmMessage += `📋 BASKET: ${selectedBasket.label}\n`;
        confirmMessage += `📊 LEG: ${selectedLeg.action} ${selectedLeg.symbol} ${selectedLeg.instrument_type} ${selectedLeg.strike || ''}\n`;
        confirmMessage += `🔢 QUANTITY: ${selectedLeg.quantity}\n`;
        confirmMessage += `This will exit only this specific leg.\n`;
        confirmMessage += `Continue with single leg exit?`;
    }

    // Enhanced confirmation with complete margin breakdown
    const confirmed = await confirm(confirmMessage);
    
    if (confirmed) {
        try {
            showNotification(exitAllLegs ? 'Exiting all legs...' : 'Exiting leg...', 'info');
            
            const exitRequest = {
                exit_all_legs: exitAllLegs,
                leg_index: exitAllLegs ? null : getOriginalLegIndex(selectedBasket, activeLegs[legIndex]),
                exit_reason: exitAllLegs ? 'Manual exit all legs in basket' : 'Manual exit single leg'
            };
            
            console.log('Sending exit request:', exitRequest);
            
            const response = await fetch(`/api/baskets/${selectedBasket.id}/exit-legs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(exitRequest)
            });
            
            const result = await response.json();
            console.log('Exit response:', result);

            if (result.success) {
                if (exitAllLegs) {
                    selectedBasket.legs.forEach(leg => {
                        leg.status = 'exited';
                        leg.exited_at = new Date().toISOString();
                    });
                    
                    selectedBasket.status = 'exited';
                    selectedBasket.exited_at = new Date().toISOString();
                    
                    const releasedMargin = selectedBasket.margin_required || selectedBasket.margin || 0;
                    showNotification(`✅ All legs in "${selectedBasket.label}" exited successfully! Margin released: ₹${releasedMargin.toLocaleString()}`, 'success');
                } else {
                    const selectedLeg = activeLegs[legIndex];
                    const originalIndex = getOriginalLegIndex(selectedBasket, selectedLeg);
                    selectedBasket.legs[originalIndex].status = 'exited';
                    selectedBasket.legs[originalIndex].exited_at = new Date().toISOString();
                    
                    const remainingActiveLegs = selectedBasket.legs.filter(leg => leg.status !== 'exited').length;
                    if (remainingActiveLegs === 0) {
                        selectedBasket.status = 'exited';
                        selectedBasket.exited_at = new Date().toISOString();
                    }
                    
                    const legMargin = selectedLeg.margin_required || selectedLeg.margin || 0;
                    showNotification(`✅ Leg exited successfully! ${legMargin > 0 ? `Margin impact: ₹${legMargin.toLocaleString()}` : ''}`, 'success');
                }
                
                updateActiveATOs();
                
                setTimeout(() => {
                    loadActiveATOs();
                }, 500);
            } else {
                throw new Error(result.message || 'Unknown error occurred');
            }
        } catch (error) {
            console.error('Error exiting leg(s):', error);
            showNotification(`❌ Failed to exit leg(s): ${error.message}`, 'error');
        }
    }
}

// Helper function to get margin information safely
function getMarginInfo(item, fallback = 'N/A') {
    const margin = item.margin_required || item.margin || 0;
    return margin > 0 ? `₹${margin.toLocaleString()}` : fallback;
}









function showConfirmExitModal({ title, summaryLines, confirmText = 'Confirm Exit', cancelText = 'Cancel' }) {
  return new Promise((resolve) => {
    const modalId = 'confirm-exit-modal-' + Date.now();

    const modalHtml = `
      <div id="${modalId}" style="
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.4); z-index: 1000;
        display: flex; align-items: center; justify-content: center;">
        <div style="
          background: #312f38; color: #cbd5e1;
          border-radius: 12px;
          width: 90vw; max-width: 450px;
          overflow: hidden; box-shadow: 0 0 30px rgba(0,0,0,0.5);">
          
          <!-- Header -->
          <div style="padding: 16px; background: #26242e; color: white; font-size: 16px; font-weight: bold;">
            ${title}
          </div>

          <!-- Body -->
          <div style="padding: 16px; font-size: 14px; max-height: 60vh; overflow-y: auto;">
            <pre style="white-space: pre-wrap; font-family: inherit;">${summaryLines}</pre>
          </div>

          <!-- Footer -->
          <div style="padding: 12px 16px; background: #26242e; display: flex; justify-content: flex-end; gap: 8px;">
            <button id="${modalId}-cancel" style="padding: 8px 16px; background: #64748b; color: white; border: none; border-radius: 6px;">${cancelText}</button>
            <button id="${modalId}-submit" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 6px;">${confirmText}</button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modal = document.getElementById(modalId);
    const cleanup = (confirmed) => {
      modal.remove();
      resolve(confirmed);
    };

    document.getElementById(`${modalId}-submit`).addEventListener('click', () => cleanup(true));
    document.getElementById(`${modalId}-cancel`).addEventListener('click', () => cleanup(false));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) cleanup(false);
    });
  });
}


async function exitSingleBasket(basketId) {
  // 1) Find the basket in memory
  const basket = atos.flatMap(a => a.baskets).find(b => b.id === basketId);
  if (!basket) {
    showNotification('Basket not found', 'error');
    return;
  }

  const legsToExit = basket.legs.filter(l => l.status !== 'exited');
  if (legsToExit.length === 0) {
    showNotification('No active legs to exit in this basket', 'info');
    return;
  }

  const margin = basket.margin_required || basket.margin || 0;

  const summary =
  `📦 Basket: ${basket.label || basket.id}\n` +
  `🔢 Active Legs: ${legsToExit.length}\n` +
  `💰 Margin Release: ₹${margin.toLocaleString()}\n\n` +
  `⚠️ This will exit ALL active legs in this basket.`;

    const userConfirmed = await showConfirmExitModal({
    title: 'Confirm Exit Basket',
    summaryLines: summary,
    confirmText: 'Exit Basket'
    });

    if (!userConfirmed) return;

  try {
    showNotification(`🔄 Exiting ${legsToExit.length} legs in basket...`, 'info');

    const legs_exit_data = {};
    legsToExit.forEach((leg, idx) => {
      if (leg.premium_type === 'limit') return;
      legs_exit_data[idx] = {
        exit_price: leg.current_price,
        exit_price_type: 'market'
      };
    });

    await apiCall(
      `/baskets/${basket.id}/exit-legs_all?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`,
      'POST',
      {
        exit_all_legs: true,
        exit_reason: 'Manual exit basket',
        legs_exit_data
      }
    );

    showNotification(
      `🎯 Basket exited! Margin released: ₹${margin.toLocaleString()}`,
      'success'
    );
    loadActiveATOs();

  } catch (err) {
    console.error('❌ exitSingleBasket error', err);
    showNotification(`❌ Failed to exit basket: ${err.message}`, 'error');
  }
}

async function exitAllTrades(atoId) {
  // 1) Find the ATO in memory (or you could re-fetch from the server)
  const ato = atos.find(a => a.id == atoId);
  if (!ato || ato.status !== 'triggered') {
    showNotification('ATO must be in triggered status to exit all trades', 'error');
    return;
  }

  // 2) Identify baskets with any non-exited legs
  const activeBaskets = ato.baskets.filter(b =>
    b.legs.some(l => l.status !== 'exited')
  );
  if (activeBaskets.length === 0) {
    showNotification('No active baskets to exit', 'info');
    return;
  }

  // 3) Compute totals for confirmation dialog
  const totalMargin = activeBaskets.reduce(
    (sum, b) => sum + (b.margin_required || b.margin || 0),
    0
  );
  const totalLegs = activeBaskets.reduce(
    (sum, b) => sum + b.legs.filter(l => l.status !== 'exited').length,
    0
  );

  // 4) Build a per-basket breakdown string
  let breakdown = '\n📊 BASKET BREAKDOWN:\n';
  activeBaskets.forEach((b, i) => {
    const m   = b.margin_required || b.margin || 0;
    const cnt = b.legs.filter(l => l.status !== 'exited').length;
    breakdown += `   ${i+1}. ${b.label}: ${cnt} legs, ₹${m.toLocaleString()}\n`;
  });

  // 5) Ask user to confirm
  const summary =
  `🆔 ATO: #${ato.id.toString().slice(-6)}\n` +
  `📦 Active Baskets: ${activeBaskets.length}\n` +
  `🔢 Total Active Legs: ${totalLegs}\n` +
  '📊 BASKET BREAKDOWN:\n' +
  activeBaskets.map((b, i) => {
    const m = b.margin_required || b.margin || 0;
    const cnt = b.legs.filter(l => l.status !== 'exited').length;
    return `   ${i + 1}. ${b.label}: ${cnt} legs, ₹${m.toLocaleString()}`;
  }).join('\n') +
  `\n\n⚠️ This will exit ALL active positions.`;

const userConfirmed = await showConfirmExitModal({
  title: 'Confirm Exit All Trades',
  summaryLines: summary,
  confirmText: 'Exit All Trades'
});

if (!userConfirmed) return;


  try {
    showNotification(`🔄 Exiting ${totalLegs} legs...`, 'info');

    // 6) For each basket, call the exit-legs API
    for (const basket of activeBaskets) {
      // Prepare leg-specific exit data, skipping 'limit' types
      const legs_exit_data = {};
      basket.legs
        .filter(l => l.status !== 'exited')
        .forEach((leg, idx) => {
          if (leg.premium_type === 'limit') {
            // backend will leave price/premium as-is
            return;
          }
          legs_exit_data[idx] = {
            exit_price: leg.current_price,   // your LTP field
            exit_price_type: 'market'
          };
        });

      // Call your Flask endpoint with the correct basket ID
      await apiCall(
        `/baskets/${basket.id}/exit-legs_all?userKey=${encodeURIComponent(window.ATO_USER_KEY)}`,
        'POST',
        {
          exit_all_legs: true,
          exit_reason: 'Manual exit all trades',
          legs_exit_data
        }
      );
    }

    // 7) Notify the user & refresh
    showNotification(
      `🎯 All trades exited! Margin released: ₹${totalMargin.toLocaleString()}`,
      'success'
    );
    loadActiveATOs();

  } catch (err) {
    console.error('❌ exitAllTrades error', err);
    showNotification(`❌ Failed to exit trades: ${err.message}`, 'error');
  }
}



async function cloneATO(atoId) {
   try {
       const result = await apiCall(`/alerts/${atoId}`);
       const ato = result.alert;

       document.getElementById('underlying').value = ato.symbol;
       document.getElementById('operator').value = ato.operator;
       document.getElementById('triggerPrice').value = ato.threshold;

        const dt = new Date(Date.now() + 86400000);
        dt.setHours(15, 30, 0, 0), dt.setMinutes(dt.getMinutes() - dt.getTimezoneOffset());
        document.getElementById('validTill').value = dt.toISOString().slice(0, 16);

       baskets = ato.baskets.map(basket => ({
           id: basketIdCounter++,
           label: basket.label + ' (Clone)',
           strategy: basket.strategy,
           legs: basket.legs.map(leg => ({
               action: leg.action,
               instrumentType: leg.instrument_type,
               symbol: leg.symbol,
               strike: leg.strike || '',
               expiry: leg.expiry ? leg.expiry.split('T')[0] : '',
               quantity: leg.quantity || '',
               price: leg.price || '',
               premium: leg.premium || '',
               premiumType: leg.premium_type || '',
               sl: leg.sl || '',
               tp: leg.tp || ''
           })),
           riskMode: basket.risk_mode,
           riskSettings: basket.risk_settings || {}
       }));

       baskets.forEach(basket => {
           currentRiskMode[basket.id] = basket.riskMode;
       });

       showMainTab('builder');
       document.querySelector('.main-tab[onclick="showMainTab(\'builder\')"]').classList.add('active');
       await renderBaskets();

       showNotification(`ATO cloned successfully! Modified for new trading session.`, 'success');
   } catch (error) {
       showNotification(`Failed to clone ATO: ${error.message}`, 'error');
   }
}

function viewATODetails(atoId) {
   const ato = atos.find(a => a.id == atoId);
   if (!ato) return;

   let details = `Advanced ATO Details (ID: ${ato.id})\n\n`;
   details += `Status: ${ato.status.toUpperCase()}\n`;
   details += `Created: ${dateTimeHandler.formatDateTimeForUser(ato.created_at)}\n\n`;

   details += `Alert Configuration:\n`;
   details += `- Symbol: ${ato.symbol}\n`;
   details += `- Condition: ${ato.operator} ${ato.threshold}\n`;
   details += `- Valid till: ${new Date(ato.valid_till).toLocaleDateString('en-GB')} ${new Date(ato.valid_till).toLocaleTimeString('en-US')}\n\n`;

   details += `Total Margin Required: ₹${(ato.total_margin_required || 0).toLocaleString()}\n\n`;

   details += `Baskets (${ato.baskets.length}):\n`;
   ato.baskets.forEach((basket, i) => {
       details += `\nBasket ${i + 1}: ${basket.label}\n`;
       details += `- Strategy: ${basket.strategy}\n`;
       details += `- Margin Required: ₹${(basket.margin_required || 0).toLocaleString()}\n`;
       details += `- Primary Risk Mode: ${basket.risk_mode}\n`;
       details += `- Legs (${basket.legs.length}):\n`;

       basket.legs.forEach((leg, j) => {
           details += `  ${j + 1}. ${leg.action} ${leg.symbol} ${leg.instrument_type}`;
           if (leg.strike) details += ` Strike:${leg.strike}`;
           if (leg.expiry) details += ` Exp:${leg.expiry}`;
           details += ` Qty:${leg.quantity}`;
           if (leg.price) details += ` Price:₹${leg.price}`;
           if (leg.premium) details += ` Premium:₹${leg.premium}`;
           details += ` Margin:₹${(leg.margin || 0).toLocaleString()}`;
           if (leg.sl) details += ` SL:${leg.sl}`;
           if (leg.tp) details += ` TP:${leg.tp}`;
           details += `\n`;
       });
   });

   alert(details);
}

async function resetForm() {
   document.getElementById('underlying').value = '';
   document.getElementById('operator').value = '';
   document.getElementById('triggerPrice').value = '';
   document.getElementById('validTill').value = '';

   baskets = [];
   basketIdCounter = 1;
   currentRiskMode = {};

   await renderBaskets();
}

function getOriginalLegIndex(basket, activeLeg) {
   return basket.legs.findIndex(leg => 
       leg.id === activeLeg.id || 
       (leg.symbol === activeLeg.symbol && 
       leg.instrument_type === activeLeg.instrument_type && 
       leg.strike === activeLeg.strike && 
       leg.action === activeLeg.action)
   );
}


window.createATOWithProperMargins = createATOWithProperMargins;
window.triggerATO = triggerATO;
window.deleteATO = deleteATO;
window.exitAllTrades = exitAllTrades;
window.exitSingleTrade = exitSingleTrade;
window.cloneATO = cloneATO;
window.viewATODetails = viewATODetails;