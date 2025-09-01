let marginCache = {};
let marginCalculationInProgress = {};

function getMarginCacheKey(leg) {
    return `${leg.action}_${leg.instrumentType}_${leg.symbol}_${leg.strike || 'N/A'}_${leg.expiry || 'N/A'}_${leg.quantity}_${leg.price || 'N/A'}_${leg.premium || 'N/A'}`;
}

async function calculateLegMargin(leg) {
    if (!isLegDataComplete(leg)) {
        return 0;
    }

    const cacheKey = getMarginCacheKey(leg);
    if (marginCache[cacheKey] !== undefined) {
        return marginCache[cacheKey];
    }

    try {
        const apiPayload = {
            legs: [{
                action: leg.action,
                instrument_type: leg.instrumentType,  // CE, PE, FUT, EQ
                symbol: leg.symbol,
                quantity: parseInt(leg.quantity) || 0,
                expiry: leg.expiry || null,
                strike: leg.strike ? parseFloat(leg.strike) : null,
                price: leg.price ? parseFloat(leg.price) : null,
                premium: leg.premium ? parseFloat(leg.premium) : null
            }]
        };

        console.log(`📡 Fetching leg margin from API:`, apiPayload);

        const response = await fetch('http://192.168.4.221:9000/api/get-basket-margin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(apiPayload)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        const legMargin = data.legs?.[0]?.total || data.required_margin || 0;
        marginCache[cacheKey] = legMargin;

        console.log(`✅ Leg margin (${leg.symbol} ${leg.instrumentType}): ₹${legMargin.toLocaleString()}`);

        return legMargin;

    } catch (err) {
        console.error('❌ Error fetching leg margin from API:', err);
        marginCache[cacheKey] = 0;
        return 0;
    }
}

async function calculateBasketMargin(basket) {
    if (!basket.legs || basket.legs.length === 0) {
        return { required: 0, blocked: 0 };
    }
    
    const validLegs = basket.legs.filter(leg => isLegDataComplete(leg));
    
    if (validLegs.length === 0) {
        return { required: 0, blocked: 0 };
    }
    
    const basketCacheKey = `basket_${basket.id}_${validLegs.map(leg => getMarginCacheKey(leg)).join('|')}`;
    
    if (marginCache[basketCacheKey] !== undefined) {
        return marginCache[basketCacheKey];
    }
    
    if (marginCalculationInProgress[basketCacheKey]) {
        return { required: 0, blocked: 0 };
    }
    
    marginCalculationInProgress[basketCacheKey] = true;
    
    try {
        const apiLegsData = validLegs.map(leg => ({
            action: leg.action,
            instrument_type: leg.instrumentType,
            symbol: leg.symbol,
            quantity: parseInt(leg.quantity) || 0,
            expiry: leg.expiry || null,
            strike: leg.strike ? parseFloat(leg.strike) : null,
            price: leg.price ? parseFloat(leg.price) : null,
            premium: leg.premium ? parseFloat(leg.premium) : null
        }));
        
        console.log(`🚀 Calling basket margin API with ${apiLegsData.length} legs:`, apiLegsData);
        
        const response = await fetch('http://192.168.4.221:9000/api/get-basket-margin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                legs: apiLegsData
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        const requiredMargin = data.required_margin || 0;
        const blockedMargin = data.blocked_margin || requiredMargin;
        
        const marginData = { required: requiredMargin, blocked: blockedMargin };
        marginCache[basketCacheKey] = marginData;
        
        console.log(`✅ Basket margin calculated (with offsetting): ₹${requiredMargin.toLocaleString()} (blocked: ₹${blockedMargin.toLocaleString()})`);
        
        if (data.legs && Array.isArray(data.legs)) {
            data.legs.forEach((legMarginData, index) => {
                if (validLegs[index]) {
                    const legCacheKey = getMarginCacheKey(validLegs[index]);
                    const legMargin = legMarginData.total || legMarginData.required || 0;
                    marginCache[legCacheKey] = legMargin;
                    console.log(`  Leg ${index + 1} (${validLegs[index].symbol} ${validLegs[index].instrumentType}): ₹${legMargin.toLocaleString()}`);
                }
            });
        }
        
        return marginData;
        
    } catch (error) {
        console.error('❌ Error calculating basket margin via API:', error);
        
        console.warn('⚠️ Falling back to sum of individual leg margins (no offsetting)');
        let total = 0;
        
        for (const leg of validLegs) {
            const legMargin = await calculateLegMargin(leg);
            total += legMargin;
        }
        
        const fallbackData = { required: total, blocked: total };
        marginCache[basketCacheKey] = fallbackData;
        
        return fallbackData;
        
    } finally {
        delete marginCalculationInProgress[basketCacheKey];
    }
}

function isLegDataComplete(leg) {
    if (!leg.action || !leg.instrumentType || !leg.symbol || !leg.quantity) {
        return false;
    }
    
    if (leg.instrumentType === 'EQ') {
        return true;
    }
    
    if (!leg.expiry) {
        return false;
    }
    
    if ((leg.instrumentType === 'CE' || leg.instrumentType === 'PE')) {
        if (!leg.strike) {
            return false;
        }
        if (!leg.premium && leg.action === 'B') {
            console.warn(`Premium missing for BUY ${leg.instrumentType} ${leg.symbol} ${leg.strike} - margin may be inaccurate`);
        }
    }
    
    return true;
}

function clearMarginCache(basketId, legIndex) {
    const basket = baskets.find(b => b.id === basketId);
    if (basket && basket.legs[legIndex]) {
        const leg = basket.legs[legIndex];
        const legCacheKey = getMarginCacheKey(leg);
        delete marginCache[legCacheKey];
        
        const basketCachePattern = `basket_${basketId}_`;
        Object.keys(marginCache).forEach(key => {
            if (key.startsWith(basketCachePattern)) {
                delete marginCache[key];
            }
        });
        
        console.log(`Cleared margin cache for leg and basket: ${leg.symbol} ${leg.instrumentType}`);
    }
}

function clearAllMarginCache() {
    const cacheSize = Object.keys(marginCache).length;
    marginCache = {};
    marginCalculationInProgress = {};
    console.log(`Cleared ${cacheSize} margin cache entries`);
}

async function updateBasketMarginDisplay(basketId) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket) return;
    
    try {
        const marginData = await calculateBasketMargin(basket);
        console.log(`Updating margin display for basket ${basketId}:`, marginData);
        const requiredMargin = marginData.required || 0;
        const blockedMargin = marginData.blocked || requiredMargin;
        
        const basketHeader = document.querySelector(`[data-basket-id="${basketId}"] .basket-header span`);
        if (basketHeader) {
            basketHeader.textContent = `Strategy: ${basket.strategy || 'Custom'} | Legs: ${basket.legs.length} | Required: ₹${requiredMargin.toLocaleString()} | Blocked: ₹${blockedMargin.toLocaleString()}`;
        }
        
        for (let i = 0; i < basket.legs.length; i++) {
            await updateLegMarginDisplay(basketId, i);
        }
        
    } catch (error) {
        console.error('Error updating basket margin display:', error);
    }
}

