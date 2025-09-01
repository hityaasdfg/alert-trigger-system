function canExitTrades(ato) {
    if (!ato || ato.status !== 'triggered') {
        return false;
    }
    
    const activeBaskets = ato.baskets.filter(b => {
        if (!b.status && ato.status === 'triggered') {
            return true;
        }
        return b.status !== 'exited';
    });
    
    return activeBaskets.length > 0;
}

function getOriginalLegIndex(basket, activeLeg) {
    return basket.legs.findIndex(leg => 
        leg.id === activeLeg.id || 
        (leg.symbol === activeLeg.symbol && 
        leg.instrument_type === activeLeg.instrument_type && 
        leg.strike === activeLeg.strike && 
        leg.action === activeLeg.action)
    );
}

function renderBasketWithLegStatus(basket, index, atoStatus) {
    let basketStatus = basket.status || (atoStatus === 'triggered' ? 'active' : 'pending');
    const isExited = basketStatus === 'exited';

    const totalLegs = basket.legs.length;
    const exitedLegs = basket.legs.filter(leg => leg.status === 'exited').length;
    const activeLegs = totalLegs - exitedLegs;

    const isPartiallyExited = basket.legs.some(leg => {
    const q = Number(leg.quantity || 0);
    const eq = leg.exit_quantity !== undefined
            ? Number(leg.exit_quantity)
            : (leg.partial_exits || []).reduce((sum, rec) => sum + (rec.quantity || 0), 0);
        return eq > 0 && eq < q;
    });

    // Show exit button only if ATO is triggered and basket has active legs
    const showExitButton = atoStatus === 'triggered' && activeLegs > 0;

    return `
    <div style="background: rgba(255,255,255,0.05); border-radius: 6px; padding: 12px; border-left: 3px solid ${isPartiallyExited ? '#fdcb6e' : isExited ? '#ff6b6b' : '#00b894'} : '#00b894'};">
        
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: #f1f5f9;">${index + 1}. ${basket.label}</strong>
                <span style="color: #94a3b8; font-size: 12px; margin-left: 10px; text-transform: uppercase;">
                    ${basket.strategy.replace(/_/g, ' ')}
                </span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <!-- Exit Button (Left of Status) -->
                ${showExitButton ? `
                <button onclick="exitSingleBasket(${basket.id})" 
                        style="
                            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                            color: white;
                            border: none;
                            padding: 3px 6px;
                            border-radius: 3px;
                            cursor: pointer;
                            font-size: 9px;
                            font-weight: 600;
                            text-transform: uppercase;
                            letter-spacing: 0.3px;
                            transition: all 0.3s ease;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                        "
                        onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 2px 6px rgba(255, 107, 107, 0.4)';"
                        onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.2)';"
                        title="Exit this basket">
                    Exit
                </button>
                ` : ''}
                
                <!-- Status Badge -->
                ${isExited ? 
                    `<span style="background: #ff6b6b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">EXITED</span>` : 
                    isPartiallyExited ?
                    `<span style="background: #fdcb6e; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">PARTIAL</span>` :
                    `<span style="background: #00b894; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; display: ${atoStatus === 'triggered' ? 'inline-block' : 'none'}">ACTIVE</span>`
                }
            </div>
        </div>
        
        <div style="margin-top: 8px; display: flex; gap: 15px; font-size: 12px; color: #94a3b8;">
            <span>📊 Legs: ${activeLegs}/${totalLegs}</span>
            <span>⚡ Risk: ${basket.risk_mode ? basket.risk_mode.replace('_', ' ').toUpperCase() : 'INDIVIDUAL'}</span>
            ${basket.exited_at ? `<span>🕐 Exited: ${new Date(basket.exited_at).toLocaleTimeString()}</span>` : ''}
        </div>
        
        <div style="margin-top: 8px; display: grid; gap: 8px;">
            ${basket.legs.map((leg, legIndex) => {
                const legIsExited = leg.status === 'exited';
                const showLegExitButton = atoStatus === 'triggered' && !legIsExited;

                return `
                <div style="display: flex; justify-content: space-between; align-items: center; 
                    background: rgba(255,255,255,0.02); padding: 6px 10px; border-radius: 4px;
                    border-left: 2px solid ${legIsExited ? '#ff6b6b' : '#00b894'};">
                    
                    <div>
                        <span style="color: #e2e8f0; font-size: 11px;">
                        ${legIndex + 1}. ${leg.action} ${leg.symbol} ${leg.instrument_type} ${leg.strike || ''}
                        </span>
                        <span style="color: #94a3b8; font-size: 10px; margin-left: 8px;">
                        Qty: ${leg.quantity}
                        </span>
                        <span style="color: #94a3b8; font-size: 10px; margin-left: 8px;">
                        Exit Qty: ${leg.exit_quantity}
                        </span>
                        <span style="color: #94a3b8; font-size: 10px; margin-left: 8px;">
                        ENTRY: ₹${leg.price || leg.premium || 0}
                        </span>
                        ${legIsExited && leg.exit_price ? `
                        <span style="color: #94a3b8; font-size: 10px; margin-left: 8px;">
                        EXIT: ₹${leg.exit_price || leg.exit_price || 0}
                        </span>
                        ` : ''}
                        ${legIsExited && leg.pnl ? `
                        <span style="color: ${leg.pnl >= 0 ? '#2ecc71' : '#ff6b6b'}; font-size: 10px; margin-left: 8px;">
                            pnl: ₹${leg.pnl.toFixed(2)}
                        </span>
                        ` : ''}
                    </div>
                    
                    <!-- Right side: Status + Exit Button -->
                    <div style="display: flex; align-items: center; gap: 6px;">
                        ${legIsExited ? 
                        `<span style="background: #ff6b6b; color: white; padding: 1px 4px; border-radius: 2px; font-size: 9px;">EXITED</span>` : 
                        `<span style="background: #00b894; color: white; padding: 1px 4px; border-radius: 2px; font-size: 9px;">ACTIVE</span>`
                        }
                        
                        <!-- Individual Leg Exit Button (Right Side) -->
                        ${showLegExitButton ? `
                        <button onclick="exitSingleLeg(${basket.id}, ${leg.id || legIndex})" 
                                style="
                                    background: linear-gradient(135deg, #fdcb6e 0%, #e17055 100%);
                                    color: white;
                                    border: none;
                                    padding: 2px 6px;
                                    border-radius: 3px;
                                    cursor: pointer;
                                    font-size: 8px;
                                    font-weight: 600;
                                    transition: all 0.3s ease;
                                    box-shadow: 0 1px 2px rgba(0,0,0,0.2);
                                    min-width: 20px;
                                "
                                onmouseover="this.style.transform='scale(1.1)'; this.style.boxShadow='0 2px 4px rgba(253, 203, 110, 0.4)';"
                                onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 1px 2px rgba(0,0,0,0.2)';"
                                title="Exit this leg only">
                            ×
                        </button>
                        ` : ''}
                    </div>
                </div>
                `;
            }).join('')}
        </div>

    </div>
    `;
}





