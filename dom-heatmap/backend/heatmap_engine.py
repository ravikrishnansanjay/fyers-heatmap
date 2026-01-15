from collections import defaultdict, deque
import time
from typing import Dict, List
from .models import PriceLevel, Side

class HeatmapEngine:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        # Rolling max liquidity per price level to normalize heat
        self.max_liquidity = 1.0 
        self.history: Dict[float, float] = defaultdict(float) # price -> accumulated/max size
        
        # We can track recent max volume to scale the heat dynamically
        self.recent_volume_window = deque() # (timestamp, volume)

    def update_max_liquidity(self, current_levels: List[PriceLevel]):
        """
        Update the global max liquidity seen in the window to normalize colors.
        """
        now = time.time()
        
        # Prune old history
        while self.recent_volume_window and self.recent_volume_window[0][0] < now - self.window_seconds:
            self.recent_volume_window.popleft()

        current_max = 0
        if current_levels:
            current_max = max(p.size for p in current_levels)
        
        self.recent_volume_window.append((now, current_max))
        
        # Re-evaluate global max in window
        # Optimization: Just take the max of the valid window
        if self.recent_volume_window:
            self.max_liquidity = max(v for t, v in self.recent_volume_window)
        
        if self.max_liquidity == 0:
            self.max_liquidity = 1.0

    def calculate_heat(self, price_levels: List[PriceLevel]) -> List[PriceLevel]:
        """
        Assign heat intensity (0-1) to each level based on current and historical max.
        """
        self.update_max_liquidity(price_levels)
        
        for level in price_levels:
            # Simple linear scaling for now. 
            # Could use log scaling for better visual range on heavy levels.
            heat = level.size / self.max_liquidity
            level.heat_intensity = min(max(heat, 0.0), 1.0)
            
        return price_levels
