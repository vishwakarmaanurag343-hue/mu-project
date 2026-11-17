"""High-Frequency Market Microstructure Engine.

Calculates real-time order book metrics:
1. Level 2 (5-level) Order Book Depth Ladder
2. Volume-Weighted Micro-Price (P_micro)
3. Order Flow Imbalance (OFI) over rolling sub-second windows
4. Spread dynamics (Effective & Relative Spread in bps)
5. Short-term Order Pressure Signal (Immediate Buy/Sell imbalance)
"""

import time
from dataclasses import dataclass, field


@dataclass
class OrderBookLevel:
    price: float
    size: float


@dataclass
class MicrostructureMetrics:
    timestamp: float
    best_bid: float
    best_ask: float
    mid_price: float
    micro_price: float
    spread_abs: float
    spread_bps: float
    total_bid_depth: float
    total_ask_depth: float
    imbalance_ratio: float  # -1.0 (all ask) to +1.0 (all bid)
    ofi_score: float  # Order Flow Imbalance
    pressure_label: str  # "STRONG BUY PRESSURE", "NEUTRAL", "STRONG SELL PRESSURE"
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)


class MicrostructureEngine:
    """Processes Level-2 depth updates and computes sub-second microstructure indicators."""

    def __init__(self, ofi_decay: float = 0.85):
        self.ofi_decay = ofi_decay
        self.prev_best_bid = 0.0
        self.prev_best_ask = 0.0
        self.prev_bid_size = 0.0
        self.prev_ask_size = 0.0
        self.rolling_ofi = 0.0

    def process_depth(
        self,
        raw_bids: list[list[str | float]],
        raw_asks: list[list[str | float]],
    ) -> MicrostructureMetrics:
        """Process incoming 5-level bids and asks and compute high-frequency indicators."""
        now = time.time()

        parsed_bids = [
            OrderBookLevel(price=float(b[0]), size=float(b[1]))
            for b in raw_bids[:5]
        ]
        parsed_asks = [
            OrderBookLevel(price=float(a[0]), size=float(a[1]))
            for a in raw_asks[:5]
        ]

        if not parsed_bids or not parsed_asks:
            raise ValueError("Empty bids or asks")

        best_bid = parsed_bids[0].price
        best_ask = parsed_asks[0].price
        bid_size_top = parsed_bids[0].size
        ask_size_top = parsed_asks[0].size

        mid_price = (best_bid + best_ask) / 2.0
        spread_abs = max(best_ask - best_bid, 0.0)
        spread_bps = (spread_abs / mid_price) * 10000.0 if mid_price > 0 else 0.0

        # Micro-Price (Volume-Weighted Midpoint: weights best bid by ask size and vice versa)
        total_top_size = bid_size_top + ask_size_top
        if total_top_size > 0:
            micro_price = (best_bid * ask_size_top + best_ask * bid_size_top) / total_top_size
        else:
            micro_price = mid_price

        # Total 5-level depth
        total_bid_depth = sum(b.size for b in parsed_bids)
        total_ask_depth = sum(a.size for a in parsed_asks)
        total_depth = total_bid_depth + total_ask_depth

        imbalance_ratio = 0.0
        if total_depth > 0:
            imbalance_ratio = (total_bid_depth - total_ask_depth) / total_depth

        # Order Flow Imbalance (OFI) calculation (Cont, Kukanov & Stoikov 2014)
        delta_bid = 0.0
        if best_bid > self.prev_best_bid:
            delta_bid = bid_size_top
        elif best_bid == self.prev_best_bid:
            delta_bid = bid_size_top - self.prev_bid_size
        else:
            delta_bid = -self.prev_bid_size

        delta_ask = 0.0
        if best_ask < self.prev_best_ask:
            delta_ask = ask_size_top
        elif best_ask == self.prev_best_ask:
            delta_ask = ask_size_top - self.prev_ask_size
        else:
            delta_ask = -self.prev_ask_size

        instant_ofi = delta_bid - delta_ask
        self.rolling_ofi = (self.rolling_ofi * self.ofi_decay) + (instant_ofi * (1.0 - self.ofi_decay))

        # Update historical references
        self.prev_best_bid = best_bid
        self.prev_best_ask = best_ask
        self.prev_bid_size = bid_size_top
        self.prev_ask_size = ask_size_top

        # Real-time directional pressure classification
        if imbalance_ratio > 0.35 and self.rolling_ofi > 0:
            pressure = "STRONG BUY PRESSURE"
        elif imbalance_ratio > 0.15:
            pressure = "MODERATE BUY PRESSURE"
        elif imbalance_ratio < -0.35 and self.rolling_ofi < 0:
            pressure = "STRONG SELL PRESSURE"
        elif imbalance_ratio < -0.15:
            pressure = "MODERATE SELL PRESSURE"
        else:
            pressure = "BALANCED BOOK"

        return MicrostructureMetrics(
            timestamp=now,
            best_bid=round(best_bid, 4),
            best_ask=round(best_ask, 4),
            mid_price=round(mid_price, 4),
            micro_price=round(micro_price, 4),
            spread_abs=round(spread_abs, 4),
            spread_bps=round(spread_bps, 2),
            total_bid_depth=round(total_bid_depth, 4),
            total_ask_depth=round(total_ask_depth, 4),
            imbalance_ratio=round(imbalance_ratio, 4),
            ofi_score=round(self.rolling_ofi, 4),
            pressure_label=pressure,
            bids=parsed_bids,
            asks=parsed_asks,
        )
