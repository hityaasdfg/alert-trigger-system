
// Optimized version to prevent blinking and DOM loading issues

async function renderBaskets() {
    const container = document.getElementById('basketsContainer');
    
    // Create a document fragment to build DOM off-screen
    const fragment = document.createDocumentFragment();
    
    if (baskets.length === 0) {
        const emptyMessage = document.createElement('p');
        emptyMessage.style.cssText = 'text-align: center; color: #94a3b8; padding: 40px;';
        emptyMessage.textContent = 'No baskets created yet. Click "Add New Basket" to get started.';
        fragment.appendChild(emptyMessage);
    } else {
        // Pre-calculate all async data to avoid multiple renders
        const basketsData = await Promise.all(
            baskets.map(async (basket) => ({
                basket,
                marginData: await calculateBasketMargin(basket),
                legsSection: await renderLegsSection(basket),
                summarySection: await renderBasketSummary(basket)
            }))
        );
        
        // Build all DOM elements at once
        for (const { basket, marginData, legsSection, summarySection } of basketsData) {
            const basketDiv = createBasketElement(basket, marginData, legsSection, summarySection);
            fragment.appendChild(basketDiv);
        }
        
    }
    
    // Single DOM update - prevents blinking
    container.replaceChildren(fragment);
}


function createBasketElement(basket, marginData, legsSection, summarySection) {
    const basketDiv = document.createElement('div');
    basketDiv.className = 'basket-container';
    
    const requiredMargin = marginData.required || 0;
    const blockedMargin = marginData.blocked || requiredMargin;
    const strategySection = renderStrategySection(basket);
    const riskSection = renderAdvancedRiskSection(basket);
    
    basketDiv.innerHTML = `
        <div class="basket-header" data-basket-id="${basket.id}">
            <div>
                <h4>${basket.label}</h4>
                <span>Strategy: ${basket.strategy || 'Custom'} | Legs: ${basket.legs.length} | Required: ₹${requiredMargin.toLocaleString()} | Blocked: ₹${blockedMargin.toLocaleString()}</span>
            </div>
            <button class="btn btn-danger" onclick="removeBasket(${basket.id})">Remove Basket</button>
        </div>
        <div class="basket-content">
            ${strategySection}
            ${legsSection}
            ${riskSection}
        </div>
    `;
    
    return basketDiv;
}

// Alternative: Incremental update approach for better performance
async function renderBasketsIncremental() {
    const container = document.getElementById('basketsContainer');
    
    if (baskets.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #94a3b8; padding: 40px;">No baskets created yet. Click "Add New Basket" to get started.</p>';
        return;
    }
    
    // Get existing basket elements
    const existingBaskets = new Map();
    container.querySelectorAll('.basket-container').forEach(basketEl => {
        const id = basketEl.querySelector('.basket-header').dataset.basketId;
        existingBaskets.set(id, basketEl);
    });
    
    // Track which baskets we've processed
    const processedIds = new Set();
    
    for (const basket of baskets) {
        processedIds.add(basket.id.toString());
        
        if (existingBaskets.has(basket.id.toString())) {
            // Update existing basket
            await updateBasketElement(existingBaskets.get(basket.id.toString()), basket);
        } else {
            // Create new basket
            const marginData = await calculateBasketMargin(basket);
            const legsSection = await renderLegsSection(basket);
            const summarySection = await renderBasketSummary(basket);
            const basketDiv = createBasketElement(basket, marginData, legsSection, summarySection);
            container.appendChild(basketDiv);
        }
    }
    
    // Remove baskets that no longer exist
    existingBaskets.forEach((basketEl, id) => {
        if (!processedIds.has(id)) {
            basketEl.remove();
        }
    });
}

