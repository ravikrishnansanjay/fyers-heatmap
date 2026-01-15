const CONFIG = {
    // symbol and wsUrl are now dynamic
    rowHeight: 24,
    rowHeight: 24,
    visibleRows: 60, // How many rows to render around center
    centerPrice: 780.0 // Approximate TMPV price
};

class HeatmapRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d', { alpha: true });
        this.width = window.innerWidth;
        this.height = CONFIG.rowHeight * CONFIG.visibleRows * 2; // Extra buffer
        this.canvas.width = this.width;
        this.canvas.height = this.height;

        // Price -> Heat History (Ring buffer logic simplified)
        // Map<price, {bidHeat: float, askHeat: float}>
        this.heatMap = new Map();

        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        this.width = window.innerWidth;
        this.canvas.width = this.width;
        // height managed via content
    }

    update(price, bidHeat, askHeat) {
        this.heatMap.set(price, { bidHeat, askHeat, timestamp: Date.now() });
    }

    // In a full implementation, we would draw a scrolling history (time on X axis)
    // For this DOM view, we often just want the ladder itself to glow.
    // Let's implement background coloring of the ladder rows instead of a separate complex WebGL shader for now,
    // as it's more standard for DOM ladders.
    // If the user wants a "Bookmap" style (Price vs Time), that's different.
    // The prompt asked for "DOM Heat Map" which often means the ladder columns themselves.
    // However, "Limit order concentration" often implies the chart.
    // Let's stick to coloring the ladder background cells first.
}

class DomLadder {
    constructor() {
        this.ladderEl = document.getElementById('ladder-rows');
        this.rows = new Map(); // price -> element
        this.data = { bids: {}, asks: {} };
        this.centerPrice = CONFIG.centerPrice;
    }

    render(snapshot) {
        // 1. Process Data
        snapshot.bids.forEach(level => {
            this.data.bids[level.price] = level;
        });
        snapshot.asks.forEach(level => {
            this.data.asks[level.price] = level;
        });

        // Update Center if first run
        if (!this.initialized) {
            if (snapshot.bids.length > 0) {
                this.centerPrice = snapshot.bids[0].price;
                this.initialized = true;
                this.initRows();
            }
        }

        this.updateRows();
    }

    initRows() {
        this.ladderEl.innerHTML = '';
        this.rows.clear();

        // Generate range around center
        const range = 40;
        const startPrice = this.centerPrice + (range * 5);
        const endPrice = this.centerPrice - (range * 5);

        for (let p = startPrice; p >= endPrice; p -= 5) {
            this.createRow(p);
        }
    }

    createRow(price) {
        const row = document.createElement('div');
        row.className = 'ladder-row';
        row.dataset.price = price;

        row.innerHTML = `
            <div class="cell-bid"></div>
            <div class="cell-price">${price}</div>
            <div class="cell-ask"></div>
            <div class="heat-bar-bid"></div>
            <div class="heat-bar-ask"></div>
        `;

        row.addEventListener('click', () => {
            console.log(`Clicked price ${price}`);
            document.getElementById('order-panel').classList.remove('hidden');
            document.getElementById('order-price').value = price;
        });

        this.ladderEl.appendChild(row);
        this.rows.set(price, row);
    }

    updateRows() {
        this.rows.forEach((row, price) => {
            const bid = this.data.bids[price];
            const ask = this.data.asks[price];

            const bidCell = row.querySelector('.cell-bid');
            const askCell = row.querySelector('.cell-ask');
            const bidBar = row.querySelector('.heat-bar-bid');
            const askBar = row.querySelector('.heat-bar-ask');

            if (bid) {
                bidCell.textContent = bid.size;
                // Heatmap Color Logic
                const intensity = bid.heat_intensity;
                // Simple opacity or width based on size
                bidBar.style.width = `${Math.min(intensity * 100, 100)}%`;
                // Color scaling
                bidBar.style.backgroundColor = this.getHeatColor(intensity, 'bid');
            } else {
                bidCell.textContent = '';
                bidBar.style.width = '0';
            }

            if (ask) {
                askCell.textContent = ask.size;
                const intensity = ask.heat_intensity;
                askBar.style.width = `${Math.min(intensity * 100, 100)}%`;
                askBar.style.backgroundColor = this.getHeatColor(intensity, 'ask');
            } else {
                askCell.textContent = '';
                askBar.style.width = '0';
            }
        });
    }

    getHeatColor(intensity, side) {
        // Heatmap gradient: Blue (Low) -> Orange -> Red (High)
        // Simplified for DOM bars
        if (side === 'bid') return `rgba(35, 134, 54, ${0.2 + intensity * 0.8})`;
        if (side === 'ask') return `rgba(218, 54, 51, ${0.2 + intensity * 0.8})`;
    }
}

// WebSocket Logic
// WebSocket Logic
let socket = null;
const statusEl = document.getElementById('connection-status');
const ladder = new DomLadder();
const symbolSelect = document.getElementById('symbol-select');

function connectWebSocket(symbol) {
    if (socket) {
        socket.close();
    }

    const wsUrl = `ws://${window.location.host}/ws/dom/${symbol}`;
    console.log(`Connecting to ${wsUrl}...`);
    statusEl.textContent = 'Connecting...';
    statusEl.classList.remove('connected');

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        statusEl.textContent = 'Connected';
        statusEl.classList.add('connected');
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'snapshot') {
            ladder.render(msg.data);
        }
    };

    socket.onclose = () => {
        statusEl.textContent = 'Disconnected';
        statusEl.classList.remove('connected');
    };
}

// Initial Connection
connectWebSocket(symbolSelect.value);

// Handle Symbol Change
symbolSelect.addEventListener('change', (e) => {
    const newSymbol = e.target.value;
    // Clear data
    ladder.data = { bids: {}, asks: {} };
    ladder.rows.clear();
    ladder.ladderEl.innerHTML = '';
    ladder.initialized = false;

    // Update Config (optional, if we want to store it)
    CONFIG.symbol = newSymbol;

    connectWebSocket(newSymbol);
});

function closeOrderPanel() {
    document.getElementById('order-panel').classList.add('hidden');
}
