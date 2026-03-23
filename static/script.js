document.addEventListener('DOMContentLoaded', () => {
    // ---- Graph Visualization ----
    let graph;
    
    // Type colors
    const colorMap = {
        'Customer': '#58a6ff',
        'SalesOrder': '#8957e5',
        'Product': '#3fb950',
        'Delivery': '#d29922',
        'Plant': '#ff7b72',
        'BillingDocument': '#f0883e',
        'JournalEntry': '#a371f7',
        'Payment': '#2ea043'
    };

    fetch('/api/graph')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('graph-container');
            graph = ForceGraph()(container)
                .graphData(data)
                .nodeLabel('title')
                .nodeColor(node => colorMap[node.label] || '#8b949e')
                .nodeVal(node => {
                    // Make nodes like SalesOrder slightly bigger if they have many connections
                    return ['Customer', 'SalesOrder'].includes(node.label) ? 1.5 : 1;
                })
                .linkColor(() => 'rgba(255,255,255,0.2)')
                .linkDirectionalArrowLength(3.5)
                .linkDirectionalArrowRelPos(1);
        });

    document.getElementById('resetGraphBtn').addEventListener('click', () => {
        if(graph) {
            graph.zoomToFit(400);
        }
    });

    // ---- Chat Interface ----
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const loading = document.getElementById('loading');

    function addMessage(text, isUser = false, type = 'system', sqlQuery = null) {
        const div = document.createElement('div');
        div.className = `message ${isUser ? 'user-message' : 'system-message'}`;
        
        if (type === 'error') {
            div.className = 'message error-message';
        }

        // Handle basic markdown/formatting
        let formattedText = text.replace(/\n/g, '<br>');
        div.innerHTML = formattedText;

        if (sqlQuery) {
            const sqlDiv = document.createElement('div');
            sqlDiv.className = 'sql-debug';
            sqlDiv.textContent = `Executed SQL:\n${sqlQuery}`;
            div.appendChild(sqlDiv);
        }

        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    async function handleSend() {
        const query = chatInput.value.trim();
        if (!query) return;

        addMessage(query, true);
        chatInput.value = '';
        loading.style.display = 'flex';

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
            loading.style.display = 'none';
        }
    }

    sendBtn.addEventListener('click', handleSend);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
});