function renderUnderlyingRiskOptions(basket, selectedOption) {
    const basketId = basket.id;
    const settings = basket.riskSettings.underlying.settings;

    switch (selectedOption) {
        case 'price_based':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>Underlying TP Price</label>
                    <input type="number" value="${settings.tp || ''}" onchange="updateRiskSetting(${basketId}, 'underlying', 'tp', this.value)" step="0.01" placeholder="e.g., 22800">
                </div>
                <div class="form-group">
                    <label>Underlying SL Price</label>
                    <input type="number" value="${settings.sl || ''}" onchange="updateRiskSetting(${basketId}, 'underlying', 'sl', this.value)" step="0.01" placeholder="e.g., 22200">
                </div>
            </div>
        `;
        case 'points_based':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>Points Up from Entry</label>
                    <input type="number" value="${settings.pointsUp || ''}" onchange="updateRiskSetting(${basketId}, 'underlying', 'pointsUp', this.value)" step="0.5" placeholder="e.g., 200">
                </div>
                <div class="form-group">
                    <label>Points Down from Entry</label>
                    <input type="number" value="${settings.pointsDown || ''}" onchange="updateRiskSetting(${basketId}, 'underlying', 'pointsDown', this.value)" step="0.5" placeholder="e.g., 100">
                </div>
            </div>
        `;
        default:
            return '';
    }
}

async function updateBasketElement(basketEl, basket) {
    // Only update if necessary - check if data has changed
    const header = basketEl.querySelector('.basket-header span');
    const marginData = await calculateBasketMargin(basket);
    const requiredMargin = marginData.required || 0;
    const blockedMargin = marginData.blocked || requiredMargin;
    
    const newHeaderText = `Strategy: ${basket.strategy || 'Custom'} | Legs: ${basket.legs.length} | Required: ₹${requiredMargin.toLocaleString()} | Blocked: ₹${blockedMargin.toLocaleString()}`;
    
    if (header.textContent !== newHeaderText) {
        header.textContent = newHeaderText;
    }
    
    // Update other sections as needed
    // This is more complex but prevents unnecessary DOM manipulation
}



function getUnderlyingRiskDescription(selectedOption) {
    const descriptions = {
        'price_based': {
            title: 'Underlying Price Based Exit',
            description: 'Exit when underlying reaches specific price levels',
            examples: {
                tp: 'Exit all positions when NIFTY reaches 22,800 (target price)',
                sl: 'Exit all positions when NIFTY falls to 22,200 (stop price)'
            }
        },
        'points_based': {
            title: 'Points Movement Based',
            description: 'Exit based on points movement from current underlying price',
            examples: {
                tp: 'Exit when underlying moves 200 points up from current level',
                sl: 'Exit when underlying moves 100 points down from current level'
            }
        }
    };

    const desc = descriptions[selectedOption];
    if (!desc) return '';

    return `
    <div style="background: rgba(74, 144, 226, 0.1); padding: 15px; border-radius: 8px; margin: 15px 0;">
        <h6 style="color: #74b9ff; margin-bottom: 10px;">📖 ${desc.title}</h6>
        <p style="color: #94a3b8; font-size: 13px; margin-bottom: 10px;">${desc.description}</p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div>
                <strong style="color: #00b894;">✅ Take Profit Example:</strong>
                <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.tp}</div>
            </div>
            <div>
                <strong style="color: #ff6b6b;">🛑 Stop Loss Example:</strong>
                <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.sl}</div>
            </div>
        </div>
    </div>
`;
}

function getDrawdownRiskDescription(selectedOption) {
    const descriptions = {
        'amount_based': {
            title: 'Drawdown Amount Based',
            description: 'Exit when maximum loss from peak reaches specific amount',
            examples: {
                tp: 'Not applicable for drawdown (only protects against losses)',
                sl: 'Exit if portfolio drops ₹3,000 from its highest point'
            }
        },
        'percentage_based': {
            title: 'Drawdown Percentage Based',
            description: 'Exit when maximum loss from peak reaches specific percentage',
            examples: {
                tp: 'Not applicable for drawdown (only protects against losses)',
                sl: 'Exit if portfolio drops 10% from its highest point during the trade'
            }
        }
    };

    const desc = descriptions[selectedOption];
    if (!desc) return '';

    return `
    <div style="background: rgba(74, 144, 226, 0.1); padding: 15px; border-radius: 8px; margin: 15px 0;">
        <h6 style="color: #74b9ff; margin-bottom: 10px;">📖 ${desc.title}</h6>
        <p style="color: #94a3b8; font-size: 13px; margin-bottom: 10px;">${desc.description}</p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div style="opacity: 0.5;">
                <strong style="color: #94a3b8;">✅ Take Profit:</strong>
                <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.tp}</div>
            </div>
            <div>
                <strong style="color: #ff6b6b;">🛑 Drawdown Protection:</strong>
                <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.sl}</div>
            </div>
        </div>
    </div>
`;
}

