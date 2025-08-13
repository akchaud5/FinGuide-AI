"""
Yahoo Finance API Client for Indian Market Data
"""

import yfinance as yf
import pandas as pd
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from .base_client import BaseMarketDataClient

logger = logging.getLogger(__name__)

class YahooFinanceClient(BaseMarketDataClient):
    """Yahoo Finance client for Indian market data"""
    
    def __init__(self):
        super().__init__("YahooFinance")
        self.session = None
        
        # Indian market symbols mapping
        self.indian_indices = {
            "NIFTY": "^NSEI",
            "NIFTY50": "^NSEI", 
            "SENSEX": "^BSESN",
            "BANKNIFTY": "^NSEBANK",
            "NIFTYIT": "^CNXIT",
            "NIFTYPHARMA": "^CNXPHARMA",
            "NIFTYAUTO": "^CNXAUTO",
            "NIFTYMETAL": "^CNXMETAL",
            "NIFTYREALTY": "^CNXREALTY"
        }
        
    async def get_real_time_price(self, symbol: str) -> Dict[str, Any]:
        """Get real-time price data for Indian stocks/indices"""
        try:
            normalized_symbol = self.normalize_symbol(symbol)
            self.logger.info(f"Fetching real-time data for {normalized_symbol}")
            
            # Use yfinance to get current data
            ticker = yf.Ticker(normalized_symbol)
            info = ticker.info
            
            # Get latest price data
            hist = ticker.history(period="1d", interval="1m")
            if hist.empty:
                raise ValueError(f"No data available for {symbol}")
                
            latest = hist.iloc[-1]
            
            return {
                "symbol": symbol,
                "normalized_symbol": normalized_symbol,
                "price": float(latest['Close']),
                "open": float(latest['Open']),
                "high": float(latest['High']),
                "low": float(latest['Low']),
                "volume": int(latest['Volume']),
                "timestamp": latest.name.isoformat(),
                "currency": info.get("currency", "INR"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "day_change": float(latest['Close'] - latest['Open']),
                "day_change_percent": float(((latest['Close'] - latest['Open']) / latest['Open']) * 100),
                "source": "yahoo_finance",
                "market_state": "open" if self.is_market_open() else "closed"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching real-time data for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
            
    async def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical OHLCV data"""
        try:
            if not self.validate_period(period):
                raise ValueError(f"Invalid period: {period}")
                
            if not self.validate_interval(interval):
                raise ValueError(f"Invalid interval: {interval}")
                
            normalized_symbol = self.normalize_symbol(symbol)
            self.logger.info(f"Fetching historical data for {normalized_symbol}, period={period}, interval={interval}")
            
            ticker = yf.Ticker(normalized_symbol)
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                raise ValueError(f"No historical data available for {symbol}")
                
            # Convert to JSON-serializable format
            data = []
            for timestamp, row in hist.iterrows():
                data.append({
                    "timestamp": timestamp.isoformat(),
                    "open": float(row['Open']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "close": float(row['Close']),
                    "volume": int(row['Volume'])
                })
                
            return {
                "symbol": symbol,
                "normalized_symbol": normalized_symbol,
                "period": period,
                "interval": interval,
                "data": data,
                "count": len(data),
                "source": "yahoo_finance"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
            
    async def get_market_indices(self) -> Dict[str, Any]:
        """Get major Indian market indices"""
        try:
            indices_data = {}
            
            for name, symbol in self.indian_indices.items():
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d", interval="1m")
                    
                    if not hist.empty:
                        latest = hist.iloc[-1]
                        prev_close = ticker.info.get("previousClose", latest['Open'])
                        
                        indices_data[name] = {
                            "symbol": symbol,
                            "price": float(latest['Close']),
                            "change": float(latest['Close'] - prev_close),
                            "change_percent": float(((latest['Close'] - prev_close) / prev_close) * 100),
                            "high": float(latest['High']),
                            "low": float(latest['Low']),
                            "volume": int(latest['Volume']),
                            "timestamp": latest.name.isoformat()
                        }
                        
                except Exception as e:
                    self.logger.warning(f"Failed to fetch data for {name}: {e}")
                    continue
                    
            return {
                "indices": indices_data,
                "timestamp": datetime.now().isoformat(),
                "market_state": "open" if self.is_market_open() else "closed",
                "source": "yahoo_finance"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching market indices: {e}")
            return {"error": str(e)}
            
    def is_market_open(self) -> bool:
        """Check if Indian markets are currently open"""
        now = datetime.now()
        
        # Indian markets are open Monday-Friday, 9:15 AM - 3:30 PM IST
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
            
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
        
    async def get_top_gainers_losers(self, count: int = 10) -> Dict[str, Any]:
        """Get top gainers and losers from Nifty 50"""
        try:
            # Get Nifty 50 constituent symbols
            nifty_symbols = [
                "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
                "INFY.NS", "HDFC.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS",
                "ASIANPAINT.NS", "MARUTI.NS", "BAJFINANCE.NS", "HCLTECH.NS", "AXISBANK.NS",
                "LT.NS", "DMART.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
                "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "TECHM.NS",
                "DIVISLAB.NS", "KOTAKBANK.NS", "TATAMOTORS.NS", "BAJAJFINSV.NS", "M&M.NS",
                "CIPLA.NS", "GRASIM.NS", "BRITANNIA.NS", "COALINDIA.NS", "IOC.NS",
                "EICHERMOT.NS", "DRREDDY.NS", "JSWSTEEL.NS", "BPCL.NS", "ADANIPORTS.NS",
                "HINDALCO.NS", "INDUSINDBK.NS", "TATASTEEL.NS", "HEROMOTOCO.NS", "UPL.NS",
                "BAJAJ-AUTO.NS", "ONGC.NS", "SHREECEM.NS", "TATACONSUM.NS", "APOLLOHOSP.NS"
            ]
            
            stock_data = []
            
            for symbol in nifty_symbols[:20]:  # Limit to avoid rate limits
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="2d", interval="1d")
                    
                    if len(hist) >= 2:
                        current = hist.iloc[-1]
                        previous = hist.iloc[-2]
                        change_percent = ((current['Close'] - previous['Close']) / previous['Close']) * 100
                        
                        stock_data.append({
                            "symbol": symbol.replace('.NS', ''),
                            "price": float(current['Close']),
                            "change_percent": float(change_percent),
                            "volume": int(current['Volume'])
                        })
                        
                except Exception as e:
                    self.logger.warning(f"Failed to fetch data for {symbol}: {e}")
                    continue
                    
            # Sort by change percentage
            stock_data.sort(key=lambda x: x['change_percent'], reverse=True)
            
            return {
                "top_gainers": stock_data[:count],
                "top_losers": stock_data[-count:],
                "timestamp": datetime.now().isoformat(),
                "source": "yahoo_finance"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching gainers/losers: {e}")
            return {"error": str(e)}
            
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Yahoo Finance (add .NS suffix for Indian stocks)"""
        symbol = symbol.strip().upper()
        
        # Check if it's an index
        if symbol in self.indian_indices:
            return self.indian_indices[symbol]
            
        # Add .NS suffix for Indian stocks if not present
        if not symbol.endswith('.NS') and not symbol.startswith('^'):
            return f"{symbol}.NS"
            
        return symbol