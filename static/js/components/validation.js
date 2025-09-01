function validateBasket(basket) {
    const errors = [];

    if (basket.legs.length === 0) {
        errors.push('Basket must have at least one leg');
    }

    // console.log('Validating basket:', basket);

    basket.legs.forEach((leg, index) => {
        if (!leg.symbol) errors.push(`Leg ${index + 1}: Symbol is required`);
        if (!leg.instrumentType) errors.push(`Leg ${index + 1}: Instrument Type is required`);
        if (!leg.quantity) errors.push(`Leg ${index + 1}: Quantity is required`);

        // Check premium value for all legs
        if (leg.premium == null || leg.premium === '') {
            errors.push(`Leg ${index + 1}: Premium is required`);
        }

        if (leg.instrumentType === 'EQ') {
            // For equity, price is required
            if (!leg.premium) errors.push(`Leg ${index + 1}: Price is required for Equity`);
        } else {
            // For options and futures
            if (!leg.strike && leg.instrumentType !== 'FUT') {
                errors.push(`Leg ${index + 1}: Strike Price is required`);
            }
            if (!leg.expiry) {
                errors.push(`Leg ${index + 1}: Expiry Date is required`);
            }
        }
    });

    return errors;
}


function validateAlert() {
   const errors = [];

   const underlying = document.getElementById('underlying').value;
   const operator = document.getElementById('operator').value;
   const triggerPrice = document.getElementById('triggerPrice').value;
   const validTill = document.getElementById('validTill').value;
   
   if (!underlying) errors.push('Underlying is required');
   if (!operator) errors.push('Alert condition is required');
   if (!triggerPrice) errors.push('Trigger price is required');
   if (!validTill) errors.push('Valid till date is required');
   
   if (validTill) {
       const timingErrors = dateTimeHandler.validateATOTiming(
           new Date(), 
           new Date(validTill), 
           'NSE'
       );
       errors.push(...timingErrors);
   }
   
   return errors;
}

async function validateBasketWithMargins(basket) {
   const errors = [];

   if (basket.legs.length === 0) {
       errors.push('Basket must have at least one leg');
   }

   for (let index = 0; index < basket.legs.length; index++) {
       const leg = basket.legs[index];
       
       if (!leg.symbol) errors.push(`Leg ${index + 1}: Symbol is required`);
       if (!leg.instrumentType) errors.push(`Leg ${index + 1}: Instrument Type is required`);
       if (!leg.quantity) errors.push(`Leg ${index + 1}: Quantity is required`);

       if (leg.instrumentType !== 'EQ') {
           if (!leg.strike) errors.push(`Leg ${index + 1}: Strike Price is required`);
           if (!leg.expiry) errors.push(`Leg ${index + 1}: Expiry Date is required`);
       } else {
           if (!leg.price) errors.push(`Leg ${index + 1}: Price is required for Equity`);
       }

       try {
           const margin = await calculateLegMargin(leg);
           if (margin === 0 && leg.action === 'S') {
               errors.push(`Leg ${index + 1}: Warning - Zero margin for sell position`);
           }
       } catch (error) {
           errors.push(`Leg ${index + 1}: Margin calculation failed - ${error.message}`);
       }
   }

   return errors;
}

async function validateMarginsBeforeATO(baskets) {
   const errors = [];
   
   for (let basketIndex = 0; basketIndex < baskets.length; basketIndex++) {
       const basket = baskets[basketIndex];
       
       try {
           const basketMargin = await calculateBasketMargin(basket);
           
           if (basketMargin === 0 && basket.legs.length > 0) {
               const hasValidLegs = basket.legs.some(leg => isLegDataComplete(leg));
               if (hasValidLegs) {
                   errors.push(`Basket ${basketIndex + 1}: Margin calculation returned zero despite valid legs`);
               }
           }
           
           if (basketMargin > 1000000) {
               errors.push(`Basket ${basketIndex + 1}: Very high margin (₹${basketMargin.toLocaleString()}) - please verify`);
           }
           
           console.log(`Basket ${basketIndex + 1} margin validation: ₹${basketMargin.toLocaleString()}`);
           
       } catch (error) {
           errors.push(`Basket ${basketIndex + 1}: Margin calculation failed - ${error.message}`);
       }
   }
   
   return errors;
}