function renderUnderlyingBasedRiskContent(basket) {
    const basketId = basket.id;
    const selectedOption = basket.riskSettings.underlying.selectedOption;

    return `
    <div class="risk-content active">
        <div class="risk-sub-sections">
            <div class="risk-sub-section">
                <h5>📈 Underlying Based Risk Management</h5>
                <div class="risk-dropdown">
                    <button type="button" class="risk-dropdown-toggle" onclick="toggleRiskDropdown(${basketId}, 'underlying')">
                        ${selectedOption ? RISK_MANAGEMENT_OPTIONS.underlying_based[selectedOption] : 'Select Risk Management Option'} ▼
                    </button>
                    <div id="risk-dropdown-${basketId}-underlying" class="risk-dropdown-content">
                        ${Object.entries(RISK_MANAGEMENT_OPTIONS.underlying_based).map(([key, value]) => 
                            `<div class="risk-dropdown-item" onclick="selectRiskOption(${basketId}, 'underlying', '${key}')">${value}</div>`
                        ).join('')}
                    </div>
                </div>
                
                ${selectedOption ? getUnderlyingRiskDescription(selectedOption) : ''}
                
                <div id="underlying-risk-options-${basketId}" class="risk-selection-container ${selectedOption ? 'show' : ''}">
                    ${renderUnderlyingRiskOptions(basket, selectedOption)}
                </div>
            </div>
        </div>
    </div>
`;
}




function getBasketRiskDescription(selectedOption) {
    const descriptions = {
        'net_pnl_tp_sl': {
            title: 'Net PnL Take Profit / Stop Loss',
            description: 'Exit entire basket when combined P&L reaches specific amount',
            examples: {
                tp: 'If basket makes ₹5,000 profit, exit all positions',
                sl: 'If basket loses ₹2,000, exit all positions'
            }
        },
        'pnl_margin_percentage': {
            title: 'PnL % on Total Margin',
            description: 'Exit based on profit/loss percentage of total margin used',
            examples: {
                tp: 'If profit is 25% of margin (₹25,000 profit on ₹1,00,000 margin), exit all',
                sl: 'If loss is 15% of margin (₹15,000 loss on ₹1,00,000 margin), exit all'
            }
        },
        'underlying_movement': {
            title: 'Underlying Movement Based',
            description: 'Exit when underlying moves specific points from entry',
            examples: {
                tp: 'If NIFTY moves 150 points up from entry (22500 → 22650), exit all',
                sl: 'If NIFTY moves 100 points down from entry (22500 → 22400), exit all'
            }
        },
        'time_based': {
            title: 'Time & VIX Based Exit',
            description: 'Exit at specific time ',
            examples: {
                tp: 'Auto-exit all positions at 3:20 PM regardless of P&L',
                sl: 'Auto-exit all positions at 3:20 PM regardless of P&L',
            }
        }
    };
    const desc = descriptions[selectedOption];
            if (!desc) return '';

            return `
            <div style="background: rgba(74, 144, 226, 0.1); padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h6 style="color: #74b9ff; margin-bottom: 10px;">📖 ${desc.title}</h6>
                <p style="color: #94a3b8; font-size: 13px; margin-bottom: 10px;">${desc.description}</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <strong style="color: #00b894;">✅ Take Profit Example:</strong>
                        <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.tp}</div>
                    </div>
                    <div>
                        <strong style="color: #ff6b6b;">🛑 Stop Loss Example:</strong>
                        <div style="color: #94a3b8; font-size: 12px; margin-top: 5px;">${desc.examples.sl}</div>
                    </div>
                </div>
            </div>
        `;
        }

