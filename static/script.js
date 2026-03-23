document.addEventListener('DOMContentLoaded', () => {
    // ---- Graph Visualization ----
    let graph;
    let graphData = { nodes: [], links: [] };
    const container = document.getElementById('graph-container');
    const tooltip = document.getElementById('graph-tooltip');
    
    // Type colors for light theme
    const colorMap = {
        'Customer': '#3b82f6', // blue
        'SalesOrder': '#3b82f6',
        'Product': '#ef4444', // red
        'Delivery': '#3b82f6',
        'Plant': '#ef4444', 
        'BillingDocument': '#3b82f6',
        'JournalEntry': '#3b82f6',
        'Payment': '#3b82f6'
    };

    fetch('/api/graph')
        .then(res => res.json())
        .then(data => {
            graphData = data;
            graph = ForceGraph()(container)
                .width(container.clientWidth)
                .height(container.clientHeight)
                .graphData(data)
                .nodeRelSize(4)
                .nodeColor(node => colorMap[node.label] || '#9ca3af')
                .nodeCanvasObject((node, ctx, globalScale) => {
                    const label = node.label;
                    const size = ['Customer', 'SalesOrder', 'JournalEntry'].includes(label) ? 6 : 3;
                    
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                    
                    // Draw node styling depending on type (some filled, some hollow)
                    if (['Product', 'Plant'].includes(label)) {
                        ctx.fillStyle = '#fff';
                        ctx.fill();
                        ctx.lineWidth = 1.5;
                        ctx.strokeStyle = '#ef4444'; // Red outline
                        ctx.stroke();
                    } else {
                        ctx.fillStyle = '#fff';
                        ctx.fill();
                        ctx.lineWidth = 1.5;
                        ctx.strokeStyle = '#3b82f6'; // Blue outline
                        ctx.stroke();
                        
                        // If it's a main node, fill it or add inner dot
                        if (size === 6) {
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, 2, 0, 2 * Math.PI, false);
                            ctx.fillStyle = '#3b82f6';
                            ctx.fill();
                        }
                    }
                })
                .linkColor(() => '#bde0fe') // Light blue links
                .linkWidth(0.5)
                .onNodeHover(node => {
                    container.style.cursor = node ? 'pointer' : null;
                    if (node) {
                        // Show Custom Tooltip
                        tooltip.style.display = 'block';
                        
                        // Populate tooltip cleanly
                        tooltip.innerHTML = `
                            <h3>${node.label}</h3>
                            <div class="tooltip-row"><span>Entity:</span><span class="val">${node.label}</span></div>
                            <div class="tooltip-row"><span>ID:</span><span class="val">${node.id.split('_')[1] || node.id}</span></div>
                            <div class="tooltip-row"><span>Title:</span><span class="val">${node.title}</span></div>
                            <div class="tooltip-footer">
                                Connections: ${graphData.links.filter(l => l.source.id === node.id || l.target.id === node.id).length}
                            </div>
                            <div class="tooltip-hidden-msg">Additional fields hidden for readability</div>
                        `;
                    } else {
                        tooltip.style.display = 'none';
                    }
                })
                .onZoom(() => {
                    tooltip.style.display = 'none';
                });
                
            // Follow mouse for tooltip
            container.addEventListener("mousemove", (event) => {
                if (tooltip.style.display === 'block') {
                    tooltip.style.left = event.pageX + 15 + 'px';
                    tooltip.style.top = event.pageY + 15 + 'px';
                }
            });
            
            // Handle window resize dynamically
            window.addEventListener('resize', () => {
                if (graph) {
                    graph.width(container.clientWidth).height(container.clientHeight);
                }
            });
        });

    document.querySelector('.btn-minimize').addEventListener('click', () => {
        if(graph) graph.zoomToFit(400);
    });

    // ---- Chat Interface ----
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('status-text');

    // Enable/Disable send button styling based on input
    chatInput.addEventListener('input', () => {
        if (chatInput.value.trim().length > 0) {
            sendBtn.classList.add('active');
        } else {
            sendBtn.classList.remove('active');
        }
    });

    function addMessage(text, isUser = false, type = 'system', sqlQuery = null) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${isUser ? 'user' : 'system'}`;
        
        let avatarHTML = isUser ? 
            `<div class="avatar-container"><div class="user-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg></div></div>` :
            `<div class="avatar-container"><div class="system-avatar">D</div></div>`;
            
        let senderHTML = isUser ? 
            `<div class="message-sender"><strong>You</strong></div>` :
            `<div class="message-sender"><strong>Dodge AI</strong><br><span>Graph Agent</span></div>`;

        let contentClass = isUser ? 'user-message' : (type === 'error' ? 'error-message' : 'system-message');
        
        let formattedText = text.replace(/\n/g, '<br>');
        let sqlHTML = sqlQuery ? `<div class="sql-debug">Executed SQL:\n${sqlQuery}</div>` : '';

        wrapper.innerHTML = `
            ${avatarHTML}
            <div class="message-content-wrapper">
                ${senderHTML}
                <div class="message ${contentClass}">
                    ${formattedText}
                    ${sqlHTML}
                </div>
            </div>
        `;

        chatHistory.appendChild(wrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    async function handleSend() {
        const query = chatInput.value.trim();
        if (!query) return;

        addMessage(query, true);
        chatInput.value = '';
        sendBtn.classList.remove('active');
        
        // Update status to loading
        statusDot.classList.add('loading');
        statusText.textContent = 'Dodge AI is thinking...';

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const data = await response.json();
            
            if (response.ok) {
                addMessage(data.response, false, 'system', data.sql_query);
            } else {
                addMessage(`Server Error: ${data.detail}`, false, 'error');
            }
        } catch (error) {
            addMessage(`Failed to connect to server: ${error.message}`, false, 'error');
        } finally {
            // Restore status
            statusDot.classList.remove('loading');
            statusText.textContent = 'Dodge AI is awaiting instructions';
        }
    }

    sendBtn.addEventListener('click', handleSend);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });
});
