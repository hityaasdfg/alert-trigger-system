async function initializeApp() {
    // Prefill “Valid Till” to today at 15:30 local time
    window.ATO_USER_KEY = new URLSearchParams(window.location.search).get('key');
    // alert(window.ATO_USER_KEY)
    const validTillInput = document.getElementById('validTill');
    if (validTillInput) {
        const dt = dateTimeHandler.getDefaultATOValidTill('NSE');
        // force 15:30:00 local
        dt.setHours(15, 30, 0, 0);
        // shift so toISOString() uses local time instead of UTC
        dt.setMinutes(dt.getMinutes() - dt.getTimezoneOffset());
        // use defaultValue so it shows as the initial picker value
        validTillInput.defaultValue = dt.toISOString().slice(0, 16);
    }

    addCustomStyles();

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.premium-dropdown') &&
            !event.target.closest('.risk-dropdown') &&
            !event.target.closest('.search-container')) {
            document.querySelectorAll('.premium-dropdown-content, .risk-dropdown-content, .search-dropdown')
                   .forEach(dropdown => dropdown.classList.remove('show'));
        }
    });

    window.onclick = function(event) {
        const modal = document.getElementById('depthModal');
        if (event.target === modal) {
            closeDepthModal();
        }
    };

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.search-dropdown, .premium-dropdown-content, .risk-dropdown-content')
                   .forEach(dropdown => dropdown.classList.remove('show'));
        }
    });

    await Promise.all([
        loadSymbols(),
        loadActiveATOs()
    ]);

    const underlyingSelect = document.getElementById("underlying");
    let underlyingOptions = '<option value="">Select Underlying</option>';

    if (symbolsData.indices) {
        symbolsData.indices.forEach(symbol => {
            underlyingOptions += `<option value="${symbol.symbol}">${symbol.symbol} - ${symbol.name}</option>`;
        });
    }
    if (symbolsData.stocks) {
        symbolsData.stocks.forEach(symbol => {
            underlyingOptions += `<option value="${symbol.symbol}">${symbol.symbol} - ${symbol.name}</option>`;
        });
    }
    underlyingSelect.innerHTML = underlyingOptions;

    enhanceAppWithEditingCapabilities();

    console.log('🚀 Advanced ATO Basket Builder initialized with enhanced option chain support!');
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeApp);

// Auto-refresh active ATOs every 30 seconds
setInterval(() => {
    if (document.getElementById('active')?.classList.contains('active')) {
        loadActiveATOs();
    }
}, 30000);

console.log('✅ Advanced ATO Basket Builder JavaScript loaded successfully!');
