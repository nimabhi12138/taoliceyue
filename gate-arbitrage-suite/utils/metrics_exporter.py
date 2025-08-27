"""
Prometheus Metrics Exporter for Gate.io Arbitrage Suite
Exports trading metrics for monitoring
"""

from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, generate_latest
from typing import Dict, Any
import time
import logging

logger = logging.getLogger(__name__)

# Create registry
registry = CollectorRegistry()

# Define metrics
class Metrics:
    """Prometheus metrics for arbitrage suite"""
    
    # Trading metrics
    total_trades = Counter(
        'arbitrage_total_trades',
        'Total number of trades executed',
        ['strategy', 'symbol', 'side'],
        registry=registry
    )
    
    successful_trades = Counter(
        'arbitrage_successful_trades',
        'Number of successful trades',
        ['strategy'],
        registry=registry
    )
    
    failed_trades = Counter(
        'arbitrage_failed_trades',
        'Number of failed trades',
        ['strategy', 'reason'],
        registry=registry
    )
    
    # PnL metrics
    session_pnl = Gauge(
        'arbitrage_session_pnl',
        'Current session PnL in USD',
        ['strategy'],
        registry=registry
    )
    
    total_pnl = Gauge(
        'arbitrage_total_pnl',
        'Total PnL in USD',
        registry=registry
    )
    
    # Position metrics
    active_positions = Gauge(
        'arbitrage_active_positions',
        'Number of active positions',
        ['strategy', 'symbol'],
        registry=registry
    )
    
    position_value = Gauge(
        'arbitrage_position_value',
        'Total position value in USD',
        ['strategy'],
        registry=registry
    )
    
    # Risk metrics
    circuit_breaker_triggered = Gauge(
        'arbitrage_circuit_breaker_triggered',
        'Circuit breaker status (1=triggered, 0=normal)',
        registry=registry
    )
    
    max_drawdown = Gauge(
        'arbitrage_max_drawdown',
        'Maximum drawdown in USD',
        registry=registry
    )
    
    # Execution metrics
    order_latency = Histogram(
        'arbitrage_order_latency_seconds',
        'Order execution latency',
        ['exchange', 'order_type'],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry
    )
    
    slippage_bps = Summary(
        'arbitrage_slippage_bps',
        'Slippage in basis points',
        ['strategy', 'symbol'],
        registry=registry
    )
    
    # API metrics
    api_requests = Counter(
        'gate_api_requests_total',
        'Total API requests',
        ['endpoint', 'method', 'status'],
        registry=registry
    )
    
    api_request_duration = Histogram(
        'gate_api_request_duration_seconds',
        'API request duration',
        ['endpoint', 'method'],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
        registry=registry
    )
    
    api_rate_limit_hits = Counter(
        'gate_api_rate_limit_hits',
        'Number of rate limit hits',
        ['endpoint'],
        registry=registry
    )
    
    # Balance metrics
    account_balance = Gauge(
        'account_balance',
        'Account balance',
        ['asset', 'exchange'],
        registry=registry
    )
    
    # Opportunity metrics
    opportunities_found = Counter(
        'arbitrage_opportunities_found',
        'Number of arbitrage opportunities found',
        ['strategy', 'profitable'],
        registry=registry
    )
    
    opportunity_profit_bps = Summary(
        'arbitrage_opportunity_profit_bps',
        'Profit of found opportunities in bps',
        ['strategy'],
        registry=registry
    )
    
    # Funding rate metrics (for perps)
    funding_rate = Gauge(
        'funding_rate_8h',
        '8-hour funding rate',
        ['symbol'],
        registry=registry
    )
    
    # System metrics
    errors = Counter(
        'errors_total',
        'Total errors',
        ['component', 'severity'],
        registry=registry
    )
    
    # Performance metrics
    strategy_performance = Gauge(
        'strategy_performance_score',
        'Strategy performance score (0-100)',
        ['strategy'],
        registry=registry
    )


# Global metrics instance
metrics = Metrics()


