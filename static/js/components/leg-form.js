function togglePremiumVisibility(basketId, legIndex, instrumentType) {
    const premiumRow = document.getElementById(`premium-row-${basketId}-${legIndex}`);
    const strikeExpiryInputs = document.querySelectorAll(`#expiry-${basketId}-${legIndex}, #strike-${basketId}-${legIndex}`);
    
    if (premiumRow) {
        if (instrumentType === 'CE' || instrumentType === 'PE') {
            premiumRow.classList.remove('hidden');
            strikeExpiryInputs.forEach(input => {
                if (input) input.closest('.form-group').classList.remove('hidden');
            });
        } else {
            premiumRow.classList.add('hidden');
            if (instrumentType === 'EQ') {
                strikeExpiryInputs.forEach(input => {
                    if (input) input.closest('.form-group').classList.add('hidden');
                });
            } else {
                strikeExpiryInputs.forEach(input => {
                    if (input) input.closest('.form-group').classList.remove('hidden');
                });
            }
        }
    }
}

function updateLegInDOM(basketId, legIndex) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !basket.legs[legIndex]) return;
    
    const leg = basket.legs[legIndex];
    
    const quantityInput = document.getElementById(`quantity-${basketId}-${legIndex}`);
    if (quantityInput) {
        const currentValue = quantityInput.value;
        
        let lotSizeLabel = document.getElementById(`lot-size-${basketId}-${legIndex}`);
        if (!lotSizeLabel) {
            lotSizeLabel = document.createElement('span');
            lotSizeLabel.id = `lot-size-${basketId}-${legIndex}`;
            lotSizeLabel.className = 'lot-size-label';
            lotSizeLabel.style.fontSize = '50px';
            lotSizeLabel.style.color = '#94a3b8';
            lotSizeLabel.style.marginLeft = '-20px';
            quantityInput.parentNode.appendChild(lotSizeLabel);
        }
        
        if (leg.lotSize) {
            lotSizeLabel.textContent = `(Lot Size: ${leg.lotSize})`;
        } else {
            lotSizeLabel.textContent = '';
        }
        
        quantityInput.value = currentValue;
    }
    
    updateLegMarginDisplay(basketId, legIndex);
}

function updateCapitalDisplay(basketId, legIndex) {
  // 1) Grab the inputs for this specific leg
  const qtyEl   = document.getElementById(`quantity-${basketId}-${legIndex}`);
  const priceEl = document.getElementById(`price-${basketId}-${legIndex}`);
  const displayEl = document.getElementById(`leg-margin-${basketId}-${legIndex}`);
  if (!qtyEl || !priceEl || !displayEl) return;

  // 2) Parse their current values
  const qty   = parseFloat(qtyEl.value)   || 0;
  const price = parseFloat(priceEl.value) || 0;

  // 3) Compute capital and update the DOM
  const capital = qty * price;
  displayEl.innerHTML = `
    💰 <strong>Capital: ₹${capital.toLocaleString()}</strong>
  `;
}



