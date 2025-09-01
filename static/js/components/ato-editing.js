function ensureRiskSettingsStructure(riskSettings) {
    const defaultRiskSettings = {
        individual: {
            defaultTpType: 'percentage',
            defaultSlType: 'percentage'
        },
        basket: {
            selectedOption: '',
            settings: {}
        },
        underlying: {
            selectedOption: '',
            settings: {}
        },
        drawdown: {
            selectedOption: '',
            settings: {}
        },
        trailing: {
            selectedOption: '',
            settings: {}
        },
        advanced: {
            selectedOption: '',
            settings: {}
        }
    };

    if (!riskSettings) {
        return defaultRiskSettings;
    }

    const sections = ['individual', 'basket', 'underlying', 'drawdown', 'trailing', 'advanced'];
    
    for (const section of sections) {
        if (!riskSettings[section]) {
            riskSettings[section] = defaultRiskSettings[section];
            continue;
        }
        
        if (section === 'individual') {
            if (!riskSettings.individual.defaultTpType) {
                riskSettings.individual.defaultTpType = 'percentage';
            }
            if (!riskSettings.individual.defaultSlType) {
                riskSettings.individual.defaultSlType = 'percentage';
            }
            continue;
        }
        
        if (!riskSettings[section].selectedOption) {
            riskSettings[section].selectedOption = '';
        }
        
        if (!riskSettings[section].settings) {
            riskSettings[section].settings = {};
        }
    }
    
    return riskSettings;
}

