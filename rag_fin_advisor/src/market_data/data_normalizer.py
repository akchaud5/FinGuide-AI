"""
Data Normalizer for Market Data
Standardizes data formats across different sources
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class DataSource(Enum):
    YAHOO_FINANCE = "yahoo_finance"
    NSE = "nse"
    BSE = "bse"
    UNKNOWN = "unknown"

@dataclass
class NormalizedPrice:
    """Standardized price data structure"""
    symbol: str
    price: float
    change: float
    change_percent: float
    open: float
    high: float
    low: float
    volume: int
    timestamp: str
    source: str
    market_state: str
    previous_close: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    additional_data: Optional[Dict] = None

@dataclass
class NormalizedHistoricalData:
    """Standardized historical data structure"""
    symbol: str
    period: str
    interval: str
    data: List[Dict[str, Any]]
    count: int
    source: str
    timestamp: str

@dataclass
class NormalizedIndices:
    """Standardized market indices structure"""
    indices: Dict[str, Dict[str, Any]]
    timestamp: str
    market_state: str
    source: str

class DataNormalizer:
    """Normalizes market data from different sources into standard formats"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DataNormalizer")
        
        # Symbol mapping for standardization
        self.symbol_mappings = {
            "NIFTY": "NIFTY",
            "NIFTY50": "NIFTY",
            "^NSEI": "NIFTY",
            "NIFTY 50": "NIFTY",
            "SENSEX": "SENSEX",
            "^BSESN": "SENSEX",
            "BANKNIFTY": "BANKNIFTY",
            "NIFTY BANK": "BANKNIFTY",
            "^NSEBANK": "BANKNIFTY"
        }
        
    def normalize_price_data(self, raw_data: Dict[str, Any]) -> Optional[NormalizedPrice]:
        """Normalize price data from any source"""
        try:
            if "error" in raw_data:
                self.logger.warning(f"Error in raw data: {raw_data['error']}")
                return None
                
            source = raw_data.get("source", "unknown")
            
            # Extract common fields with fallbacks
            symbol = self._normalize_symbol(raw_data.get("symbol", ""))
            price = self._safe_float(raw_data.get("price", 0))
            change = self._safe_float(raw_data.get("change", 0))
            change_percent = self._safe_float(raw_data.get("change_percent", 0))
            open_price = self._safe_float(raw_data.get("open", 0))
            high = self._safe_float(raw_data.get("high", 0))
            low = self._safe_float(raw_data.get("low", 0))
            volume = self._safe_int(raw_data.get("volume", 0))
            timestamp = raw_data.get("timestamp", datetime.now().isoformat())
            market_state = raw_data.get("market_state", "unknown")
            
            # Optional fields
            previous_close = self._safe_float(raw_data.get("previous_close"))
            market_cap = self._safe_float(raw_data.get("market_cap"))
            pe_ratio = self._safe_float(raw_data.get("pe_ratio"))
            
            # Additional data (source-specific fields)
            additional_data = {
                k: v for k, v in raw_data.items() 
                if k not in [
                    "symbol", "price", "change", "change_percent", "open", 
                    "high", "low", "volume", "timestamp", "market_state",
                    "previous_close", "market_cap", "pe_ratio", "source"
                ]
            }
            
            return NormalizedPrice(
                symbol=symbol,
                price=price,
                change=change,
                change_percent=change_percent,
                open=open_price,
                high=high,
                low=low,
                volume=volume,
                timestamp=timestamp,
                source=source,
                market_state=market_state,
                previous_close=previous_close,
                market_cap=market_cap,
                pe_ratio=pe_ratio,
                additional_data=additional_data if additional_data else None
            )
            
        except Exception as e:
            self.logger.error(f"Error normalizing price data: {e}")
            return None
            
    def normalize_historical_data(self, raw_data: Dict[str, Any]) -> Optional[NormalizedHistoricalData]:
        """Normalize historical data from any source"""
        try:
            if "error" in raw_data:
                self.logger.warning(f"Error in raw data: {raw_data['error']}")
                return None
                
            symbol = self._normalize_symbol(raw_data.get("symbol", ""))
            period = raw_data.get("period", "unknown")
            interval = raw_data.get("interval", "unknown")
            data = raw_data.get("data", [])
            count = raw_data.get("count", len(data))
            source = raw_data.get("source", "unknown")
            timestamp = raw_data.get("timestamp", datetime.now().isoformat())
            
            # Normalize data points
            normalized_data = []
            for point in data:
                normalized_point = {
                    "timestamp": point.get("timestamp"),
                    "open": self._safe_float(point.get("open", 0)),
                    "high": self._safe_float(point.get("high", 0)),
                    "low": self._safe_float(point.get("low", 0)),
                    "close": self._safe_float(point.get("close", 0)),
                    "volume": self._safe_int(point.get("volume", 0))
                }
                normalized_data.append(normalized_point)
                
            return NormalizedHistoricalData(
                symbol=symbol,
                period=period,
                interval=interval,
                data=normalized_data,
                count=count,
                source=source,
                timestamp=timestamp
            )
            
        except Exception as e:
            self.logger.error(f"Error normalizing historical data: {e}")
            return None
            
    def normalize_indices_data(self, raw_data: Dict[str, Any]) -> Optional[NormalizedIndices]:
        """Normalize market indices data from any source"""
        try:
            if "error" in raw_data:
                self.logger.warning(f"Error in raw data: {raw_data['error']}")
                return None
                
            indices = {}
            raw_indices = raw_data.get("indices", {})
            
            for index_name, index_data in raw_indices.items():
                normalized_name = self._normalize_symbol(index_name)
                
                indices[normalized_name] = {
                    "name": index_data.get("name", normalized_name),
                    "price": self._safe_float(index_data.get("price", 0)),
                    "change": self._safe_float(index_data.get("change", 0)),
                    "change_percent": self._safe_float(index_data.get("change_percent", 0)),
                    "open": self._safe_float(index_data.get("open", 0)),
                    "high": self._safe_float(index_data.get("high", 0)),
                    "low": self._safe_float(index_data.get("low", 0)),
                    "previous_close": self._safe_float(index_data.get("previous_close", 0)),
                    "volume": self._safe_int(index_data.get("volume", 0))
                }
                
            return NormalizedIndices(
                indices=indices,
                timestamp=raw_data.get("timestamp", datetime.now().isoformat()),
                market_state=raw_data.get("market_state", "unknown"),
                source=raw_data.get("source", "unknown")
            )
            
        except Exception as e:
            self.logger.error(f"Error normalizing indices data: {e}")
            return None
            
    def normalize_gainers_losers(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize gainers and losers data"""
        try:
            if "error" in raw_data:
                self.logger.warning(f"Error in raw data: {raw_data['error']}")
                return None
                
            gainers = []
            losers = []
            
            for gainer in raw_data.get("top_gainers", []):
                gainers.append({
                    "symbol": self._normalize_symbol(gainer.get("symbol", "")),
                    "price": self._safe_float(gainer.get("price", 0)),
                    "change": self._safe_float(gainer.get("change", 0)),
                    "change_percent": self._safe_float(gainer.get("change_percent", 0)),
                    "volume": self._safe_int(gainer.get("volume", 0))
                })
                
            for loser in raw_data.get("top_losers", []):
                losers.append({
                    "symbol": self._normalize_symbol(loser.get("symbol", "")),
                    "price": self._safe_float(loser.get("price", 0)),
                    "change": self._safe_float(loser.get("change", 0)),
                    "change_percent": self._safe_float(loser.get("change_percent", 0)),
                    "volume": self._safe_int(loser.get("volume", 0))
                })
                
            return {
                "top_gainers": gainers,
                "top_losers": losers,
                "timestamp": raw_data.get("timestamp", datetime.now().isoformat()),
                "source": raw_data.get("source", "unknown")
            }
            
        except Exception as e:
            self.logger.error(f"Error normalizing gainers/losers data: {e}")
            return None
            
    def merge_data_sources(self, primary_data: Dict, fallback_data: Dict) -> Dict[str, Any]:
        """Merge data from multiple sources, preferring primary source"""
        try:
            if not primary_data or "error" in primary_data:
                return fallback_data
                
            if not fallback_data or "error" in fallback_data:
                return primary_data
                
            # Merge logic: use primary data but fill missing fields from fallback
            merged = primary_data.copy()
            
            for key, value in fallback_data.items():
                if key not in merged or merged[key] is None or merged[key] == 0:
                    merged[key] = value
                    
            # Add source information
            merged["primary_source"] = primary_data.get("source", "unknown")
            merged["fallback_source"] = fallback_data.get("source", "unknown")
            merged["merged"] = True
            
            return merged
            
        except Exception as e:
            self.logger.error(f"Error merging data sources: {e}")
            return primary_data or fallback_data or {}
            
    def validate_data_quality(self, data: Union[NormalizedPrice, NormalizedHistoricalData, Dict]) -> Dict[str, Any]:
        """Validate data quality and return quality metrics"""
        try:
            quality_score = 100
            issues = []
            
            if isinstance(data, NormalizedPrice):
                # Check for zero/missing values
                if data.price <= 0:
                    quality_score -= 30
                    issues.append("Invalid price")
                    
                if data.volume <= 0:
                    quality_score -= 10
                    issues.append("Zero volume")
                    
                if not data.timestamp:
                    quality_score -= 20
                    issues.append("Missing timestamp")
                    
                # Check for reasonable ranges
                if abs(data.change_percent) > 20:  # More than 20% change
                    quality_score -= 5
                    issues.append("High volatility")
                    
            elif isinstance(data, NormalizedHistoricalData):
                # Check data completeness
                if data.count == 0:
                    quality_score = 0
                    issues.append("No historical data")
                elif data.count < 10:
                    quality_score -= 20
                    issues.append("Insufficient data points")
                    
                # Check for data gaps
                timestamps = [point.get("timestamp") for point in data.data if point.get("timestamp")]
                if len(timestamps) < data.count * 0.9:
                    quality_score -= 15
                    issues.append("Missing timestamps")
                    
            return {
                "quality_score": max(0, quality_score),
                "issues": issues,
                "is_valid": quality_score >= 50
            }
            
        except Exception as e:
            self.logger.error(f"Error validating data quality: {e}")
            return {"quality_score": 0, "issues": [f"Validation error: {e}"], "is_valid": False}
            
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to standard format"""
        if not symbol:
            return ""
            
        symbol = symbol.strip().upper()
        
        # Apply symbol mappings
        if symbol in self.symbol_mappings:
            return self.symbol_mappings[symbol]
            
        # Remove common suffixes for standardization
        if symbol.endswith('.NS'):
            symbol = symbol[:-3]
        elif symbol.endswith('.NSE'):
            symbol = symbol[:-4]
        elif symbol.endswith('.BO'):
            symbol = symbol[:-3]
        elif symbol.endswith('.BSE'):
            symbol = symbol[:-4]
            
        return symbol
        
    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float"""
        try:
            if value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
            
    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int"""
        try:
            if value is None:
                return 0
            return int(float(value))  # Convert via float to handle string numbers
        except (ValueError, TypeError):
            return 0