function generateId() {
    return Date.now() + Math.random();
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 100);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 3000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function addCustomStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .search-option {
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            transition: background-color 0.2s ease;
        }
        
        .search-option:hover {
            background: rgba(102, 126, 234, 0.2);
        }
        
        .search-option .strike-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .search-option .oi-info {
            display: flex;
            gap: 8px;
            font-size: 11px;
        }
        
        .lot-size-label {
            background: rgba(102, 126, 234, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 30px !important;
            color: #94a3b8;
            white-space: nowrap;
            margin-left: -70px;
            display: inline-block;
        }
        
        .form-group input, .form-group select {
            transition: border-color 0.3s ease;
        }
        
        .form-group input:focus, .form-group select:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }
        
        .oi-positive {
            color: #00b894 !important;
        }
        
        .oi-negative {
            color: #ff6b6b !important;
        }
        
        .oi-neutral {
            color: #94a3b8 !important;
        }
    `;
    
    document.head.appendChild(styleElement);
}

