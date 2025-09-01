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

function getTpSlLabel(type, tpOrSl) {
    const prefix = tpOrSl === 'TP' ? 'Take Profit' : 'Stop Loss';
    switch (type) {
        case 'percentage':
            return `${prefix} (%)`;
        case 'points':
            return `${prefix} (Points)`;
        case 'premium':
            return `${prefix} Premium (₹)`;
        case 'pnl_amount':
            return `${prefix} PnL (₹)`;
        case 'pnl_margin':
            return `${prefix} Margin (%)`;
        default:
            return `${prefix}`;
    }
}

function getTpSlStep(type) {
    switch (type) {
        case 'percentage':
            return '0.1';
        case 'points':
            return '0.25';
        case 'premium':
            return '0.05';
        case 'pnl_amount':
            return '10';
        case 'pnl_margin':
            return '0.1';
        default:
            return '0.1';
    }
}

function getTpSlPlaceholder(type, tpOrSl) {
    const isTP = tpOrSl === 'TP';
    switch (type) {
        case 'percentage':
            return isTP ? 'e.g., 50' : 'e.g., 30';
        case 'points':
            return isTP ? 'e.g., 25' : 'e.g., 15';
        case 'premium':
            return isTP ? 'e.g., 120' : 'e.g., 50';
        case 'pnl_amount':
            return isTP ? 'e.g., 3000' : 'e.g., 1500';
        case 'pnl_margin':
            return isTP ? 'e.g., 20' : 'e.g., 10';
        default:
            return '';
    }
}

function getTpSlExample(type, value, tpOrSl) {
    if (!value) return 'Enter a value above to see example';

    const isTP = tpOrSl === 'TP';
    const action = isTP ? 'profit' : 'loss';

    switch (type) {
        case 'percentage':
            return `If bought at ₹100, ${isTP ? 'exit at' : 'exit at'} ₹${isTP ? (100 * (1 + value/100)).toFixed(2) : (100 * (1 - value/100)).toFixed(2)} (${isTP ? '+' : '-'}${value}%)`;
        case 'points':
            return `If bought at ₹100, ${isTP ? 'exit at' : 'exit at'} ₹${isTP ? (100 + parseFloat(value)) : (100 - parseFloat(value))} (${isTP ? '+' : '-'}${value} points)`;
        case 'premium':
            return `Exit when price ${isTP ? 'reaches' : 'drops to'} ₹${value}`;
        case 'pnl_amount':
            return `Exit when leg ${action} ${isTP ? 'reaches' : 'hits'} ₹${value}`;
        case 'pnl_margin':
            return `Exit when ${action} is ${value}% of margin used for this leg`;
        default:
            return 'Configure your target/stop loss values';
    }
}

function getTpSlTypeDescription(type) {
    switch (type) {
        case 'percentage':
            return 'Percentage (%) - Exit when profit/loss reaches X% of entry price';
        case 'points':
            return 'Absolute Points - Exit when price moves X points from entry';
        case 'premium':
            return 'Price (₹) - Exit when price reaches specific price';
        case 'pnl_amount':
            return 'PnL Amount (₹) - Exit when profit/loss reaches specific amount';
        case 'pnl_margin':
            return 'PnL % on Margin - Exit when profit/loss is X% of margin used';
        default:
            return 'Percentage based exit';
    }
}

window.switchRiskMode = switchRiskMode;
window.updateRiskSetting = updateRiskSetting;
window.updateTPSLType = updateTPSLType;
window.toggleRiskDropdown = toggleRiskDropdown;
window.selectRiskOption = selectRiskOption;