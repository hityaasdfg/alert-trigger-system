async function addNewBasket() {
    const basketId = basketIdCounter++;
    const basket = {
        id: basketId,
        label: `Basket ${basketId}`,
        strategy: '',
        legs: [],
        riskMode: 'individual',
        riskSettings: {
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
        }
    };

    baskets.push(basket);
    currentRiskMode[basketId] = 'individual';
    clearAllMarginCache();
    await renderBaskets();
    showNotification(`Basket ${basketId} created successfully!`, 'success');
}

async function removeBasket(basketId) {
    baskets = baskets.filter(b => b.id !== basketId);
    delete currentRiskMode[basketId];
    clearAllMarginCache();
    await renderBaskets();
    showNotification('Basket removed successfully!', 'info');
}

function updateBasketLabel(basketId, label) {
    const basket = baskets.find(b => b.id === basketId);
    if (basket) {
        basket.label = label;
        showNotification('Basket label updated!', 'info');
    }
}

async function applyStrategy(basketId, strategy) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !strategy) return;

    basket.strategy = strategy;
    basket.legs = [];

    const strategyLegs = STRATEGIES[strategy];
    strategyLegs.forEach(([action, instrumentType]) => {
        basket.legs.push({
            action: action,
            instrumentType: instrumentType,
            symbol: '',
            strike: '',
            expiry: '',
            quantity: '',
            price: '',
            premium: '',
            premiumType: '',
            sl: '',
            tp: ''
        });
    });

    await renderBaskets();
    showNotification(`${strategy.replace(/_/g, ' ').toUpperCase()} strategy applied!`, 'success');
}

async function addLeg(basketId) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;

    basket.legs.push({
        action: 'B',
        instrumentType: '',
        symbol: '',
        strike: '',
        expiry: '',
        quantity: '',
        price: '',
        premium: '',
        premiumType: '',
        sl: '',
        tp: ''
    });

    await renderBaskets();
    showNotification('New leg added!', 'success');
}

async function removeLeg(basketId, legIndex) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;

    basket.legs.splice(legIndex, 1);
    await renderBaskets();
    showNotification('Leg removed!', 'info');
}

function updateLeg(basketId, legIndex, field, value) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !basket.legs[legIndex]) return;
    
    const leg = basket.legs[legIndex];
    
    if (field === 'quantity') {
        leg.rawQuantity = value;
        
        if (leg.lotSize && !isNaN(parseInt(value))) {
            const lotMultiplier = parseInt(value) || 0;
            const lotSize = parseInt(leg.lotSize) || 1;
            const actualQuantity = lotMultiplier * lotSize;
            
            leg[field] = actualQuantity.toString();
        } else {
            leg[field] = value;
        }
    } else {
        leg[field] = value;
    }
    
    if (['action', 'instrumentType', 'quantity', 'price', 'premium'].includes(field)) {
        clearMarginCache(basketId, legIndex);
    }
}

async function onSymbolChange(basketId, legIndex, symbol) {
    updateLeg(basketId, legIndex, 'symbol', symbol);

    if (symbol) {
        const expiryData = await loadExpiries(symbol);
        const defaultExpiry = expiryData?.expiries?.[0] || null;

        if (defaultExpiry) {
            updateLeg(basketId, legIndex, 'expiry', defaultExpiry);
            await loadStrikes(symbol, defaultExpiry);
        }

        await renderBaskets();
        showNotification(`Market data loaded for ${symbol}`, 'info');
    }
}

async function onExpiryChange(basketId, legIndex, expiry) {
    updateLeg(basketId, legIndex, 'expiry', expiry);

    const leg = baskets.find(b => b.id === basketId)?.legs[legIndex];
    
    if (leg?.symbol && expiry && leg.instrument_type) {
        await loadStrikes(leg.symbol, expiry, leg.instrument_type);
    }

    await renderBaskets();
}

window.addNewBasket = addNewBasket;
window.removeBasket = removeBasket;
window.updateBasketLabel = updateBasketLabel;
window.applyStrategy = applyStrategy;
window.addLeg = addLeg;
window.removeLeg = removeLeg;
window.updateLeg = updateLeg;
window.onSymbolChange = onSymbolChange;
window.onExpiryChange = onExpiryChange;