// Additional function for single leg exit (alternative to full basket exit)
async function exitSingleLeg(basketId, legId) {
    const ato = atos.find(a => a.baskets.some(b => b.id == basketId));
    if (!ato || ato.status !== 'triggered') {
        showNotification('ATO must be in triggered status to exit trades', 'error');
        return;
    }

    const basket = ato.baskets.find(b => b.id == basketId);
    if (!basket) {
        showNotification('Basket not found', 'error');
        return;
    }

    // Find the leg (by ID or index)
    const leg = basket.legs.find(l => l.id == legId) || basket.legs[legId];
    if (!leg || leg.status === 'exited') {
        showNotification('Leg not found or already exited', 'error');
        return;
    }

    // Show exit form directly for this leg
    const exitData = await showExitForm(leg, basket);
    
    if (!exitData) {
        showNotification('Exit cancelled', 'info');
        return;
    }
    
    await processLegExit(leg, basket, exitData);
    
    // Check if all legs are now exited
    const remainingActiveLegs = basket.legs.filter(leg => leg.status !== 'exited').length;
    if (remainingActiveLegs === 0) {
        basket.status = 'exited';
        basket.exited_at = new Date().toISOString();
    }
    
    showNotification(`✅ Position exited successfully!`, 'success');
    updateActiveATOs();
    setTimeout(() => loadActiveATOs(), 500);
}