async function editATO(atoId) {
    try {
        console.log(`Starting to edit ATO: ${atoId}`);
        
        const result = await apiCall(`/alerts/${atoId}`);
        const ato = result.alert;

        if (!ato) {
            showNotification('ATO not found', 'error');
            return;
        }

        if (ato.status !== 'waiting') {
            showNotification('Only ATOs in waiting status can be edited', 'error');
            return;
        }

        console.log('ATO data loaded:', ato);

        const underlyingInput = document.getElementById('underlying');
        const operatorSelect = document.getElementById('operator');
        const triggerPriceInput = document.getElementById('triggerPrice');
        const validTillInput = document.getElementById('validTill');
        
        if (!underlyingInput || !operatorSelect || !triggerPriceInput || !validTillInput) {
            console.error('Required form elements not found in DOM');
            showNotification('Error: Form elements not found', 'error');
            return;
        }
        
        underlyingInput.value = ato.symbol;
        operatorSelect.value = ato.operator;
        triggerPriceInput.value = ato.threshold;
        
        try {
            const dt = new Date(ato.valid_till);
            // shift into local so toISOString() emits your local Y-M-DThh:mm
            dt.setMinutes(dt.getMinutes() - dt.getTimezoneOffset());
            validTillInput.value = dt.toISOString().slice(0, 16);
            } catch (dateError) {
            console.error('Error formatting date:', dateError);
            validTillInput.value = '';
        }
        
        fetchAndDisplayLTP(ato.symbol);

        baskets = [];
        basketIdCounter = 1;
        currentRiskMode = {};

        ato.baskets.forEach(basket => {
            const newBasketId = basketIdCounter++;
            
            let riskSettings = basket.risk_settings;
            riskSettings = ensureRiskSettingsStructure(riskSettings);
            
            console.log(`Basket ${newBasketId} risk settings:`, riskSettings);
            
            const newBasket = {
                id: newBasketId,
                label: basket.label || `Basket ${newBasketId}`,
                strategy: basket.strategy || '',
                legs: basket.legs.map(leg => ({
                    action: leg.action,
                    instrumentType: leg.instrument_type,
                    symbol: leg.symbol,
                    strike: leg.strike || '',
                    expiry: leg.expiry ? (() => {
                        const expiryDate = new Date(leg.expiry);
                        if (isNaN(expiryDate.getTime())) {
                            console.error('Invalid expiry date:', leg.expiry);
                            return '';
                        }
                        const year = expiryDate.getFullYear();
                        const month = String(expiryDate.getMonth() + 1).padStart(2, '0');
                        const day = String(expiryDate.getDate()).padStart(2, '0');
                        return `${year}-${month}-${day}`;
                    })() : '',

                    quantity: leg.quantity || '',
                    rawQuantity: leg.quantity ? (leg.lot_size ? leg.quantity / leg.lot_size : leg.quantity) : '',
                    lotSize: leg.lot_size || '',
                    price: leg.price || '',
                    premium: leg.premium || '',
                    premiumType: leg.premium_type || '',
                    sl: leg.sl || '',
                    tp: leg.tp || ''
                })),
                riskMode: basket.risk_mode || 'individual',
                riskSettings: riskSettings
            };
            
            baskets.push(newBasket);
            currentRiskMode[newBasketId] = newBasket.riskMode;
        });

        window.editingAtoId = atoId;
        
        showMainTab('builder');
        
        const builderTabButton = document.querySelector('.main-tab[onclick*="showMainTab(\'builder\'"]');
        if (builderTabButton) {
            document.querySelectorAll('.main-tab').forEach(tab => tab.classList.remove('active'));
            builderTabButton.classList.add('active');
        }
        
        const builderTab = document.getElementById('builder');
        if (!builderTab) {
            console.error('Builder tab element not found');
            showNotification('Error: Builder tab not found', 'error');
            return;
        }
        
        const existingIndicator = document.querySelector('.editing-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
        
        const editIndicator = document.createElement('div');
        editIndicator.className = 'editing-indicator';
        editIndicator.style.backgroundColor = 'rgba(116, 185, 255, 0.2)';
        editIndicator.style.borderLeft = '4px solid #74b9ff';
        editIndicator.style.padding = '15px';
        editIndicator.style.marginBottom = '20px';
        editIndicator.style.borderRadius = '8px';
        editIndicator.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #74b9ff;">🔄 Editing ATO #${atoId.toString().slice(-6)}</h4>
                    <p style="margin: 5px 0 0 0; color: #94a3b8;">
                        Make your changes and click "Update ATO" when finished.
                    </p>
                </div>
                <div>
                    <button class="btn btn-secondary btn-sm" onclick="cancelEditing()">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        builderTab.insertBefore(editIndicator, builderTab.firstChild);
        
        const createButton = document.querySelector('.create-ato-btn');
        if (createButton) {
            createButton.textContent = ' UPDATE ATO ALERT';
            createButton.classList.add('update-mode');
            createButton.onclick = updateExistingATO;
        } else {
            console.error('Create ATO button not found');
        }
        
        await renderBaskets();
        
        for (const basket of baskets) {
            for (let i = 0; i < basket.legs.length; i++) {
                const leg = basket.legs[i];
                
                if (leg.symbol) {
                    if (leg.expiry) {
                        const expiryInput = document.getElementById(`expiry-${basket.id}-${i}`);
                        if (expiryInput) expiryInput.value = leg.expiry;
                        
                        if (leg.strike) {
                            const strikeInput = document.getElementById(`strike-${basket.id}-${i}`);
                            if (strikeInput) strikeInput.value = leg.strike;
                        }
                    }
                    
                    try {
                        fetchSymbolLTP(basket.id, i, leg.symbol);
                    } catch (ltpError) {
                        console.warn(`Error fetching LTP for ${leg.symbol}:`, ltpError);
                    }
                }
            }
        }
        
        showNotification(`ATO #${atoId.toString().slice(-6)} loaded for editing`, 'success');
        
    } catch (error) {
        console.error('Error editing ATO:', error);
        showNotification(`Error editing ATO: ${error.message}`, 'error');
    }
}

function cancelEditing() {
    window.editingAtoId = null;
    
    const indicator = document.querySelector('.editing-indicator');
    if (indicator) indicator.remove();
    
    const createButton = document.querySelector('.create-ato-btn');
    if (createButton) {
        createButton.textContent = ' CREATE ATO ALERT';
        createButton.classList.remove('update-mode');
        createButton.onclick = createATOWithProperMargins;
    } else {
        console.warn('Create button not found when canceling edit mode');
    }
    
    resetForm();
    
    showNotification('ATO editing cancelled', 'info');
}

async function updateExistingATO() {
    try {
        console.log("Starting updateExistingATO function");
        
        if (!window.editingAtoId) {
            showNotification('No ATO is being edited', 'error');
            return;
        }
        
        showNotification('Updating ATO...', 'info');
        
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

        console.log("Calculating total ATO margin with proper offsetting...");
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
                price: leg.instrumentType === 'EQ' ? parseFloat(leg.price) || null : null,
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

        console.log("Calculating margin via API...");
        
        let marginData;
        try {
            const marginResponse = await fetch('http://192.168.4.221:9000/api/get-basket-margin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    legs: allLegsFromAllBaskets
                })
            });

            if (!marginResponse.ok) {
                throw new Error(`HTTP ${marginResponse.status}`);
            }

            marginData = await marginResponse.json();

            if (marginData.error) {
                throw new Error(marginData.error);
            }
        } catch (marginError) {
            console.error("Error calculating margin:", marginError);
            showNotification(`Error calculating margin: ${marginError.message}`, 'error');
            return;
        }

        const totalATOMargin = marginData.required_margin || 0;
        const totalBlockedMargin = marginData.blocked_margin || 0;

        console.log(`Total ATO margin calculated: ₹${totalATOMargin.toLocaleString()}`);

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
            updated_at: new Date().toISOString(),
            total_baskets: basketsWithData.length,
            total_legs: allLegsFromAllBaskets.length,
            margin_calculation_method: 'API with cross-basket offsetting'
        };

        console.log("Sending updated ATO data to API...");
        
        try {
            const result = await apiCall(`/alerts/${window.editingAtoId}`, 'PUT', atoData);
            console.log("ATO Updated Successfully:", result);
            showNotification('🔄 ATO Updated Successfully!', 'success');
        } catch (updateError) {
            console.error("Error updating ATO:", updateError);
            showNotification(`Error updating ATO: ${updateError.message}`, 'error');
            return;
        }

        window.editingAtoId = null;
        
        const createButton = document.querySelector('.create-ato-btn');
        if (createButton) {
            createButton.textContent = ' CREATE ATO ALERT';
            createButton.classList.remove('update-mode');
            createButton.onclick = createATOWithProperMargins;
        } else {
            console.warn('Create button not found when resetting after update');
        }
        
        const indicator = document.querySelector('.editing-indicator');
        if (indicator) indicator.remove();

        resetForm();
        await loadActiveATOs();
        
        showMainTab('active');
        
        const activeTabButton = document.querySelector('.main-tab[onclick*="showMainTab(\'active\'"]');
        if (activeTabButton) {
            document.querySelectorAll('.main-tab').forEach(tab => {
                if (tab && tab.classList) {
                    tab.classList.remove('active');
                }
            });
            activeTabButton.classList.add('active');
        } else {
            console.warn('Active tab button not found');
        }

    } catch (error) {
        console.error('❌ Error updating ATO:', error);
        showNotification(`Error updating ATO: ${error.message}`, 'error');
    }
}

function addEditingStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .editing-indicator {
            background-color: rgba(116, 185, 255, 0.2);
            border-left: 4px solid #74b9ff;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            animation: fadeIn 0.5s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .create-ato-btn.update-mode {
            background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            animation: updatePulse 2s infinite;
        }
        
        @keyframes updatePulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(116, 185, 255, 0.7); }
            50% { transform: scale(1.02); box-shadow: 0 0 0 10px rgba(116, 185, 255, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(116, 185, 255, 0); }
        }
    `;
    
    document.head.appendChild(styleElement);
    console.log('Edit ATO styles added');
}

function enhanceAppWithEditingCapabilities() {
    addEditingStyles();
    window.editingAtoId = null;
    window.editATO = editATO;
    window.cancelEditing = cancelEditing;
    window.updateExistingATO = updateExistingATO;
    console.log('✅ Edit ATO functionality initialized');
}

