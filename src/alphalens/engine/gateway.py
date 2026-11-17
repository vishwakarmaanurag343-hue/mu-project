"""High-Frequency Automated Order Routing Gateway & Simulated Execution Bridge."""

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    MICRO_PRICE_PEG = "MICRO_PRICE_PEG"


class OrderStatus(StrEnum):
    NEW = "NEW"
    FILLED = "FILLED"
    REJECTED = "REJECTED"


@dataclass
class ExecutionFill:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    requested_price: float
    fill_price: float
    quantity: float
    slippage_bps: float
    latency_microseconds: int  # Internal execution delay simulation
    timestamp: float
    status: OrderStatus


@dataclass
class PortfolioState:
    cash_inr: float = 1_000_000.0  # ₹10,00,000 initial virtual margin
    holdings: dict[str, float] = field(default_factory=dict)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_trades_executed: int = 0
    recent_fills: list[ExecutionFill] = field(default_factory=list)


class OrderRoutingGateway:
    """Automated Order Execution Gateway with sub-millisecond execution and slippage modeling."""

    def __init__(self, initial_cash: float = 1_000_000.0):
        self.portfolio = PortfolioState(cash_inr=initial_cash)
        self.auto_hft_enabled = False
        self.last_auto_trade_time = 0.0
        self.cooldown_seconds = 2.0  # Prevent spamming orders faster than 2 seconds in test mode

    def set_auto_hft(self, enabled: bool) -> bool:
        self.auto_hft_enabled = enabled
        return self.auto_hft_enabled

    def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType,
        best_bid: float,
        best_ask: float,
        micro_price: float,
        kyles_lambda: float = 0.012,
    ) -> ExecutionFill:
        """Route order with sub-millisecond price slippage and queue placement."""
        t_start = time.perf_counter_ns()
        now = time.time()
        order_id = f"HFT-{uuid.uuid4().hex[:8].upper()}"

        if order_type == OrderType.MICRO_PRICE_PEG:
            target_price = micro_price
        elif order_type == OrderType.LIMIT:
            target_price = best_bid if side == OrderSide.BUY else best_ask
        else:
            target_price = best_ask if side == OrderSide.BUY else best_bid

        # Market Microstructure Slippage Model:
        slippage_bps = max(kyles_lambda * math.sqrt(max(quantity, 1.0)) * 0.5, 0.01)
        slippage_mult = (
            (1.0 + slippage_bps / 10000.0)
            if side == OrderSide.BUY
            else (1.0 - slippage_bps / 10000.0)
        )
        fill_price = round(target_price * slippage_mult, 2)
        total_value = fill_price * quantity

        # Margin check
        if side == OrderSide.BUY and total_value > self.portfolio.cash_inr:
            t_end = time.perf_counter_ns()
            latency_us = int((t_end - t_start) / 1000)
            return ExecutionFill(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                requested_price=target_price,
                fill_price=0.0,
                quantity=quantity,
                slippage_bps=0.0,
                latency_microseconds=latency_us,
                timestamp=now,
                status=OrderStatus.REJECTED,
            )

        # Update Portfolio State
        if side == OrderSide.BUY:
            self.portfolio.cash_inr -= total_value
            self.portfolio.holdings[symbol] = self.portfolio.holdings.get(symbol, 0.0) + quantity
        else:
            current_held = self.portfolio.holdings.get(symbol, 0.0)
            sell_qty = min(quantity, current_held) if current_held > 0 else quantity
            self.portfolio.cash_inr += fill_price * sell_qty
            self.portfolio.holdings[symbol] = current_held - sell_qty

        self.portfolio.total_trades_executed += 1
        t_end = time.perf_counter_ns()
        latency_us = max(int((t_end - t_start) / 1000), 12)  # Benchmark in microseconds

        fill = ExecutionFill(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_price=round(target_price, 2),
            fill_price=fill_price,
            quantity=quantity,
            slippage_bps=round(slippage_bps, 2),
            latency_microseconds=latency_us,
            timestamp=now,
            status=OrderStatus.FILLED,
        )

        self.portfolio.recent_fills.insert(0, fill)
        if len(self.portfolio.recent_fills) > 20:
            self.portfolio.recent_fills.pop()

        return fill


# Singleton gateway instance
gateway = OrderRoutingGateway()
