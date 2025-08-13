"""
Cache Manager for Market Data
Provides intelligent caching with TTL and fallback mechanisms
"""

import json
import asyncio
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class CacheManager:
    """Intelligent cache manager for market data with TTL support"""
    
    def __init__(self, cache_dir: str = "data/cache/market_data"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Memory cache for frequently accessed data
        self.memory_cache = {}
        
        # Cache TTL settings (in seconds)
        self.ttl_settings = {
            "real_time": 60,      # 1 minute for real-time data
            "indices": 30,        # 30 seconds for indices
            "historical_1d": 3600,  # 1 hour for daily historical
            "historical_intraday": 300,  # 5 minutes for intraday
            "company_info": 86400,  # 24 hours for company info
            "gainers_losers": 300,  # 5 minutes for gainers/losers
            "fii_dii": 3600,      # 1 hour for FII/DII data
            "default": 600        # 10 minutes default
        }
        
        self.logger = logging.getLogger(f"{__name__}.CacheManager")
        
    def _get_cache_key(self, prefix: str, symbol: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        key_parts = [prefix, symbol]
        
        # Add sorted kwargs to key
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
            
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
        
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"
        
    def _is_cache_valid(self, cache_data: Dict, cache_type: str) -> bool:
        """Check if cached data is still valid"""
        try:
            cached_time = datetime.fromisoformat(cache_data.get("cached_at", ""))
            ttl = self.ttl_settings.get(cache_type, self.ttl_settings["default"])
            expiry_time = cached_time + timedelta(seconds=ttl)
            
            return datetime.now() < expiry_time
            
        except Exception as e:
            self.logger.warning(f"Error checking cache validity: {e}")
            return False
            
    async def get(
        self, 
        cache_type: str, 
        symbol: str, 
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Get data from cache if valid"""
        try:
            cache_key = self._get_cache_key(cache_type, symbol, **kwargs)
            
            # Check memory cache first
            if cache_key in self.memory_cache:
                cache_data = self.memory_cache[cache_key]
                if self._is_cache_valid(cache_data, cache_type):
                    self.logger.debug(f"Cache hit (memory) for {cache_type}:{symbol}")
                    return cache_data.get("data")
                else:
                    # Remove expired entry
                    del self.memory_cache[cache_key]
                    
            # Check file cache
            cache_file = self._get_cache_file(cache_key)
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                if self._is_cache_valid(cache_data, cache_type):
                    self.logger.debug(f"Cache hit (file) for {cache_type}:{symbol}")
                    
                    # Store in memory cache for faster access
                    self.memory_cache[cache_key] = cache_data
                    return cache_data.get("data")
                else:
                    # Remove expired file
                    cache_file.unlink()
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading cache for {cache_type}:{symbol}: {e}")
            return None
            
    async def set(
        self, 
        cache_type: str, 
        symbol: str, 
        data: Dict[str, Any], 
        **kwargs
    ) -> bool:
        """Store data in cache"""
        try:
            cache_key = self._get_cache_key(cache_type, symbol, **kwargs)
            
            cache_entry = {
                "cached_at": datetime.now().isoformat(),
                "cache_type": cache_type,
                "symbol": symbol,
                "kwargs": kwargs,
                "data": data
            }
            
            # Store in memory cache
            self.memory_cache[cache_key] = cache_entry
            
            # Store in file cache
            cache_file = self._get_cache_file(cache_key)
            with open(cache_file, 'w') as f:
                json.dump(cache_entry, f, indent=2)
                
            self.logger.debug(f"Cached {cache_type}:{symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching {cache_type}:{symbol}: {e}")
            return False
            
    async def invalidate(self, cache_type: str = None, symbol: str = None):
        """Invalidate cache entries"""
        try:
            if cache_type is None and symbol is None:
                # Clear all cache
                self.memory_cache.clear()
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                self.logger.info("Cleared all cache")
                return
                
            # Clear specific entries
            keys_to_remove = []
            
            for cache_key, cache_data in self.memory_cache.items():
                if (cache_type is None or cache_data.get("cache_type") == cache_type) and \
                   (symbol is None or cache_data.get("symbol") == symbol):
                    keys_to_remove.append(cache_key)
                    
            for key in keys_to_remove:
                del self.memory_cache[key]
                cache_file = self._get_cache_file(key)
                if cache_file.exists():
                    cache_file.unlink()
                    
            self.logger.info(f"Invalidated cache for type={cache_type}, symbol={symbol}")
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache: {e}")
            
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            memory_count = len(self.memory_cache)
            file_count = len(list(self.cache_dir.glob("*.json")))
            
            # Calculate cache sizes
            memory_size = 0
            for cache_data in self.memory_cache.values():
                memory_size += len(json.dumps(cache_data))
                
            file_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
            
            # Cache hit/miss stats by type
            type_stats = {}
            for cache_data in self.memory_cache.values():
                cache_type = cache_data.get("cache_type", "unknown")
                if cache_type not in type_stats:
                    type_stats[cache_type] = 0
                type_stats[cache_type] += 1
                
            return {
                "memory_cache": {
                    "entries": memory_count,
                    "size_bytes": memory_size
                },
                "file_cache": {
                    "entries": file_count,
                    "size_bytes": file_size
                },
                "cache_types": type_stats,
                "ttl_settings": self.ttl_settings
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
            
    async def cleanup_expired(self):
        """Clean up expired cache entries"""
        try:
            cleaned_count = 0
            
            # Clean memory cache
            expired_keys = []
            for cache_key, cache_data in self.memory_cache.items():
                cache_type = cache_data.get("cache_type", "default")
                if not self._is_cache_valid(cache_data, cache_type):
                    expired_keys.append(cache_key)
                    
            for key in expired_keys:
                del self.memory_cache[key]
                cleaned_count += 1
                
            # Clean file cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                        
                    cache_type = cache_data.get("cache_type", "default")
                    if not self._is_cache_valid(cache_data, cache_type):
                        cache_file.unlink()
                        cleaned_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"Error processing cache file {cache_file}: {e}")
                    # Remove corrupted cache files
                    cache_file.unlink()
                    cleaned_count += 1
                    
            self.logger.info(f"Cleaned up {cleaned_count} expired cache entries")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")
            return 0