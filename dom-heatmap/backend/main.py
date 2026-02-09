from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
from typing import List, Optional, Dict
import json
from urllib import request, error

# from .flyer_adapter import MockFlyerClient
from .fyers_client import FyersClient
from .heatmap_engine import HeatmapEngine
from .models import DomUpdate, FlatTradeOrderRequest

# Configuration (from User Request)
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Configuration
FYERS_APP_ID = os.getenv("FYERS_APP_ID")
FYERS_SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth-callback")
FLATTRADE_PI_ORDER_URL = os.getenv("FLATTRADE_PI_ORDER_URL")
FLATTRADE_PI_API_KEY = os.getenv("FLATTRADE_PI_API_KEY")
FLATTRADE_PI_ACCESS_TOKEN = os.getenv("FLATTRADE_PI_ACCESS_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
import os

# Mount static files
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="frontend")
# We'll serve UI at /ui to avoid conflict with /auth-callback or keep / as well?
# Let's keep / as UI for simplicity but redirect auth there.

# Global Fyers Client
fyers_client = FyersClient(client_id=FYERS_APP_ID, secret_key=FYERS_SECRET_ID, redirect_uri=REDIRECT_URI)

class ConnectionManager:
    def __init__(self):
        # Map symbol -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.active_connections:
            self.active_connections[symbol] = []
        self.active_connections[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.active_connections:
            if websocket in self.active_connections[symbol]:
                self.active_connections[symbol].remove(websocket)
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]

    async def broadcast(self, message: str, symbol: str):
        if symbol in self.active_connections:
            # Broadcast only to subscribers of this symbol
            # Copy list to avoid modification issues during iteration
            for connection in self.active_connections[symbol][:]:
                try:
                    await connection.send_text(message)
                except Exception:
                    # Handle disconnected clients gracefully if needed
                    pass

manager = ConnectionManager()

# Global state for simulation/stream
active_streams = {}

@app.get("/")
def read_root():
    # Helper index to guide user
    auth_url = fyers_client.get_auth_url()
    return HTMLResponse(content=f"""
    <html>
        <body>
            <h1>DOM Heatmap Server</h1>
            <p>Status: Running</p>
            <p><a href="/ui/">Go to Heatmap UI</a></p>
            <hr/>
            <h2>Fyers Authentication</h2>
            <p>Status: {"Authenticated" if fyers_client.access_token else "Not Authenticated"}</p>
            <p>If not authenticated, please <a href="{auth_url}" target="_blank">Login with Fyers</a></p>
        </body>
    </html>
    """)

@app.get("/auth-callback")
def auth_callback(auth_code: Optional[str] = None):
    if auth_code:
        try:
            fyers_client.generate_token(auth_code)
            return {"status": "success", "message": "Authentication successful. You can close this window and open the Heatmap UI."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "No auth code provided"}

@app.post("/api/orders")
def place_order(order: FlatTradeOrderRequest):
    if not FLATTRADE_PI_ORDER_URL:
        raise HTTPException(status_code=500, detail="FLATTRADE_PI_ORDER_URL is not configured.")

    if order.order_type == "LIMIT" and order.price is None:
        raise HTTPException(status_code=422, detail="Price is required for LIMIT orders.")

    payload = {
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "order_type": order.order_type,
        "price": order.price,
        "product_type": order.product_type,
        "validity": order.validity,
        "disclosed_quantity": order.disclosed_quantity,
        "remarks": order.remarks,
    }

    headers = {"Content-Type": "application/json"}
    if FLATTRADE_PI_API_KEY:
        headers["X-API-Key"] = FLATTRADE_PI_API_KEY
    if FLATTRADE_PI_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {FLATTRADE_PI_ACCESS_TOKEN}"

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(FLATTRADE_PI_ORDER_URL, data=data, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=15) as response:
            response_body = response.read()
            response_data = json.loads(response_body) if response_body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Order request failed: {exc}") from exc

    return {"status": "submitted", "data": response_data}

@app.websocket("/ws/dom/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await manager.connect(websocket, symbol)
    
    # Start stream if not running for this specific symbol
    if symbol not in active_streams:
        # Create dedicated task for this symbol's data generation
        engine = HeatmapEngine()
        
        async def broadcast_updates(snapshot):
            # Calculate heat
            snapshot.bids = engine.calculate_heat(snapshot.bids)
            snapshot.asks = engine.calculate_heat(snapshot.asks)
            
            update = DomUpdate(type="snapshot", data=snapshot)
            await manager.broadcast(update.model_dump_json(), symbol)

        # Start the stream in background
        task = asyncio.create_task(fyers_client.stream_updates(symbol, broadcast_updates))
        active_streams[symbol] = {"task": task}
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, symbol)
        # Cleanup if needed regarding active streams... 
        # For now, keep the stream running for other potential clients or simplicity
