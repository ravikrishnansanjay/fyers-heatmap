import asyncio
import random
import time
from typing import Callable, List, Dict
from .models import PriceLevel, DomSnapshot, Side

class MockFlyerClient:
    """
    Simulates Level-2 Market Data from Flyer API.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, int] = {}
        self.asks: Dict[float, int] = {}
        self.running = False
        self._initialize_book()

    def _initialize_book(self):
        """Create a realistic initial book"""
        mid_price = 780.0
        # Bids
        for i in range(20):
            price = mid_price - (i * 5)
            self.bids[price] = random.randint(10, 500)
        
        # Asks
        for i in range(20):
            price = mid_price + (i * 5) + 5
            self.asks[price] = random.randint(10, 500)

    async def stream_updates(self, callback: Callable[[DomSnapshot], None]):
        """
        Continuously push updates to the callback.
        """
        self.running = True
        try:
            while self.running:
                # Simulate market changes
                self._simulate_movement()
                
                # Snapshot generation (in real systems, you might send deltas)
                snapshot = self._generate_snapshot()
                await callback(snapshot)
                
                # Update frequency (simulating ~10-50ms latency / 20-100Hz)
                await asyncio.sleep(0.05) 
        except Exception as e:
            print(f"Stream error: {e}")

    def _simulate_movement(self):
        """Randomly modify order book to create 'heat'"""
        # 1. Modify existing levels
        if random.random() > 0.5:
            price = random.choice(list(self.bids.keys()))
            change = random.randint(-50, 50)
            self.bids[price] = max(0, self.bids[price] + change)
            if self.bids[price] == 0:
                del self.bids[price]

        if random.random() > 0.5:
            price = random.choice(list(self.asks.keys()))
            change = random.randint(-50, 50)
            self.asks[price] = max(0, self.asks[price] + change)
            if self.asks[price] == 0:
                del self.asks[price]

        # 2. Add new levels (limit order placement)
        # Occasionally extend the ladder
        if random.random() < 0.1:
            # aggressive bid
            best_bid = max(self.bids.keys()) if self.bids else 22450
            new_bid = best_bid + 5
            # Don't cross spread too easily in mock
            min_ask = min(self.asks.keys()) if self.asks else 22500
            if new_bid < min_ask:
                self.bids[new_bid] = random.randint(100, 300)

    def _generate_snapshot(self) -> DomSnapshot:
        # Sort and take top 20 levels
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:30]
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])[:30]

        bid_levels = [PriceLevel(price=p, size=s, order_count=random.randint(1, 10)) for p, s in sorted_bids]
        ask_levels = [PriceLevel(price=p, size=s, order_count=random.randint(1, 10)) for p, s in sorted_asks]

        return DomSnapshot(
            bids=bid_levels,
            asks=ask_levels,
            symbol=self.symbol,
            timestamp=time.time()
        )

    def stop(self):
        self.running = False
