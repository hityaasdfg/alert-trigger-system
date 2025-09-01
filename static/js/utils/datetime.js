const dateTimeHandler = {
    getDefaultATOValidTill: function(exchange = 'NSE') {
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        
        const marketClose = new Date(now);
        marketClose.setHours(15, 30, 0, 0);
        
        let validTill;
        
        if (now > marketClose) {
            validTill = new Date(now);
            validTill.setDate(validTill.getDate() + 1);
            validTill.setHours(15, 30, 0, 0);
        } else {
            validTill = new Date(marketClose);
        }
        
        while (validTill.getDay() === 0 || validTill.getDay() === 6) {
            validTill.setDate(validTill.getDate() + 1);
        }
        
        return validTill;
    },
    
    formatDateTimeForUser: function(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffMins < 1) {
            return 'Just now';
        } else if (diffMins < 60) {
            return `${diffMins}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else if (diffDays < 7) {
            return `${diffDays}d ago`;
        } else {
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
    },
    
    getMarketAwareElapsedTime: function(startTime) {
        const start = new Date(startTime);
        const now = new Date();
        const totalMs = now - start;
        const totalMinutes = Math.floor(totalMs / (1000 * 60));
        
        return {
            total: totalMinutes,
            trading: totalMinutes
        };
    },
    
    formatExpiryLabel: function(expiryDate) {
        const today = new Date();
        const expiry = new Date(expiryDate);
        const msPerDay = 1000 * 60 * 60 * 24;
        const diffMs = expiry.getTime() - today.getTime();
        const diffDays = Math.ceil(diffMs / msPerDay);
        
        if (diffDays === 0) {
            return 'Expires today';
        } else if (diffDays === 1) {
            return 'Expires tomorrow';
        } else if (diffDays > 0) {
            return `${diffDays} days to expiry`;
        } else {
            const pastDays = Math.abs(diffDays);
            return `Expired ${pastDays} day${pastDays > 1 ? 's' : ''} ago`;
        }
    },
    
    validateATOTiming: function(triggerTime, validTill, exchange = 'NSE') {
        const errors = [];
        const now = new Date();
        
        if (validTill <= now) {
            errors.push('Valid till time must be in the future');
        }
        
        // const validTillHour = validTill.getHours();
        // if (validTillHour < 9 || (validTillHour === 9 && validTill.getMinutes() < 15) || 
        //     validTillHour > 15 || (validTillHour === 15 && validTill.getMinutes() > 30)) {
        //     errors.push('Valid till time should be during market hours (9:15 AM - 3:30 PM)');
        // }
        
        const day = validTill.getDay();
        if (day === 0 || day === 6) {
            errors.push('Valid till date cannot be on weekend');
        }
        
        return errors;
    },
    
    isMarketHours: function(exchange = 'NSE') {
        const now = new Date();
        const hour = now.getHours();
        const minute = now.getMinutes();
        const day = now.getDay();
        
        if (day === 0 || day === 6) {
            return false;
        }
        
        const marketStart = 9 * 60 + 15;
        const marketEnd = 15 * 60 + 30;
        const currentMinutes = hour * 60 + minute;
        
        return currentMinutes >= marketStart && currentMinutes <= marketEnd;
    }
};