async function updateLegMarginDisplay(basketId, legIndex) {
    const basket = baskets.find(b => b.id === basketId);
    if (!basket || !basket.legs[legIndex]) return;
    
    try {
        const leg = basket.legs[legIndex];
        const legMargin = await calculateLegMargin(leg);
        
        const marginDisplay = document.getElementById(`leg-margin-${basketId}-${legIndex}`);
        if (marginDisplay) {
            marginDisplay.innerHTML = `
                💰 <strong>Leg Margin: ₹${legMargin.toLocaleString()}</strong>
                ${leg.action === 'S' && (leg.instrumentType === 'CE' || leg.instrumentType === 'PE') ? ' (Selling Options)' : ''}
                ${leg.action === 'B' && (leg.instrumentType === 'CE' || leg.instrumentType === 'PE') ? ' (Premium Payment)' : ''}
                ${legMargin === 0 && isLegDataComplete(leg) ? ' <span style="color: #ff6b6b;">(Calculation Failed)</span>' : ''}
            `;
        }
    } catch (error) {
        console.error('Error updating leg margin display:', error);
    }
}

const debouncedMarginUpdate = debounce(async (basketId) => {
    try {
        await updateBasketMarginDisplay(basketId);
    } catch (error) {
        console.error('Error in debounced margin update:', error);
        showNotification('Error updating margin calculations', 'error');
    }
}, 800);

window.debouncedMarginUpdate = debouncedMarginUpdate;
