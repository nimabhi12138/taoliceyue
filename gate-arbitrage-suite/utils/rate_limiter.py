from typing import Optional
"""
Rate Limiter for Gate.io API
Manages API request rates to avoid hitting limits
"""

import asyncio
import time
from typing import Dict, Optional
from collections import deque
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_second: int = 10
    requests_per_minute: int = 300
    requests_per_hour: int = 10000
    burst_size: int = 20
    
    # Gate.io specific limits
    spot_orders_per_second: int = 5
    perp_orders_per_second: int = 5
    cancel_orders_per_second: int = 10
    
    # Cooldown periods
    rate_limit_cooldown: int = 60  # seconds
    error_429_backoff: int = 120  # seconds


class RateLimiter:
    """
    Thread-safe rate limiter for API requests
    Implements token bucket algorithm with sliding window
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        
        # Request tracking
        self._request_times: deque = deque(maxlen=10000)
        self._order_times: Dict[str, deque] = {
            "spot": deque(maxlen=1000),
            "perp": deque(maxlen=1000),
            "cancel": deque(maxlen=1000)
        }
        
        # Token bucket
        self._tokens = self.config.burst_size
        self._last_refill = time.time()
        
        # Rate limit state
        self._is_rate_limited = False
        self._rate_limit_until = 0
        
        # Metrics
        self._total_requests = 0
        self._rate_limited_count = 0
        self._current_rps = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
    async def acquire(self, request_type: str = "general", weight: int = 1) -> bool:
        """
        Acquire permission to make an API request
        Returns True if request can proceed, False if rate limited
        """
        async with self._lock:
            current_time = time.time()
            
            # Check if in cooldown
            if self._is_rate_limited and current_time < self._rate_limit_until:
                remaining = self._rate_limit_until - current_time
                logger.warning(f"Rate limited for {remaining:.1f}s more")
                return False
                
            # Refill tokens
            self._refill_tokens(current_time)
            
            # Check token availability
            if self._tokens < weight:
                logger.warning(f"No tokens available (need {weight}, have {self._tokens})")
                await self._wait_for_tokens(weight)
                
            # Check rate limits
            if not self._check_rate_limits(current_time, request_type):
                return False
                
            # Consume tokens
            self._tokens -= weight
            
            # Record request
            self._record_request(current_time, request_type)
            
            return True
            
    def _refill_tokens(self, current_time: float):
        """Refill tokens based on elapsed time"""
        elapsed = current_time - self._last_refill
        tokens_to_add = elapsed * self.config.requests_per_second
        
        self._tokens = min(
            self.config.burst_size,
            self._tokens + tokens_to_add
        )
        self._last_refill = current_time
        
    def _check_rate_limits(self, current_time: float, request_type: str) -> bool:
        """Check if request would exceed rate limits"""
        # Clean old requests
        self._clean_old_requests(current_time)
        
        # Check per-second limit
        recent_requests = sum(
            1 for t in self._request_times 
            if current_time - t < 1
        )
        if recent_requests >= self.config.requests_per_second:
            logger.warning(f"Per-second limit reached: {recent_requests}/{self.config.requests_per_second}")
            return False
            
        # Check per-minute limit
        minute_requests = sum(
            1 for t in self._request_times 
            if current_time - t < 60
        )
        if minute_requests >= self.config.requests_per_minute:
            logger.warning(f"Per-minute limit reached: {minute_requests}/{self.config.requests_per_minute}")
            return False
            
        # Check order-specific limits
        if request_type in ["spot_order", "perp_order", "cancel_order"]:
            return self._check_order_limits(current_time, request_type)
            
        return True
        
    def _check_order_limits(self, current_time: float, order_type: str) -> bool:
        """Check order-specific rate limits"""
        limits = {
            "spot_order": self.config.spot_orders_per_second,
            "perp_order": self.config.perp_orders_per_second,
            "cancel_order": self.config.cancel_orders_per_second
        }
        
        if order_type not in limits:
            return True
            
        order_key = order_type.split("_")[0]
        recent_orders = sum(
            1 for t in self._order_times[order_key]
            if current_time - t < 1
        )
        
        limit = limits[order_type]
        if recent_orders >= limit:
            logger.warning(f"{order_type} limit reached: {recent_orders}/{limit}")
            return False
            
        return True
        
    def _record_request(self, current_time: float, request_type: str):
        """Record request timestamp"""
        self._request_times.append(current_time)
        self._total_requests += 1
        
        # Record order-specific requests
        if "order" in request_type:
            order_key = request_type.split("_")[0]
            if order_key in self._order_times:
                self._order_times[order_key].append(current_time)
                
        # Update current RPS
        self._update_rps(current_time)
        
    def _clean_old_requests(self, current_time: float):
        """Remove old request timestamps"""
        # Keep only last hour of requests
        cutoff = current_time - 3600
        
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()
            
        for order_queue in self._order_times.values():
            while order_queue and order_queue[0] < cutoff:
                order_queue.popleft()
                
    def _update_rps(self, current_time: float) -> None:
        """Update current requests per second metric"""
        recent_count = sum(
            1 for t in self._request_times 
            if current_time - t < 1
        )
        self._current_rps = recent_count
        
    async def _wait_for_tokens(self, needed: int) -> None:
        """Wait for tokens to become available"""
        wait_time = needed / self.config.requests_per_second
        logger.info(f"Waiting {wait_time:.2f}s for tokens")
        await asyncio.sleep(wait_time)
        
    def handle_rate_limit_error(self, retry_after: Optional[int] = None):
        """Handle 429 rate limit error from API"""
        self._rate_limited_count += 1
        
        if retry_after:
            self._rate_limit_until = time.time() + retry_after
        else:
            self._rate_limit_until = time.time() + self.config.error_429_backoff
            
        self._is_rate_limited = True
        logger.error(f"Rate limited! Cooling down until {self._rate_limit_until}")
        
    def reset_rate_limit(self):
        """Reset rate limit state"""
        self._is_rate_limited = False
        self._rate_limit_until = 0
        logger.info("Rate limit reset")
        
    def get_metrics(self) -> Dict:
        """Get rate limiter metrics"""
        current_time = time.time()
        
        return {
            "current_rps": self._current_rps,
            "total_requests": self._total_requests,
            "rate_limited_count": self._rate_limited_count,
            "tokens_available": self._tokens,
            "is_rate_limited": self._is_rate_limited,
            "requests_last_minute": sum(
                1 for t in self._request_times 
                if current_time - t < 60
            ),
            "requests_last_hour": len(self._request_times)
        }
        
    async def wait_if_needed(self):
        """Wait if currently rate limited"""
        if self._is_rate_limited:
            wait_time = max(0, self._rate_limit_until - time.time())
            if wait_time > 0:
                logger.info(f"Waiting {wait_time:.1f}s for rate limit cooldown")
                await asyncio.sleep(wait_time)
                self.reset_rate_limit()


# Global rate limiter instance
rate_limiter = RateLimiter()