function updateActiveATOs() {
    const container = document.getElementById('activeATOsList');

    if (atos.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #94a3b8;">No active ATOs found. Create your first ATO in the Builder tab.</p>';
        return;
    }

    const sortedATOs = [...atos].sort((a, b) => {
        const statusPriority = {
            'triggered': 1,
            'waiting': 2,
            'completed': 3,
            'cancelled': 4
        };
        const priorityA = statusPriority[a.status] || 5;
        const priorityB = statusPriority[b.status] || 5;

        if (priorityA !== priorityB) {
            return priorityA - priorityB;
        }

        return new Date(b.created_at) - new Date(a.created_at);
    });

    let html = `
    <div style="margin-bottom: 30px; text-align: center;">
        <h4 style="color: #667eea; margin-bottom: 10px;">📊 Active ATOs Dashboard</h4>
        <div style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
            <div style="background: rgba(0, 184, 148, 0.1); padding: 10px 20px; border-radius: 8px; border: 1px solid rgba(0, 184, 148, 0.3);">
                <strong style="color: #00b894;">TRIGGERED: ${sortedATOs.filter(a => a.status === 'triggered').length}</strong>
            </div>
            <div style="background: rgba(253, 203, 110, 0.1); padding: 10px 20px; border-radius: 8px; border: 1px solid rgba(253, 203, 110, 0.3);">
                <strong style="color: #fdcb6e;">WAITING: ${sortedATOs.filter(a => a.status === 'waiting').length}</strong>
            </div>
            <div style="background: rgba(116, 185, 255, 0.1); padding: 10px 20px; border-radius: 8px; border: 1px solid rgba(116, 185, 255, 0.3);">
                <strong style="color: #74b9ff;">COMPLETED: ${sortedATOs.filter(a => a.status === 'completed').length}</strong>
            </div>
            
        </div>
    </div>
    `;

    sortedATOs.forEach(ato => {
        const totalMargin = ato.total_margin_required || 0;
        const totalLegs = ato.baskets.reduce((sum, basket) => sum + basket.legs.length, 0);
        
        const canEditDelete = ato.status === 'waiting';
        const canTrade = canExitTrades(ato);

        const activeBaskets = ato.baskets.filter(b => {
            if (!b.status && ato.status === 'triggered') {
                return true;
            }
            return b.status !== 'exited';
        }).length;

        const createdTime = new Date(ato.created_at);
        const triggeredTime = ato.triggered_at ? new Date(ato.triggered_at) : null;
        const completedTime = ato.completed_at ? new Date(ato.completed_at) : null;
        const cancelledTime = ato.cancelled_at ? new Date(ato.cancelled_at) : null;
        const updatedTime = ato.updated_at && ato.updated_at !== ato.created_at ? new Date(ato.updated_at) : null;

        const startTime = triggeredTime || createdTime;
        const elapsedInfo = dateTimeHandler.getMarketAwareElapsedTime(startTime);
        const timeElapsed = elapsedInfo.trading;

        html += `
        <div class="section" style="border-left: 4px solid ${getStatusColor(ato.status)};">
            <div class="ato-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                <div>
                    <h4 style="margin: 0; color: #f1f5f9;">🎯 ATO #${ato.id.toString().slice(-6)}</h4>
                    <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 14px;">
                        ${ato.symbol} ${ato.operator} ${ato.threshold} • 
                        ${timeElapsed < 60 ? `${timeElapsed}m ago` : `${Math.floor(timeElapsed / 60)}h ${timeElapsed % 60}m ago`}
                    </p>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="status-badge status-${ato.status}">${ato.status.toUpperCase()}</span>
                    ${canTrade ? `<span style="background: rgba(0, 184, 148, 0.2); color: #00b894; padding: 4px 8px; border-radius: 4px; font-size: 11px;">🔥 LIVE</span>` : ''}
                    ${updatedTime ? `<span style="background: rgba(116, 185, 255, 0.2); color: #74b9ff; padding: 4px 8px; border-radius: 4px; font-size: 11px;">✏️ EDITED</span>` : ''}
                </div>
            </div>
            
            <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div>
                        <strong style="color: #667eea;">📈 Alert Details</strong>
                        <div style="color: #e2e8f0; font-size: 14px; margin-top: 5px;">
                            ${ato.symbol} ${ato.operator} ${ato.threshold}
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            Valid till: ${new Date(ato.valid_till).toLocaleDateString('en-GB')} ${new Date(ato.valid_till).toLocaleTimeString()}
                        </div>
                    </div>
                    
                    <div>
                        <strong style="color: #00b894;">⏰ Timeline</strong>
                        <div style="color: #e2e8f0; font-size: 14px; margin-top: 5px;">
                            Created: ${createdTime.toLocaleString('en-GB', { hour12: false })}
                        </div>
                        ${updatedTime ? `<div style="color: #74b9ff; font-size: 12px;">Updated: ${updatedTime.toLocaleString('en-GB', { hour12: false })}</div>` : ''}
                        ${triggeredTime ? `<div style="color: #00b894; font-size: 12px;">Triggered: ${triggeredTime.toLocaleString('en-GB', { hour12: false })}</div>` : ''}
                        ${completedTime ? `<div style="color: #74b9ff; font-size: 12px;">Completed: ${completedTime.toLocaleString('en-GB', { hour12: false })}</div>` : ''}
                        
                    </div>
                    
                    <div>
                        <strong style="color: #fdcb6e;">💰 Margin & Stats</strong>
                        <div style="color: #e2e8f0; font-size: 14px; margin-top: 5px;">
                            Total Margin: ₹${totalMargin.toLocaleString()}
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            Baskets: ${ato.baskets.length} • Legs: ${totalLegs}
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5 style="color: #f1f5f9; margin-bottom: 10px;">🧺 Baskets (${ato.baskets.length})</h5>
                <div style="display: grid; gap: 10px;">
                    ${ato.baskets.map((basket, index) => renderBasketWithLegStatus(basket, index, ato.status)).join('')}
                </div>
            </div>
            
            <div class="ato-actions">
                <!--  
                <button class="btn-btn-primary btn-sm" onclick="viewATODetails('${ato.id}')">
                   📋 View Details
               </button>
                -->
               ${canEditDelete ? `
                   <button class="btn btn-info btn-sm" onclick="editATO('${ato.id}')">
                       ✏️ Edit ATO
                   </button>
                   <button class="btn btn-danger btn-sm" onclick="deleteATO('${ato.id}')">
                       🗑️ Delete
                   </button>
                    <!--
                    <button class="btn btn-warning btn-sm" onclick="triggerATO('${ato.id}')">
                        🚀 Trigger Now
                    </button>
                     -->
                    
               ` : ''}
               
               ${canTrade ? `
                    <!--
                   <button class="btn btn-warning btn-sm" onclick="exitSingleTrade('${ato.id}')">
                       🔄 Exit Single Trade
                   </button>
                   -->
                   <button class="btn btn-danger btn-sm" onclick="exitAllTrades('${ato.id}')">
                       🚪 Exit All Trades
                   </button>
               ` : ''}
           </div>
       </div>
   `;
   });

   container.innerHTML = html;
}

function getStatusColor(status) {
   switch (status) {
       case 'triggered':
           return '#00b894';
       case 'waiting':
           return '#fdcb6e';
       case 'completed':
           return '#74b9ff';
       case 'cancelled':
           return '#ff6b6b';
       default:
           return '#94a3b8';
   }
}

