"""
NSE (National Stock Exchange) API Client for Real-time Indian Market Data
"""

import aiohttp
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from .base_client import BaseMarketDataClient

logger = logging.getLogger(__name__)

class NSEClient(BaseMarketDataClient):
    """NSE API client for real-time Indian market data"""
    
    def __init__(self):
        super().__init__("NSE")
        self.base_url = "https://www.nseindia.com/api"
        self.session = None
        
        # NSE headers to mimic browser requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }
        
        # NSE symbol mapping
        self.nse_indices = {
            "NIFTY": "NIFTY 50",
            "NIFTY50": "NIFTY 50",
            "BANKNIFTY": "NIFTY BANK",
            "NIFTYIT": "NIFTY IT",
            "NIFTYPHARMA": "NIFTY PHARMA",
            "NIFTYAUTO": "NIFTY AUTO",
            "NIFTYMETAL": "NIFTY METAL",
            "NIFTYREALTY": "NIFTY REALTY"
        }
        
    async def _get_session(self):
        """Get or create aiohttp session with NSE cookies"""
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=30, limit_per_host=10)
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            # Get NSE cookies by visiting homepage
            try:
                async with self.session.get("https://www.nseindia.com") as response:
                    pass  # Just to get cookies
            except Exception as e:
                self.logger.warning(f"Failed to get NSE cookies: {e}")
                
        return self.session
        
    async def get_real_time_price(self, symbol: str) -> Dict[str, Any]:
        """Get real-time price data from NSE"""
        try:
            session = await self._get_session()
            normalized_symbol = self.normalize_symbol(symbol)
            
            # Try equity quote first
            url = f"{self.base_url}/quote-equity?symbol={normalized_symbol}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'error' not in data:
                        return self._parse_equity_quote(data, symbol)
                        
            # If equity fails, try as index
            if symbol.upper() in self.nse_indices:
                return await self._get_index_data(symbol)
                
            raise ValueError(f"No data available for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error fetching NSE real-time data for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
            
    async def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical data from NSE (limited availability)"""
        try:
            session = await self._get_session()
            normalized_symbol = self.normalize_symbol(symbol)
            
            # NSE provides limited historical data via their chart API
            url = f"{self.base_url}/chart-databyindex"
            params = {
                "index": f"{normalized_symbol}EQN",
                "indices": "true"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_historical_data(data, symbol, period, interval)
                    
            raise ValueError(f"No historical data available for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error fetching NSE historical data for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
            
    async def get_market_indices(self) -> Dict[str, Any]:
        """Get major market indices from NSE"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/allIndices"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_indices_data(data)
                    
            raise ValueError("Failed to fetch market indices")
            
        except Exception as e:
            self.logger.error(f"Error fetching NSE market indices: {e}")
            return {"error": str(e)}
            
    async def get_top_gainers_losers(self, index: str = "NIFTY 50") -> Dict[str, Any]:
        """Get top gainers and losers from NSE"""
        try:
            session = await self._get_session()
            
            # Get gainers
            gainers_url = f"{self.base_url}/equity-stockIndices?index={index.replace(' ', '%20')}"
            losers_url = gainers_url  # Same endpoint provides both
            
            async with session.get(gainers_url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_gainers_losers(data)
                    
            raise ValueError("Failed to fetch gainers/losers")
            
        except Exception as e:
            self.logger.error(f"Error fetching NSE gainers/losers: {e}")
            return {"error": str(e)}
            
    async def get_fii_dii_data(self) -> Dict[str, Any]:
        """Get FII/DII investment data"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/fiidiiTradeReact"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_fii_dii_data(data)
                    
            raise ValueError("Failed to fetch FII/DII data")
            
        except Exception as e:
            self.logger.error(f"Error fetching FII/DII data: {e}")
            return {"error": str(e)}
            
    def _parse_equity_quote(self, data: Dict, original_symbol: str) -> Dict[str, Any]:
        """Parse NSE equity quote response"""
        try:
            info = data.get('info', {})
            price_info = data.get('priceInfo', {})
            
            return {
                "symbol": original_symbol,
                "nse_symbol": info.get('symbol'),
                "company_name": info.get('companyName'),
                "price": float(price_info.get('lastPrice', 0)),
                "change": float(price_info.get('change', 0)),
                "change_percent": float(price_info.get('pChange', 0)),
                "open": float(price_info.get('open', 0)),
                "high": float(price_info.get('intraDayHighLow', {}).get('max', 0)),
                "low": float(price_info.get('intraDayHighLow', {}).get('min', 0)),
                "previous_close": float(price_info.get('previousClose', 0)),
                "volume": int(data.get('securityWiseDP', {}).get('quantityTraded', 0)),
                "value": float(data.get('securityWiseDP', {}).get('turnoverInLakhs', 0)),
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('pe'),
                "pb_ratio": info.get('pb'),
                "dividend_yield": info.get('dividendYield'),
                "timestamp": datetime.now().isoformat(),
                "source": "nse",
                "market_state": "open" if self.is_market_open() else "closed"
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing equity quote: {e}")
            return {"error": f"Failed to parse equity data: {e}"}
            
    async def _get_index_data(self, symbol: str) -> Dict[str, Any]:
        """Get index data from NSE"""
        try:
            session = await self._get_session()
            index_name = self.nse_indices.get(symbol.upper(), symbol)
            
            url = f"{self.base_url}/equity-stockIndices?index={index_name.replace(' ', '%20')}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Find the main index data
                    for item in data.get('data', []):
                        if item.get('index') == index_name:
                            return {
                                "symbol": symbol,
                                "index_name": index_name,
                                "price": float(item.get('last', 0)),
                                "change": float(item.get('variation', 0)),
                                "change_percent": float(item.get('percentChange', 0)),
                                "open": float(item.get('open', 0)),
                                "high": float(item.get('dayHigh', 0)),
                                "low": float(item.get('dayLow', 0)),
                                "previous_close": float(item.get('previousClose', 0)),
                                "timestamp": datetime.now().isoformat(),
                                "source": "nse",
                                "market_state": "open" if self.is_market_open() else "closed"
                            }
                            
            raise ValueError(f"Index {index_name} not found")
            
        except Exception as e:
            self.logger.error(f"Error fetching index data: {e}")
            return {"error": str(e)}
            
    def _parse_indices_data(self, data: Dict) -> Dict[str, Any]:
        """Parse NSE indices data"""
        try:
            indices = {}
            
            for item in data.get('data', []):
                index_name = item.get('index', '')
                if index_name in ['NIFTY 50', 'NIFTY BANK', 'NIFTY IT', 'NIFTY PHARMA']:
                    indices[index_name.replace(' ', '_').upper()] = {
                        "name": index_name,
                        "price": float(item.get('last', 0)),
                        "change": float(item.get('variation', 0)),
                        "change_percent": float(item.get('percentChange', 0)),
                        "open": float(item.get('open', 0)),
                        "high": float(item.get('dayHigh', 0)),
                        "low": float(item.get('dayLow', 0)),
                        "previous_close": float(item.get('previousClose', 0))
                    }
                    
            return {
                "indices": indices,
                "timestamp": datetime.now().isoformat(),
                "market_state": "open" if self.is_market_open() else "closed",
                "source": "nse"
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing indices data: {e}")
            return {"error": str(e)}
            
    def _parse_gainers_losers(self, data: Dict) -> Dict[str, Any]:
        """Parse gainers and losers data"""
        try:
            stocks = data.get('data', [])
            
            # Sort by percentage change
            sorted_stocks = sorted(stocks, key=lambda x: float(x.get('pChange', 0)), reverse=True)
            
            gainers = []
            losers = []
            
            for stock in sorted_stocks[:10]:  # Top 10 gainers
                gainers.append({
                    "symbol": stock.get('symbol'),
                    "price": float(stock.get('lastPrice', 0)),
                    "change_percent": float(stock.get('pChange', 0)),
                    "change": float(stock.get('change', 0))
                })
                
            for stock in sorted_stocks[-10:]:  # Top 10 losers
                losers.append({
                    "symbol": stock.get('symbol'),
                    "price": float(stock.get('lastPrice', 0)),
                    "change_percent": float(stock.get('pChange', 0)),
                    "change": float(stock.get('change', 0))
                })
                
            return {
                "top_gainers": gainers,
                "top_losers": list(reversed(losers)),
                "timestamp": datetime.now().isoformat(),
                "source": "nse"
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing gainers/losers: {e}")
            return {"error": str(e)}
            
    def _parse_fii_dii_data(self, data: Dict) -> Dict[str, Any]:
        """Parse FII/DII investment data"""
        try:
            # Extract FII/DII data from NSE response
            fii_data = {}
            dii_data = {}
            
            # Parse the response structure (varies by NSE API changes)
            if isinstance(data, list) and len(data) > 0:
                latest = data[0]
                fii_data = {
                    "date": latest.get('date'),
                    "equity_buy": latest.get('fii_equity_buy', 0),
                    "equity_sell": latest.get('fii_equity_sell', 0),
                    "equity_net": latest.get('fii_equity_net', 0),
                    "debt_buy": latest.get('fii_debt_buy', 0),
                    "debt_sell": latest.get('fii_debt_sell', 0),
                    "debt_net": latest.get('fii_debt_net', 0)
                }
                
                dii_data = {
                    "date": latest.get('date'),
                    "equity_buy": latest.get('dii_equity_buy', 0),
                    "equity_sell": latest.get('dii_equity_sell', 0),
                    "equity_net": latest.get('dii_equity_net', 0)
                }
                
            return {
                "fii": fii_data,
                "dii": dii_data,
                "timestamp": datetime.now().isoformat(),
                "source": "nse"
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing FII/DII data: {e}")
            return {"error": str(e)}
            
    def _parse_historical_data(self, data: Dict, symbol: str, period: str, interval: str) -> Dict[str, Any]:
        """Parse NSE historical data (limited)"""
        try:
            # NSE provides limited historical data
            chart_data = data.get('grapthData', [])
            
            parsed_data = []
            for item in chart_data:
                parsed_data.append({
                    "timestamp": item[0],  # Unix timestamp
                    "price": float(item[1])
                })
                
            return {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "data": parsed_data,
                "count": len(parsed_data),
                "source": "nse",
                "note": "NSE provides limited historical data"
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing historical data: {e}")
            return {"error": str(e)}
            
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for NSE API"""
        symbol = symbol.strip().upper()
        
        # Remove common suffixes
        if symbol.endswith('.NS'):
            symbol = symbol[:-3]
        elif symbol.endswith('.NSE'):
            symbol = symbol[:-4]
            
        return symbol
        
    def is_market_open(self) -> bool:
        """Check if Indian markets are currently open"""
        now = datetime.now()
        
        # Indian markets are open Monday-Friday, 9:15 AM - 3:30 PM IST
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
            
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
        
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None