function renderBasketRiskOptions(basket, selectedOption) {
    const basketId = basket.id;
    const settings = basket.riskSettings.basket.settings;

    switch (selectedOption) {
        case 'net_pnl_tp_sl':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>Net PnL Take Profit (₹)</label>
                    <input type="number" value="${settings.tp || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'tp', this.value)" placeholder="e.g., 5000" step="100">
                </div>
                <div class="form-group">
                    <label>Net PnL Stop Loss (₹)</label>
                    <input type="number" value="${settings.sl || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'sl', this.value)" placeholder="e.g., 2000" step="100">
                </div>
            </div>
        `;
        case 'pnl_margin_percentage':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>PnL % on Total Margin TP (%)</label>
                    <input type="number" value="${settings.tpMarginPct || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'tpMarginPct', this.value)" step="0.1" placeholder="e.g., 25">
                </div>
                <div class="form-group">
                    <label>PnL % on Total Margin SL (%)</label>
                    <input type="number" value="${settings.slMarginPct || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'slMarginPct', this.value)" step="0.1" placeholder="e.g., 15">
                </div>
            </div>
        `;
        case 'underlying_movement':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>Underlying Move TP (points)</label>
                    <input type="number" value="${settings.underlyingTpPoints || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'underlyingTpPoints', this.value)" step="0.5" placeholder="e.g., 150">
                </div>
                <div class="form-group">
                    <label>Underlying Move SL (points)</label>
                    <input type="number" value="${settings.underlyingSlPoints || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'underlyingSlPoints', this.value)" step="0.5" placeholder="e.g., 100">
                </div>
            </div>
        `;
        case 'time_based':
            return `
            <div class="form-row">
                <div class="form-group">
                    <label>Auto Exit Time</label>
                    <input type="datetime-local" value="${settings.autoExitTime || ''}" onchange="updateRiskSetting(${basketId}, 'basket', 'autoExitTime', this.value)">
                </div>
            </div>
        `;
        default:
            return '';
    }
}


function renderBasketWideRiskContent(basket) {
    const basketId = basket.id;
    const selectedOption = basket.riskSettings.basket.selectedOption;

    return `
    <div class="risk-content active">
        <div class="risk-sub-sections">
            <div class="risk-sub-section">
                <h5>🧺 Basket-Wide Risk Management</h5>
                <div class="risk-dropdown">
                    <button type="button" class="risk-dropdown-toggle" onclick="toggleRiskDropdown(${basketId}, 'basket')">
                        ${selectedOption ? RISK_MANAGEMENT_OPTIONS.basket_wide[selectedOption] : 'Select Risk Management Option'} ▼
                    </button>
                    <div id="risk-dropdown-${basketId}-basket" class="risk-dropdown-content">
                        ${Object.entries(RISK_MANAGEMENT_OPTIONS.basket_wide).map(([key, value]) => 
                            `<div class="risk-dropdown-item" onclick="selectRiskOption(${basketId}, 'basket', '${key}')">${value}</div>`
                        ).join('')}
                    </div>
                </div>
                
                ${selectedOption ? getBasketRiskDescription(selectedOption) : ''}
                
                <div id="basket-risk-options-${basketId}" class="risk-selection-container ${selectedOption ? 'show' : ''}">
                    ${renderBasketRiskOptions(basket, selectedOption)}
                </div>
            </div>
        </div>
    </div>
`;
}


const STRATEGY_DESCRIPTIONS = {
  long_call:             'Buy a call at desired strike (ATM or OTM).',
  short_call:            'Sell a call at higher strike (OTM).',
  long_put:              'Buy a put at desired strike (ATM or OTM).',
  short_put:             'Sell a put at lower strike (OTM).',
  bullish_credit_spread: 'Sell higher put strike, buy lower put strike.',
  bearish_credit_spread: 'Sell lower call strike, buy higher call strike.',
  bullish_debit_spread:  'Buy lower call strike, sell higher call strike.',
  bearish_debit_spread:  'Buy higher put strike, sell lower put strike.',
  covered_call:          'Buy futures, sell OTM call strike.',
  covered_put:           'Sell futures, buy OTM put strike.',
  iron_condor:           'Sell middle strikes (CE & PE), buy far OTM strikes for hedge.',
  short_strangle:        'Sell OTM call and OTM put.',
  long_collar:           'Buy futures, sell OTM put.',
  long_future:           'Buy futures at market price.',
  short_future:          'Sell futures at market price.'
};




function renderStrategySection(basket) {
    const strategyOptions = Object.keys(STRATEGIES).map(strategy =>
        `<option value="${strategy}" ${basket.strategy === strategy ? 'selected' : ''}>${strategy.replace(/_/g, ' ').toUpperCase()}</option>`
    ).join('');

    return `
    <div class="strategy-section">
        <h4 style="margin-bottom: 15px; color: #fdcb6e;">📋 Strategy Selection</h4>
        <div class="form-row">
            <div class="form-group">
                <label>Choose Strategy</label>
                <select onchange="
                    applyStrategy(${basket.id}, this.value);
                    document.getElementById('strategy-desc-${basket.id}').textContent =
                    STRATEGY_DESCRIPTIONS[this.value] || '';
                ">
                <option value="">Custom Strategy</option>
                ${strategyOptions}
                </select>
                <div id="strategy-desc-${basket.id}" style="margin-top:.5em;color:#94a3b8;font-size:.9em;">
                ${ STRATEGY_DESCRIPTIONS[basket.strategy] || '' }
                </div>
            </div>
            <div class="form-group">
                <label>Basket Label</label>
                <input type="text" value="${basket.label}" onchange="updateBasketLabel(${basket.id}, this.value)">
            </div>
        </div>
    </div>
`;

}

async function renderLegsSection(basket) {
    // Pre-calculate all leg data
    const legsData = await Promise.all(
        basket.legs.map(async (leg, index) => ({
            leg,
            index,
            html: await renderLegForm(basket, leg, index)
        }))
    );
    
    let legsHtml = `
        <h4 style="margin-bottom: 15px; color: #f1f5f9;">📊 Basket Legs</h4>
        <div id="legs-${basket.id}">
    `;
    
    legsHtml += legsData.map(data => data.html).join('');
    
    legsHtml += `
        </div>
        <button class="btn btn-secondary" onclick="addLeg(${basket.id})">+ Add Leg</button>
    `;
    
    return legsHtml;
}


function renderAdvancedRiskSection(basket) {
    const basketId = basket.id;
    const activeMode = currentRiskMode[basketId];

    return `
    <h4 style="margin-bottom: 15px; color: #f1f5f9;">Risk Management</h4>
    <div class="risk-tabs">
        <button class="risk-tab ${activeMode === 'individual' ? 'active' : ''}" onclick="switchRiskMode(${basketId}, 'individual')">Per-Leg TP/SL</button>
        <button class="risk-tab ${activeMode === 'basket' ? 'active' : ''}" onclick="switchRiskMode(${basketId}, 'basket')">Basket-Wide</button>
        <button class="risk-tab ${activeMode === 'underlying' ? 'active' : ''}" onclick="switchRiskMode(${basketId}, 'underlying')">Underlying Base</button>
    </div>
    
    ${renderRiskContent(basket, activeMode)}
`;
}

function renderRiskContent(basket, activeMode) {
    switch (activeMode) {
        case 'individual':
            return renderIndividualRiskContent(basket);
        case 'basket':
            return renderBasketWideRiskContent(basket);
        case 'underlying':
            return renderUnderlyingBasedRiskContent(basket);
        case 'drawdown':
            return renderDrawdownRiskContent(basket);
        case 'trailing':
            return renderTrailingRiskContent(basket);
        case 'advanced':
            return renderAdvancedRiskOptionsContent(basket);
        default:
            return '<div class="risk-content active"><p>Select a risk management option</p></div>';
    }
}

function renderIndividualRiskContent(basket) {
    const basketId = basket.id;
    return `
    <div class="risk-content active">
        <div class="risk-sub-sections">
            <div class="risk-sub-section">
                <h5>🎯 Per-Leg Target & Stop Loss Configuration</h5>
                <p style="color: #94a3b8; margin-bottom: 15px;">Select TP/SL type and configure values for each leg</p>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>TP/SL Type for All Legs</label>
                        <select onchange="updateTPSLType(${basketId}, this.value); renderBaskets();">
                            <option value="percentage" ${basket.riskSettings.individual.defaultTpType === 'percentage' ? 'selected' : ''}>Percentage (%)</option>
                            <option value="points" ${basket.riskSettings.individual.defaultTpType === 'points' ? 'selected' : ''}>Absolute Points</option>
                            <option value="premium" ${basket.riskSettings.individual.defaultTpType === 'premium' ? 'selected' : ''}> Price (₹)</option>
                            <option value="pnl_amount" ${basket.riskSettings.individual.defaultTpType === 'pnl_amount' ? 'selected' : ''}>PnL Amount (₹)</option>
                            <option value="pnl_margin" ${basket.riskSettings.individual.defaultTpType === 'pnl_margin' ? 'selected' : ''}>PnL % on Margin</option>
                        </select>
                    </div>
                </div>

                <div style="background: rgba(74, 144, 226, 0.1); padding: 15px; border-radius: 8px; margin-top: 15px;">
                    <h6 style="color: #74b9ff; margin-bottom: 10px;">📖 Selected Type: ${getTpSlTypeDescription(basket.riskSettings.individual.defaultTpType || 'percentage')}</h6>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <strong style="color: #00b894;">Take Profit Example:</strong>
                            <div style="color: #94a3b8; font-size: 13px; margin-top: 5px;">
                                ${getTpSlExample(basket.riskSettings.individual.defaultTpType || 'percentage', 25, 'TP')}
                            </div>
                        </div>
                        <div>
                            <strong style="color: #ff6b6b;">Stop Loss Example:</strong>
                            <div style="color: #94a3b8; font-size: 13px; margin-top: 5px;">
                                ${getTpSlExample(basket.riskSettings.individual.defaultTpType || 'percentage', 15, 'SL')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
`;
}

async function renderBasketSummary(basket) {
    const totalLegs = basket.legs.length;
    const buyLegs = basket.legs.filter(leg => leg.action === 'B').length;
    const sellLegs = basket.legs.filter(leg => leg.action === 'S').length;

    const marginData = await calculateBasketMargin(basket);
    const totalMargin = marginData.required || 0;
    const blockedMargin = marginData.blocked || totalMargin;
    
    const marginBreakdown = {};
    let sumOfIndividualMargins = 0;
    
    for (const leg of basket.legs) {
        if (isLegDataComplete(leg)) {
            const legMargin = await calculateLegMargin(leg);
            sumOfIndividualMargins += legMargin;
            
            const type = leg.instrumentType;
            if (type) {
                marginBreakdown[type] = (marginBreakdown[type] || 0) + legMargin;
            }
        }
    }

    const marginSavings = sumOfIndividualMargins - totalMargin;
    const savingsPercentage = sumOfIndividualMargins > 0 ? 
        ((marginSavings / sumOfIndividualMargins) * 100).toFixed(1) : 0;

    let marginBreakdownHtml = '';
    Object.entries(marginBreakdown).forEach(([type, margin]) => {
        marginBreakdownHtml += `
            <div class="margin-item">
                <span>${type} Individual Margin:</span>
                <span>₹${margin.toLocaleString()}</span>
            </div>
        `;
    });

    return `
        <div class="basket-summary">
            <h4 style="margin-bottom: 15px; color: #00b894;">📋 Basket Summary</h4>
            <div class="summary-item">
                <span>Total Legs:</span>
                <span>${totalLegs}</span>
            </div>
            <div class="summary-item">
                <span>Buy Legs:</span>
                <span>${buyLegs}</span>
            </div>
            <div class="summary-item">
                <span>Sell Legs:</span>
                <span>${sellLegs}</span>
            </div>
            <div class="summary-item">  
                <span>Strategy:</span>
                <span>${basket.strategy || 'Custom'}</span>
            </div>
            <div class="summary-item">  
                <span>Risk Mode:</span>
                <span>${currentRiskMode[basket.id].replace('_', ' ').toUpperCase()}</span>
            </div>
            
            <div class="margin-info">
                <h5 style="color: #ffd700; margin-bottom: 10px;">💰 Margin Analysis</h5>
                
                ${sumOfIndividualMargins > 0 ? `
                    <div class="margin-item" style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px; margin-top: 8px;">
                        <span>Sum of Individual Margins:</span>
                        <span style="color: #94a3b8;">₹${sumOfIndividualMargins.toLocaleString()}</span>
                    </div>
                ` : ''}
                
                <div class="margin-item margin-total">
                    <span>📊 Required Margin:</span>
                    <span style="color: #00b894; font-weight: bold;">₹${totalMargin.toLocaleString()}</span>
                </div>
                
                <div class="margin-item margin-total">
                    <span>🔒 Blocked Margin:</span>
                    <span style="color: #667eea; font-weight: bold;">₹${blockedMargin.toLocaleString()}</span>
                </div>
            </div>
        </div>
    `;
}



async function switchRiskMode(basketId, mode) {
    currentRiskMode[basketId] = mode;
    const basket = baskets.find(b => b.id === basketId);
    if (basket) {
        basket.riskMode = mode;
    }
    await renderBaskets();
    showNotification(`Switched to ${mode.replace('_', ' ').toUpperCase()} risk mode!`, 'info');
}

function updateRiskSetting(basketId, riskType, field, value) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;

    if (!basket.riskSettings[riskType]) {
        basket.riskSettings[riskType] = {};
    }
    if (!basket.riskSettings[riskType].settings) {
        basket.riskSettings[riskType].settings = {};
    }

    basket.riskSettings[riskType].settings[field] = value;
}

function toggleRiskDropdown(basketId, riskType) {
    const dropdownId = `risk-dropdown-${basketId}-${riskType}`;
    const dropdown = document.getElementById(dropdownId);

    document.querySelectorAll('.risk-dropdown-content').forEach(d => {
        if (d.id !== dropdownId) {
            d.classList.remove('show');
        }
    });

    dropdown.classList.toggle('show');
}

async function selectRiskOption(basketId, riskType, option) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;

    basket.riskSettings[riskType].selectedOption = option;

    const dropdownId = `risk-dropdown-${basketId}-${riskType}`;
    document.getElementById(dropdownId).classList.remove('show');

    await renderBaskets();
    showNotification(`Risk management option updated: ${option.replace('_', ' ').toUpperCase()}`, 'success');
}

function updateTPSLType(basketId, tpslType) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;

    basket.riskSettings.individual.defaultTpType = tpslType;
    basket.riskSettings.individual.defaultSlType = tpslType;

    basket.legs.forEach(leg => {
        leg.sl = '';
        leg.tp = '';
    });

    showNotification(`TP/SL type changed to: ${getTpSlTypeDescription(tpslType)}`, 'success');
}


// Debounced render function to prevent excessive re-renders
let renderTimeout;
function debouncedRenderBaskets(delay = 100) {
    clearTimeout(renderTimeout);
    renderTimeout = setTimeout(() => {
        renderBaskets();
    }, delay);
}

// CSS to prevent layout shifts during updates
const preventBlinkingCSS = `
    .basket-container {
        transition: none !important;
        min-height: 200px; /* Prevent collapse during updates */
    }
    
    .basket-content {
        opacity: 1;
        transition: opacity 0.1s ease;
    }
    
    .basket-content.updating {
        opacity: 0.7;
    }
    
    #basketsContainer {
        contain: layout; /* Prevent layout thrashing */
    }
`;

// Add CSS to prevent blinking
function addBlinkPreventionCSS() {
    const style = document.createElement('style');
    style.textContent = preventBlinkingCSS;
    document.head.appendChild(style);
}

// Call this once when your app initializes
addBlinkPreventionCSS();