class MetricsExporter:
    """Export metrics to Prometheus"""
    
    def __init__(self):
        self.metrics = metrics
        self._last_export = time.time()
        
    def record_trade(self, strategy: str, symbol: str, side: str, 
                     success: bool, pnl: float = 0):
        """Record a trade execution"""
        self.metrics.total_trades.labels(
            strategy=strategy,
            symbol=symbol,
            side=side
        ).inc()
        
        if success:
            self.metrics.successful_trades.labels(strategy=strategy).inc()
        else:
            self.metrics.failed_trades.labels(
                strategy=strategy,
                reason="execution_failed"
            ).inc()
            
    def update_pnl(self, strategy: str, session_pnl: float, total_pnl: float):
        """Update PnL metrics"""
        self.metrics.session_pnl.labels(strategy=strategy).set(session_pnl)
        self.metrics.total_pnl.set(total_pnl)
        
    def update_positions(self, strategy: str, positions: Dict[str, int]):
        """Update position metrics"""
        for symbol, count in positions.items():
            self.metrics.active_positions.labels(
                strategy=strategy,
                symbol=symbol
            ).set(count)
            
    def record_order_latency(self, exchange: str, order_type: str, latency: float):
        """Record order execution latency"""
        self.metrics.order_latency.labels(
            exchange=exchange,
            order_type=order_type
        ).observe(latency)
        
    def record_slippage(self, strategy: str, symbol: str, slippage_bps: float):
        """Record slippage"""
        self.metrics.slippage_bps.labels(
            strategy=strategy,
            symbol=symbol
        ).observe(slippage_bps)
        
    def record_api_request(self, endpoint: str, method: str, 
                          status: int, duration: float):
        """Record API request metrics"""
        self.metrics.api_requests.labels(
            endpoint=endpoint,
            method=method,
            status=str(status)
        ).inc()
        
        self.metrics.api_request_duration.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
        
        if status == 429:
            self.metrics.api_rate_limit_hits.labels(endpoint=endpoint).inc()
            
    def update_balance(self, asset: str, exchange: str, balance: float):
        """Update balance metrics"""
        self.metrics.account_balance.labels(
            asset=asset,
            exchange=exchange
        ).set(balance)
        
    def record_opportunity(self, strategy: str, profitable: bool, 
                          profit_bps: float = 0):
        """Record found arbitrage opportunity"""
        self.metrics.opportunities_found.labels(
            strategy=strategy,
            profitable=str(profitable)
        ).inc()
        
        if profitable:
            self.metrics.opportunity_profit_bps.labels(
                strategy=strategy
            ).observe(profit_bps)
            
    def update_funding_rate(self, symbol: str, rate: float):
        """Update funding rate metric"""
        self.metrics.funding_rate.labels(symbol=symbol).set(rate)
        
    def record_error(self, component: str, severity: str = "error"):
        """Record an error"""
        self.metrics.errors.labels(
            component=component,
            severity=severity
        ).inc()
        
    def update_circuit_breaker(self, triggered: bool):
        """Update circuit breaker status"""
        self.metrics.circuit_breaker_triggered.set(1 if triggered else 0)
        
    def update_drawdown(self, drawdown: float):
        """Update maximum drawdown"""
        self.metrics.max_drawdown.set(abs(drawdown))
        
    def calculate_performance_score(self, strategy: str, 
                                   win_rate: float, 
                                   sharpe_ratio: float,
                                   pnl: float) -> float:
        """Calculate and update strategy performance score"""
        # Simple scoring: 40% win rate, 30% sharpe, 30% pnl
        score = (
            min(win_rate * 100, 40) +  # Cap at 40
            min(sharpe_ratio * 10, 30) +  # Cap at 30
            min(max(pnl / 100, 0), 30)  # Cap at 30
        )
        
        self.metrics.strategy_performance.labels(strategy=strategy).set(score)
        return score
        
    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format"""
        return generate_latest(registry)
        
    def export_to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary for logging"""
        # This would parse the Prometheus format back to dict
        # Simplified version:
        return {
            "total_trades": self.metrics.total_trades._value._value,
            "session_pnl": self.metrics.session_pnl._value._value,
            "active_positions": self.metrics.active_positions._value._value,
            "circuit_breaker": self.metrics.circuit_breaker_triggered._value,
            "timestamp": time.time()
        }


# Global exporter instance
metrics_exporter = MetricsExporter()