async function renderLegForm(basket, leg, legIndex) {
    const hideExpiry = leg.instrumentType === 'EQ';
    const hideStrike = leg.instrumentType === 'EQ' || leg.instrumentType === 'FUT';
    const legMargin = await calculateLegMargin(leg);
    const basketId = basket.id;
    const isOption   = ['CE','PE'].includes(leg.instrumentType);
    const fieldName  = isOption ? 'premium' : 'price';      // which key on leg
    const fieldValue = isOption ? leg.premium : leg.price;  // what's displayed
    const typeKey    = isOption ? 'premiumType' : 'priceType'; // if you track “type” for price too

    const displayQuantity = leg.rawQuantity || '';

    // Ensure individual riskSettings defaults exist
    if (!basket.riskSettings) {
        basket.riskSettings = {
            individual: {
                defaultTpType: 'percentage',
                defaultSlType: 'percentage'
            }
        };
    } else if (!basket.riskSettings.individual) {
        basket.riskSettings.individual = {
            defaultTpType: 'percentage',
            defaultSlType: 'percentage'
        };
    } else if (!basket.riskSettings.individual.defaultTpType) {
        basket.riskSettings.individual.defaultTpType = 'percentage';
        basket.riskSettings.individual.defaultSlType = 'percentage';
    }

    const tpType = basket.riskSettings.individual.defaultTpType;
    const slType = basket.riskSettings.individual.defaultSlType;

    return `
        <div class="leg-item">
            <div class="leg-header">
                <span class="leg-title">Leg ${legIndex + 1}</span>
                <button class="remove-leg-btn" onclick="removeLeg(${basketId}, ${legIndex})">Remove</button>
            </div>
            <div class="form-row">
                <!-- Action -->
                <div class="form-group">
                    <label>Action</label>
                    <select id="action-${basketId}-${legIndex}"
                            onchange="updateLeg(${basketId}, ${legIndex}, 'action', this.value)">
                        <option value="B" ${leg.action === 'B' ? 'selected' : ''}>Buy (B)</option>
                        <option value="S" ${leg.action === 'S' ? 'selected' : ''}>Sell (S)</option>
                    </select>
                </div>

                <!-- Instrument Type -->
                <div class="form-group">
                    <label>Instrument Type</label>
                    <select id="instrument-type-${basketId}-${legIndex}"
                            onchange="updateLeg(${basketId}, ${legIndex}, 'instrumentType', this.value); renderBaskets();">
                        <option value="">Select Type</option>
                        <option value="CE"  ${leg.instrumentType === 'CE'  ? 'selected' : ''}>Call Option (CE)</option>
                        <option value="PE"  ${leg.instrumentType === 'PE'  ? 'selected' : ''}>Put Option (PE)</option>
                        <option value="FUT" ${leg.instrumentType === 'FUT' ? 'selected' : ''}>Future (FUT)</option>
                        <option value="EQ"  ${leg.instrumentType === 'EQ'  ? 'selected' : ''}>Equity (EQ)</option>
                    </select>
                </div>

                <!-- Symbol -->
                <div class="form-group">
                    <label>Symbol</label>
                    <div class="search-container">
                        <input type="text" id="symbol-${basketId}-${legIndex}" class="search-input"
                               placeholder="Type to search symbols..."
                               onkeyup="searchSymbol(${basketId}, ${legIndex}, this.value)"
                               value="${leg.symbol || ''}" autocomplete="off">
                        <div id="symbol-dropdown-${basketId}-${legIndex}" class="search-dropdown"></div>
                    </div>
                </div>

                <!-- Expiry Date (hidden only for EQ) -->
                <div class="form-group ${hideExpiry ? 'hidden' : ''}">
                    <label>Expiry Date</label>
                    <div class="search-container">
                        <input type="text" id="expiry-${basketId}-${legIndex}" class="search-input"
                               placeholder="Type to search expiries..."
                               onfocus="searchExpiry(${basketId}, ${legIndex}, this.value)"
                               onkeyup="searchExpiry(${basketId}, ${legIndex}, this.value)"
                               onchange="if(this.value) onExpiryChange(${basketId}, ${legIndex}, this.value)"
                               value="${leg.expiry || ''}" autocomplete="off">
                        <div id="expiry-dropdown-${basketId}-${legIndex}" class="search-dropdown"></div>
                    </div>
                </div>

                <!-- Strike Price (hidden for EQ, disabled for FUT) -->
                <div class="form-group ${hideStrike ? 'hidden' : ''}">
                    <label>Strike Price</label>
                    <div class="search-container">
                        <input type="text"
                               id="strike-${basketId}-${legIndex}"
                               class="search-input"
                               placeholder="Type to search strikes..."
                               onfocus="searchStrike(${basketId}, ${legIndex}, this.value)"
                               onkeyup="searchStrike(${basketId}, ${legIndex}, this.value)"
                               onchange="if(this.value) updateLeg(${basketId}, ${legIndex}, 'strike', this.value )"
                               value="${leg.strike || ''}"
                               autocomplete="off"
                               ${hideStrike ? 'disabled' : ''}>
                        <div id="strike-dropdown-${basketId}-${legIndex}" class="search-dropdown"></div>
                    </div>
                </div>

                <!-- Quantity -->
                <div class="form-group">
                    <label>Quantity <span id="lot-size-${basketId}-${legIndex}" style="font-size: 15px; color: #94a3b8; margin-left: 8px;"> ${leg.lotSize ? `(Lot Size: ${leg.lotSize})` : ''} </span></label>
                    <div style="display: flex; align-items: center;">
                        <input type="number"
                            id="quantity-${basketId}-${legIndex}"
                            value="${leg.rawQuantity || ''}"
                            onchange="
                                updateLeg(${basketId}, ${legIndex}, 'quantity', this.value);
                                updateCapitalDisplay(${basketId}, ${legIndex});
                            "
                            placeholder="Enter lots">
                    </div>
                </div>

                

                <!-- Individual Risk (SL/TP) -->
                ${currentRiskMode[basketId] === 'individual' ? `
                <div class="form-group">
                    <label>${getTpSlLabel(tpType, 'SL')}</label>
                    <input type="number"
                           id="sl-${basketId}-${legIndex}"
                           value="${leg.sl || ''}"
                           step="${getTpSlStep(tpType)}"
                           placeholder="${getTpSlPlaceholder(tpType, 'SL')}"
                           onchange="updateLeg(${basketId}, ${legIndex}, 'sl', this.value);"
                           style="border-left: 3px solid #ff6b6b;">
                    <small style="color: #94a3b8; font-size: 11px; margin-top: 4px; display: block;">
                        ${leg.sl ? getTpSlExample(tpType, leg.sl, 'SL') : 'Enter SL value'}
                    </small>
                </div>
                <div class="form-group">
                    <label>${getTpSlLabel(tpType, 'TP')}</label>
                    <input type="number"
                           id="tp-${basketId}-${legIndex}"
                           value="${leg.tp || ''}"
                           step="${getTpSlStep(tpType)}"
                           placeholder="${getTpSlPlaceholder(tpType, 'TP')}"
                           onchange="updateLeg(${basketId}, ${legIndex}, 'tp', this.value);"
                           style="border-left: 3px solid #00b894;">
                    <small style="color: #94a3b8; font-size: 11px; margin-top: 4px; display: block;">
                        ${leg.tp ? getTpSlExample(tpType, leg.tp, 'TP') : 'Enter TP value'}
                    </small>
                </div>
                ` : ''}

            </div>

            <!-- Premium (only for CE/PE) -->
            <div class="form-row">
                <div class="form-group" style="flex: 1;">
                    <label>${isOption ? 'Premium (₹)' : 'Price (₹)'}</label>
                    <div class="premium-input-group">
                        <input type="number" id="premium-${basketId}-${legIndex}"
                            value="${leg.premium || ''}" 
                            onchange="updateLeg(${basketId}, ${legIndex}, 'premium', this.value); updateLeg(${basketId}, ${legIndex}, 'premiumType', 'manual'); debouncedMarginUpdate(${basketId});" 
                            step="0.01" 
                            placeholder="Enter premium"
                            style="width: 100%;">
                            <div class="premium-dropdown"
                            <button type="button" class="btn btn-info premium-options-btn" onclick="togglePremiumOptions(${basketId}, ${legIndex})">
                                Options ▼
                            </button>
                            <div id="premium-dropdown-${basketId}-${legIndex}" class="premium-dropdown-content">
                                <div class="premium-option market-data" onclick="selectPremiumOption(${basketId}, ${legIndex}, 'best_bid')">
                                    📈 Best Bid
                                </div>
                                <div class="premium-option market-data" onclick="selectPremiumOption(${basketId}, ${legIndex}, 'best_ask')">
                                    📉 Best Ask
                                </div>
                                <div class="premium-option market-data" onclick="selectPremiumOption(${basketId}, ${legIndex}, 'market_price')">
                                    📊 Market Price
                                </div>
                                <div class="premium-option" onclick="selectPremiumOption(${basketId}, ${legIndex}, 'limit')">
                                    🎯 Limit Order
                                </div>
                                <div class="premium-option" onclick="openDepthModal(${basketId}, ${legIndex})">
                                    📊 Market Depth
                                </div>
                                ${leg.symbol && leg.expiry && leg.strike ? '' : ''}
                            </div>
                        </div>
                    </div>
                    ${leg.premiumType ? `<div style="font-size: 11px; color: #94a3b8; margin-top: 5px;">Type: ${leg.premiumType.replace('_', ' ').toUpperCase()}</div>` : ''}
                </div>
            </div>
            
            <div id="leg-margin-${basketId}-${legIndex}" class="leg-margin-display">
                💰 <strong>
                    ${
                        leg.instrumentType === 'EQ'
                            ? `CAPITAL: ₹${(leg.premium * leg.quantity).toLocaleString()}`
                            : leg.instrumentType === 'FUT'
                                ? `MARGIN: ₹${legMargin.toLocaleString()}`
                                : `Leg Margin: ₹${legMargin.toLocaleString()}`
                    }
                </strong>
                ${
                    (leg.instrumentType === 'CE' || leg.instrumentType === 'PE')
                        ? (leg.action === 'S' ? ' (Selling Options)' : leg.action === 'B' ? ' (Premium Payment)' : '')
                        : ''
                }
            </div>

        </div>
    `;
}



window.togglePremiumVisibility = togglePremiumVisibility;
