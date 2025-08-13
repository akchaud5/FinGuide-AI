"""
Main Market Data API - Unified interface for Indian market data
Combines multiple data sources with intelligent fallbacks
"""

import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging

from .yahoo_client import YahooFinanceClient
from .nse_client import NSEClient
from .data_normalizer import DataNormalizer, NormalizedPrice, NormalizedHistoricalData
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

class IndianMarketDataAPI:
    """
    Unified API for Indian market data with multiple source integration
    Provides intelligent fallbacks and caching
    """
    
    def __init__(self, enable_cache: bool = True):
        self.yahoo_client = YahooFinanceClient()
        self.nse_client = NSEClient()
        self.normalizer = DataNormalizer()
        self.cache_manager = CacheManager() if enable_cache else None
        
        self.logger = logging.getLogger(f"{__name__}.IndianMarketDataAPI")
        
        # Source priority for different data types
        self.source_priority = {
            "real_time": ["nse", "yahoo"],
            "historical": ["yahoo", "nse"],
            "indices": ["nse", "yahoo"],
            "company_info": ["yahoo", "nse"]
        }
        
    async def get_real_time_price(
        self, 
        symbol: str, 
        use_cache: bool = True
    ) -> Optional[NormalizedPrice]:
        """
        Get real-time price with intelligent source fallback
        """
        try:
            # Check cache first
            if use_cache and self.cache_manager:
                cached_data = await self.cache_manager.get("real_time", symbol)
                if cached_data:
                    return self.normalizer.normalize_price_data(cached_data)
                    
            self.logger.info(f"Fetching real-time price for {symbol}")
            
            # Try sources in priority order
            primary_data = None
            fallback_data = None
            
            for source in self.source_priority["real_time"]:
                try:
                    if source == "nse":
                        data = await self.nse_client.get_real_time_price(symbol)
                    elif source == "yahoo":
                        data = await self.yahoo_client.get_real_time_price(symbol)
                    else:
                        continue
                        
                    if data and "error" not in data:
                        if primary_data is None:
                            primary_data = data
                        else:
                            fallback_data = data
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Error from {source} for {symbol}: {e}")
                    continue
                    
            if primary_data:
                # Merge with fallback if available
                if fallback_data:
                    primary_data = self.normalizer.merge_data_sources(primary_data, fallback_data)
                    
                # Cache the result
                if use_cache and self.cache_manager:
                    await self.cache_manager.set("real_time", symbol, primary_data)
                    
                return self.normalizer.normalize_price_data(primary_data)
                
            self.logger.warning(f"No data available for {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting real-time price for {symbol}: {e}")
            return None
            
    async def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1y",
        interval: str = "1d",
        use_cache: bool = True
    ) -> Optional[NormalizedHistoricalData]:
        """
        Get historical data with caching
        """
        try:
            cache_key_params = {"period": period, "interval": interval}
            
            # Check cache first
            if use_cache and self.cache_manager:
                cache_type = "historical_1d" if interval == "1d" else "historical_intraday"
                cached_data = await self.cache_manager.get(cache_type, symbol, **cache_key_params)
                if cached_data:
                    return self.normalizer.normalize_historical_data(cached_data)
                    
            self.logger.info(f"Fetching historical data for {symbol} ({period}, {interval})")
            
            # Try sources in priority order
            for source in self.source_priority["historical"]:
                try:
                    if source == "yahoo":
                        data = await self.yahoo_client.get_historical_data(symbol, period, interval)
                    elif source == "nse":
                        data = await self.nse_client.get_historical_data(symbol, period, interval)
                    else:
                        continue
                        
                    if data and "error" not in data:
                        # Cache the result
                        if use_cache and self.cache_manager:
                            cache_type = "historical_1d" if interval == "1d" else "historical_intraday"
                            await self.cache_manager.set(cache_type, symbol, data, **cache_key_params)
                            
                        return self.normalizer.normalize_historical_data(data)
                        
                except Exception as e:
                    self.logger.warning(f"Error from {source} for historical data {symbol}: {e}")
                    continue
                    
            self.logger.warning(f"No historical data available for {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting historical data for {symbol}: {e}")
            return None
            
    async def get_market_indices(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get major market indices
        """
        try:
            # Check cache first
            if use_cache and self.cache_manager:
                cached_data = await self.cache_manager.get("indices", "ALL_INDICES")
                if cached_data:
                    return self.normalizer.normalize_indices_data(cached_data)
                    
            self.logger.info("Fetching market indices")
            
            # Try sources in priority order
            for source in self.source_priority["indices"]:
                try:
                    if source == "nse":
                        data = await self.nse_client.get_market_indices()
                    elif source == "yahoo":
                        data = await self.yahoo_client.get_market_indices()
                    else:
                        continue
                        
                    if data and "error" not in data:
                        # Cache the result
                        if use_cache and self.cache_manager:
                            await self.cache_manager.set("indices", "ALL_INDICES", data)
                            
                        return self.normalizer.normalize_indices_data(data)
                        
                except Exception as e:
                    self.logger.warning(f"Error from {source} for market indices: {e}")
                    continue
                    
            self.logger.warning("No market indices data available")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting market indices: {e}")
            return None
            
    async def get_top_gainers_losers(self, count: int = 10, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get top gainers and losers
        """
        try:
            cache_key_params = {"count": count}
            
            # Check cache first
            if use_cache and self.cache_manager:
                cached_data = await self.cache_manager.get("gainers_losers", "NIFTY50", **cache_key_params)
                if cached_data:
                    return self.normalizer.normalize_gainers_losers(cached_data)
                    
            self.logger.info(f"Fetching top {count} gainers and losers")
            
            # Try sources (Yahoo Finance is more reliable for this)
            for source in ["yahoo", "nse"]:
                try:
                    if source == "yahoo":
                        data = await self.yahoo_client.get_top_gainers_losers(count)
                    elif source == "nse":
                        data = await self.nse_client.get_top_gainers_losers("NIFTY 50")
                    else:
                        continue
                        
                    if data and "error" not in data:
                        # Cache the result
                        if use_cache and self.cache_manager:
                            await self.cache_manager.set("gainers_losers", "NIFTY50", data, **cache_key_params)
                            
                        return self.normalizer.normalize_gainers_losers(data)
                        
                except Exception as e:
                    self.logger.warning(f"Error from {source} for gainers/losers: {e}")
                    continue
                    
            self.logger.warning("No gainers/losers data available")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting gainers/losers: {e}")
            return None
            
    async def get_fii_dii_data(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get FII/DII investment data (NSE only)
        """
        try:
            # Check cache first
            if use_cache and self.cache_manager:
                cached_data = await self.cache_manager.get("fii_dii", "FII_DII_DATA")
                if cached_data:
                    return cached_data
                    
            self.logger.info("Fetching FII/DII data")
            
            # Only NSE provides this data
            try:
                data = await self.nse_client.get_fii_dii_data()
                
                if data and "error" not in data:
                    # Cache the result
                    if use_cache and self.cache_manager:
                        await self.cache_manager.set("fii_dii", "FII_DII_DATA", data)
                        
                    return data
                    
            except Exception as e:
                self.logger.warning(f"Error getting FII/DII data from NSE: {e}")
                
            self.logger.warning("No FII/DII data available")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting FII/DII data: {e}")
            return None
            
    async def search_symbols(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for stock symbols (basic implementation)
        """
        try:
            # This is a basic implementation
            # In production, you'd want a proper symbol search API
            
            common_stocks = {
                "RELIANCE": "Reliance Industries Limited",
                "TCS": "Tata Consultancy Services Limited",
                "HDFCBANK": "HDFC Bank Limited",
                "ICICIBANK": "ICICI Bank Limited",
                "INFY": "Infosys Limited",
                "HDFC": "Housing Development Finance Corporation Limited",
                "ITC": "ITC Limited",
                "SBIN": "State Bank of India",
                "BHARTIARTL": "Bharti Airtel Limited",
                "KOTAKBANK": "Kotak Mahindra Bank Limited"
            }
            
            query = query.upper()
            results = []
            
            for symbol, name in common_stocks.items():
                if query in symbol or query in name.upper():
                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "type": "equity"
                    })
                    
                if len(results) >= limit:
                    break
                    
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching symbols: {e}")
            return []
            
    async def get_market_status(self) -> Dict[str, Any]:
        """
        Get current market status
        """
        try:
            now = datetime.now()
            is_open = self.yahoo_client.is_market_open()
            
            # Calculate next market open/close times
            if now.weekday() >= 5:  # Weekend
                # Next Monday
                days_until_monday = 7 - now.weekday()
                next_open = (now + timedelta(days=days_until_monday)).replace(hour=9, minute=15, second=0, microsecond=0)
            else:
                if is_open:
                    # Market closes today at 3:30 PM
                    next_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
                    next_event = "market_close"
                    next_time = next_close
                else:
                    # Market opens tomorrow (or today if before 9:15 AM)
                    if now.hour < 9 or (now.hour == 9 and now.minute < 15):
                        # Today
                        next_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
                    else:
                        # Tomorrow
                        next_open = (now + timedelta(days=1)).replace(hour=9, minute=15, second=0, microsecond=0)
                    next_event = "market_open"
                    next_time = next_open
                    
            return {
                "is_open": is_open,
                "current_time": now.isoformat(),
                "market_state": "open" if is_open else "closed",
                "next_event": next_event if 'next_event' in locals() else "market_close",
                "next_event_time": next_time.isoformat() if 'next_time' in locals() else None,
                "trading_hours": "9:15 AM - 3:30 PM IST",
                "trading_days": "Monday - Friday"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market status: {e}")
            return {"error": str(e)}
            
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        """
        if not self.cache_manager:
            return {"error": "Cache is disabled"}
            
        return await self.cache_manager.get_cache_stats()
        
    async def clear_cache(self, cache_type: str = None, symbol: str = None):
        """
        Clear cache
        """
        if not self.cache_manager:
            return {"error": "Cache is disabled"}
            
        await self.cache_manager.invalidate(cache_type, symbol)
        return {"message": "Cache cleared successfully"}
        
    async def cleanup_expired_cache(self):
        """
        Clean up expired cache entries
        """
        if not self.cache_manager:
            return {"error": "Cache is disabled"}
            
        cleaned_count = await self.cache_manager.cleanup_expired()
        return {"cleaned_entries": cleaned_count}
        
    async def close(self):
        """
        Close all connections
        """
        try:
            await self.nse_client.close()
            self.logger.info("Market data API connections closed")
        except Exception as e:
            self.logger.error(f"Error closing connections: {e}")