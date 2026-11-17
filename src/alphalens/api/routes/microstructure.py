"""FastAPI WebSocket & REST endpoints for sub-second real-time market microstructure & automated execution."""

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from alphalens.engine.gateway import OrderSide, OrderType, gateway
from alphalens.engine.microstructure import MicrostructureEngine

logger = logging.getLogger("alphalens.api.microstructure")
router = APIRouter(prefix="/api/microstructure", tags=["microstructure"])


class ManualOrderPayload(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    order_type: str = "MICRO_PRICE_PEG"  # "MARKET", "LIMIT", "MICRO_PRICE_PEG"
    best_bid: float
    best_ask: float
    micro_price: float


class AutoHFTTogglePayload(BaseModel):
    enabled: bool


@router.get("/portfolio")
async def get_hft_portfolio() -> dict:
    """Return live HFT simulated margin, holdings, and recent execution fills."""
    return asdict(gateway.portfolio)


@router.post("/auto-toggle")
async def toggle_auto_hft(payload: AutoHFTTogglePayload) -> dict:
    """Toggle the automated sub-second microstructure order execution trigger."""
    gateway.set_auto_hft(payload.enabled)
    return {"auto_hft_enabled": gateway.auto_hft_enabled}


@router.post("/order")
async def route_manual_order(payload: ManualOrderPayload) -> dict:
    """Route an order directly through the high-frequency matching gateway."""
    side = OrderSide.BUY if payload.side.upper() == "BUY" else OrderSide.SELL
    order_type = OrderType.MICRO_PRICE_PEG
    if payload.order_type.upper() == "MARKET":
        order_type = OrderType.MARKET
    elif payload.order_type.upper() == "LIMIT":
        order_type = OrderType.LIMIT

    fill = gateway.execute_order(
        symbol=payload.symbol,
        side=side,
        quantity=payload.quantity,
        order_type=order_type,
        best_bid=payload.best_bid,
        best_ask=payload.best_ask,
        micro_price=payload.micro_price,
    )
    return asdict(fill)


@router.websocket("/ws")
async def microstructure_stream(websocket: WebSocket) -> None:
    """Stream live 100ms L2 order book depth ladder, OFI, micro-price, and auto-exec fills."""
    await websocket.accept()
    engine = MicrostructureEngine()

    # Binance free 100ms L2 top-5 depth feed
    binance_uri = "wss://stream.binance.com:9443/ws/btcusdt@depth5@100ms"

    try:
        async with websockets.connect(binance_uri, ping_interval=20, ping_timeout=10) as ext_ws:
            while True:
                try:
                    raw_msg = await asyncio.wait_for(ext_ws.recv(), timeout=2.0)
                    data = json.loads(raw_msg)
                    bids = data.get("bids", [])
                    asks = data.get("asks", [])

                    if bids and asks:
                        metrics = engine.process_depth(bids, asks)
                        metric_dict = asdict(metrics)

                        # Check if Automated HFT execution trigger is active
                        if gateway.auto_hft_enabled:
                            import time

                            now = time.time()
                            if (now - gateway.last_auto_trade_time) > gateway.cooldown_seconds:
                                # Trigger rule: OFI > 0.35 + Buy Pressure => Buy Peg Order
                                if (
                                    metrics.pressure_label == "STRONG BUY PRESSURE"
                                    and metrics.imbalance_ratio > 0.35
                                ):
                                    gateway.last_auto_trade_time = now
                                    gateway.execute_order(
                                        symbol="BTC/USDT",
                                        side=OrderSide.BUY,
                                        quantity=0.01,
                                        order_type=OrderType.MICRO_PRICE_PEG,
                                        best_bid=metrics.best_bid,
                                        best_ask=metrics.best_ask,
                                        micro_price=metrics.micro_price,
                                    )
                                elif (
                                    metrics.pressure_label == "STRONG SELL PRESSURE"
                                    and metrics.imbalance_ratio < -0.35
                                ):
                                    gateway.last_auto_trade_time = now
                                    gateway.execute_order(
                                        symbol="BTC/USDT",
                                        side=OrderSide.SELL,
                                        quantity=0.01,
                                        order_type=OrderType.MICRO_PRICE_PEG,
                                        best_bid=metrics.best_bid,
                                        best_ask=metrics.best_ask,
                                        micro_price=metrics.micro_price,
                                    )

                        metric_dict["auto_hft_enabled"] = gateway.auto_hft_enabled
                        metric_dict["portfolio"] = asdict(gateway.portfolio)
                        await websocket.send_text(json.dumps(metric_dict))
                except TimeoutError:
                    continue
                except WebSocketDisconnect:
                    break
    except Exception as e:
        logger.warning("Microstructure WebSocket disconnected: %s", e)
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
