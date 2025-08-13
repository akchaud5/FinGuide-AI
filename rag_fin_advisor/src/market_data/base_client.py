"""
Base client class for market data APIs
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class BaseMarketDataClient(ABC):
    """Abstract base class for market data clients"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    async def get_real_time_price(self, symbol: str) -> Dict[str, Any]:
        """Get real-time price data for a symbol"""
        pass
        
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical OHLCV data"""
        pass
        
    @abstractmethod
    async def get_market_indices(self) -> Dict[str, Any]:
        """Get major market indices (Nifty, Sensex)"""
        pass
        
    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if Indian markets are currently open"""
        pass
        
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for the specific API"""
        # Remove spaces and convert to uppercase
        symbol = symbol.strip().upper()
        
        # Handle common variations
        if symbol == "NIFTY" or symbol == "NIFTY50":
            return "^NSEI"
        elif symbol == "SENSEX" or symbol == "BSE":
            return "^BSESN"
        elif not symbol.endswith(".NS") and not symbol.startswith("^"):
            # Add .NS suffix for Indian stocks on Yahoo Finance
            return f"{symbol}.NS"
            
        return symbol
        
    def validate_period(self, period: str) -> bool:
        """Validate if period is supported"""
        valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
        return period in valid_periods
        
    def validate_interval(self, interval: str) -> bool:
        """Validate if interval is supported"""
        valid_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
        return interval in valid_intervals