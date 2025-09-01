let baskets = [];
let basketIdCounter = 1;
let atos = [];
let currentRiskMode = {};
let currentPremiumSelection = {
    basketId: null,
    legIndex: null
};
let symbolsData = {};
let strikesData = {};
let expiriesData = {};

window.apiCache = {
    expiries: {},
    strikes: {},
    loading: {
        expiries: {},
        strikes: {}
    }
};
