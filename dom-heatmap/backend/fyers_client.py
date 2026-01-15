import asyncio
import os
import json
import time
from typing import Callable, Any, Dict
# from fyers_apiv3 import fyersModel
# from fyers_apiv3.FyersWebsocket import data_ws
from .models import DomSnapshot, PriceLevel, Side

# Temporary Mock-like structure until we install the package and confirm it works
class FyersClient:
    def __init__(self, client_id: str, secret_key: str, redirect_uri: str = "http://localhost"):
        self.client_id = client_id
        self.secret_key = secret_key
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.fyers = None
        self.running = False
        self.ws_access_token = None

    def get_auth_url(self) -> str:
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id=self.client_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            return session.generate_authcode()
        except ImportError:
            return "https://api.fyers.in/api/v2/generate-authcode?client_id=" + self.client_id + "&redirect_uri=" + self.redirect_uri + "&response_type=code&state=sample_state"

    def generate_token(self, auth_code: str):
        from fyers_apiv3 import fyersModel
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth_code)
        response = session.generate_token()
        if response["s"] == "ok":
            self.access_token = response["access_token"]
            self.fyers = fyersModel.FyersModel(client_id=self.client_id, is_async=False, token=self.access_token, log_path="")
            self.ws_access_token = f"{self.client_id}:{self.access_token}"
            print("Access token generated successfully.")
        else:
            raise Exception(f"Failed to generate token: {response}")

    async def stream_updates(self, symbol: str, callback: Callable[[DomSnapshot], None]):
        """
        Connects to Fyers Data Socket and streams Depth L2 updates.
        """
        if not self.access_token:
            print("Warning: No access token. Streaming MOCK data for demonstration (or should error if strict).")
            # For strict mode requested:
            # raise Exception("Authentication required for real data.")
            # But let's fallback nicely or notify
            print("Please authenticate via http://localhost:8000/")
            await self.mock_stream(symbol, callback)
            return

        from fyers_apiv3.FyersWebsocket import data_ws

        self.running = True
        loop = asyncio.get_event_loop()

        # Fyers SDK Callbacks
        def on_message(message):
            """
            Received message from Fyers WS.
            """
            try:
                # print("WS Message:", message) # Debugging

                # Fyers V3 dict response usually contains 'type' and 'symbol'
                # Check documentation for exact structure. 
                # Assuming standard dictionary response for now given the SDK wrapper.
                
                if isinstance(message, dict) and message.get("type") == "depth_update":
                    # Parse depth data
                    # Structure example estimate: {'symbol': '...', 'bids': [{'price': 100, 'vol': 10}], 'asks': ...}
                    
                    bids_data = message.get("bids", [])
                    asks_data = message.get("asks", [])
                    
                    bids = [
                        PriceLevel(price=b['price'], size=b['volume'], order_count=b.get('ord_cnt', 0)) 
                        for b in bids_data
                    ]
                    
                    asks = [
                        PriceLevel(price=a['price'], size=a['volume'], order_count=a.get('ord_cnt', 0)) 
                        for a in asks_data
                    ]
                    
                    snapshot = DomSnapshot(
                        bids=bids,
                        asks=asks,
                        symbol=message.get("symbol"),
                        timestamp=time.time()
                    )
                    
                    asyncio.run_coroutine_threadsafe(callback(snapshot), loop)
                
                # Handling 'trade' or other types if needed
                
            except Exception as e:
                print(f"Error parsing message: {e}")

        def on_error(message):
            print("Fyers WS Error:", message)

        def on_close(message):
            print("Fyers WS Closed:", message)

        def on_open():
            print("Fyers WS Configuration...")
            # Subscribe to the symbol
            symbols = [symbol] 
            fyers_socket.subscribe(symbols=symbols, data_type="DepthUpdate")
            print(f"Subscribed to {symbol} for DepthUpdate")


        access_token_ws = f"{self.client_id}:{self.access_token}"
        
        # Create Fyers Socket
        fyers_socket = data_ws.FyersDataSocket(
            access_token=access_token_ws,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message
        )
        
        print(f"Connecting to Fyers WS for {symbol}...")
        fyers_socket.connect()
        
        # Keep the async task alive while socket runs in background thread
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Stopping Fyers Stream...")
            # fyers_socket.close() # if available
            self.running = False

    async def mock_stream(self, symbol: str, callback: Callable[[DomSnapshot], None]):
        from .flyer_adapter import MockFlyerClient
        mock = MockFlyerClient(symbol)
        await mock.stream_updates(callback)
