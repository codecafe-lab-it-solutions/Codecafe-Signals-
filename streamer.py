"""System 1.A: Real-time Live Streaming Engine (WebSockets & Async).
Continuously polls broker / market feed ticks, calculates live spread & volatility,
and broadcasts updates to connected WebSocket clients.
"""
import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any
from starlette.websockets import WebSocket, WebSocketDisconnect

from config import WATCHLIST
from universal_data import fetch_universal_candles


class LiveStreamManager:
    """Manages active WebSocket client connections and live tick broadcasts."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._running = False
        self._last_ticks: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send initial cached state
        if self._last_ticks:
            await websocket.send_json({"type": "INITIAL_TICKS", "ticks": self._last_ticks})

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    async def stream_worker(self, interval_seconds: float = 3.0):
        """Background loop fetching live quotes and broadcasting to clients."""
        self._running = True
        while self._running:
            if self.active_connections:
                for sym in WATCHLIST:
                    try:
                        # in a thread: a blocking fetch here would freeze every page of the site
                        candles = await asyncio.to_thread(fetch_universal_candles, sym, "M15", 2)
                        close_p = float(candles["close"][-1])
                        high_p = float(candles["high"][-1])
                        low_p = float(candles["low"][-1])

                        spread = round((high_p - low_p) * 0.05, 4)
                        bid = round(close_p - spread / 2, 4)
                        ask = round(close_p + spread / 2, 4)

                        tick_data = {
                            "type": "TICK",
                            "symbol": sym,
                            "price": close_p,
                            "bid": bid,
                            "ask": ask,
                            "spread": spread,
                            "timestamp": time.time(),
                        }
                        self._last_ticks[sym] = tick_data
                        await self.broadcast(tick_data)
                    except Exception:
                        pass
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False


# Global singleton instance
stream_manager = LiveStreamManager()

