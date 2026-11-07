"""Central Trading Dashboard API Server (Starlette + Uvicorn + WebSockets).
Provides REST endpoints and real-time WebSocket tick feeds.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import json
import os
import re
from typing import Any
import urllib.parse
import urllib.request
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

import auth
import coach
import paper
from backtester import run_historical_backtest
from broker import OrderRequest, get_broker
from config import TRADING_MODE, WATCHLIST
import db
from intelligence import generate_market_intelligence
from ml_pipeline import predict_barrier_probability, train_barrier_model
from orchestrator import AutonomousTradingOrchestrator
from rag_kb import add_document, get_all_documents, search_knowledge_base
from risk_engine import RiskEngine
from streamer import stream_manager
from universal_data import USER_AGENT, fetch_universal_candles

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
HTML_PATH = os.path.join(WEB_DIR, "index.html")
LOGIN_PATH = os.path.join(WEB_DIR, "login.html")
COOKIE = "yo_session"
PUBLIC = ("/login", "/api/login", "/healthz")

broker = get_broker(TRADING_MODE)
auth.bootstrap()
risk = RiskEngine()
orchestrator = AutonomousTradingOrchestrator(broker=broker, risk_engine=risk)


async def serve_index(request):
    if os.path.exists(HTML_PATH):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h2>Dashboard index.html not found</h2>")


class AuthMiddleware(BaseHTTPMiddleware):
    """Every page and API needs a login. Each login gets its own paper account (paper.USER)."""

    async def dispatch(self, request, call_next):
        if request.url.path in PUBLIC:
            return await call_next(request)
        who = auth.read_token(request.cookies.get(COOKIE))
        if not who:
            if request.url.path.startswith("/api/"):
                return JSONResponse({"error": "Please log in."}, status_code=401)
            return RedirectResponse("/login")
        request.state.user, request.state.role = who
        paper.USER.set(who[0])
        return await call_next(request)


def admin_only(handler):
    async def wrapped(request):
        if request.state.role != "admin":
            return JSONResponse({"error": "Admins only."}, status_code=403)
        if asyncio.iscoroutinefunction(handler):
            return await handler(request)
        return await asyncio.to_thread(handler, request)
    return wrapped


async def login_page(request):
    with open(LOGIN_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


async def api_login(request):
    body = await request.json()
    name = str(body.get("username", "")).strip().lower()
    role = auth.login(name, str(body.get("password", "")))
    if not role:
        await asyncio.sleep(1)  # slows password guessing
        return JSONResponse({"error": "Wrong username or password."}, status_code=401)
    resp = JSONResponse({"ok": True, "user": name, "role": role})
    resp.set_cookie(COOKIE, auth.make_token(name), max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=request.url.scheme == "https")  # https behind Render's proxy via proxy_headers
    return resp


async def api_logout(request):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


async def api_me(request):
    return JSONResponse({"user": request.state.user, "role": request.state.role})


async def api_password(request):
    if request.state.role == "demo":
        return JSONResponse({"error": "The shared demo login can't change its password."}, status_code=403)
    body = await request.json()
    if not auth.login(request.state.user, str(body.get("old", ""))):
        return JSONResponse({"error": "Current password is wrong."}, status_code=400)
    try:
        auth.set_password(request.state.user, str(body.get("new", "")))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"ok": True})


async def api_admin_users(request):
    if request.method == "POST":
        body = await request.json()
        try:
            action, name = body.get("action"), str(body.get("username", "")).strip().lower()
            if action == "create":
                auth.create_user(name, str(body.get("password", "")), body.get("role", "client"))
            elif action == "reset":
                auth.set_password(name, str(body.get("password", "")))
            elif action == "delete":
                if name == request.state.user:
                    raise ValueError("You can't delete your own login.")
                auth.delete_user(name)
            else:
                raise ValueError("action must be create, reset or delete")
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse([{"username": n, "role": u["role"], "created": u.get("created")}
                         for n, u in sorted(auth.users().items())])


async def api_coach(request):
    """Screen coach: one shared screen frame in, one trade plan out."""
    body = await request.json()
    try:
        plan = await asyncio.to_thread(coach.analyze, body["image"], str(body.get("symbol", "")).strip(),
                                       str(body.get("note", "")).strip()[:500])
        return JSONResponse(plan)
    except (ValueError, KeyError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)


async def api_close(request):
    body = await request.json()
    return JSONResponse(asdict(await asyncio.to_thread(broker.close_position, body.get("ticket"))))


async def healthz(request):
    return JSONResponse({"ok": True})


async def ws_live(websocket: WebSocket):
    """Real-time WebSocket tick and status feed."""
    if not auth.read_token(websocket.cookies.get(COOKIE)):
        await websocket.close(code=1008)
        return
    await stream_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive & handle incoming client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        stream_manager.disconnect(websocket)
    except Exception:
        stream_manager.disconnect(websocket)


def api_status(request):  # sync: Starlette runs it in a worker thread
    """System overview, account metrics, and broker position reconciliation."""
    if broker.name == "paper":  # the per-user paper account is the source of truth; the shared DB mixes users
        daily_pnl = paper.daily_pnl()
    else:
        broker.reconcile_positions()
        daily_pnl = db.get_daily_realized_pnl()
    acct = broker.get_account()
    positions = broker.get_positions()
    return JSONResponse({
        "broker": acct.broker,
        "is_demo": acct.is_demo,
        "balance": acct.balance,
        "equity": acct.equity,
        "margin": acct.margin,
        "free_margin": acct.free_margin,
        "currency": acct.currency,
        "daily_realized_pnl": daily_pnl,
        "open_positions_count": len(positions),
        "kill_switch_active": risk.kill_switch_active,
        "watchlist": WATCHLIST,
        "user": request.state.user,
        "role": request.state.role,
    })


def api_intelligence(request):  # sync: Starlette runs it in a worker thread
    """System 1 Market Intelligence report for symbol."""
    sym = request.query_params.get("symbol", WATCHLIST[0])
    tf = request.query_params.get("tf", "H1")
    use_llm = request.query_params.get("llm", "true").lower() == "true"
    report = generate_market_intelligence(sym, tf, use_llm=use_llm)
    return JSONResponse(report)


SYMBOL_RE = re.compile(r"^[A-Za-z0-9.=^&-]{1,24}$")  # Yahoo/Bybit tickers: RELIANCE.NS, EURUSD=X, ^NSEI, BTC-USD


def api_search(request):  # sync: Starlette runs it in a worker thread
    """Find any tradable symbol by name or ticker (Yahoo Finance search)."""
    q = request.query_params.get("q", "").strip()[:40]
    if not q:
        return JSONResponse([])
    url = ("https://query2.finance.yahoo.com/v1/finance/search?quotesCount=8&newsCount=0&q="
           + urllib.parse.quote(q))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=8) as r:
            quotes = json.loads(r.read().decode()).get("quotes", [])
    except Exception as e:
        return JSONResponse({"error": f"Search failed: {e}"}, status_code=502)
    return JSONResponse([{"symbol": x["symbol"], "name": x.get("shortname") or x.get("longname") or "",
                          "exchange": x.get("exchDisp", ""), "type": x.get("quoteType", "")}
                         for x in quotes if x.get("symbol") and SYMBOL_RE.match(x["symbol"])])


def api_scan(request):  # sync: Starlette runs it in a worker thread
    """System 2 Strategy scan across the watchlist, plus the symbol open on the page if it isn't in it."""
    extra = request.query_params.get("extra", "").strip()
    symbols = list(WATCHLIST) + ([extra] if extra and SYMBOL_RE.match(extra) and extra not in WATCHLIST else [])
    results = []
    for s in symbols:
        try:
            res = orchestrator.run_single_cycle(s, execute=False)
            results.append(res)
        except Exception as e:
            results.append({"symbol": s, "error": str(e)})
    return JSONResponse(results)


def api_backtest(request):  # sync: Starlette runs it in a worker thread
    """Historical strategy backtest."""
    sym = request.query_params.get("symbol", WATCHLIST[0])
    tf = request.query_params.get("tf", "H1")
    count = int(request.query_params.get("count", "300"))
    candles = fetch_universal_candles(sym, tf, count=count)
    res = run_historical_backtest(candles)
    return JSONResponse(asdict(res))


def api_positions(request):  # sync: Starlette runs it in a worker thread
    """Active open positions."""
    positions = broker.get_positions()
    return JSONResponse([asdict(p) for p in positions])


def api_history(request):  # sync: Starlette runs it in a worker thread
    """This login's closed paper trades (SL, TP or manual close), newest first."""
    return JSONResponse([t for t in paper.load()["trades"] if t["status"] != "OPEN"][::-1])


def api_trades(request):  # sync: Starlette runs it in a worker thread
    """Trade history from local DB."""
    trades = db.get_open_trades()
    return JSONResponse(trades)


def api_emergency_stop(request):  # sync: Starlette runs it in a worker thread
    """Trigger kill switch and flatten positions."""
    res = orchestrator.emergency_shutdown()
    return JSONResponse(res)


async def api_resume(request):
    """Turn this login's kill switch off again."""
    risk.reset_kill_switch()
    return JSONResponse({"ok": True, "kill_switch_active": False})


async def api_execute(request):
    """Execute approved trade."""
    if risk.kill_switch_active:
        return JSONResponse({"ok": False, "error": "Kill switch is on: press Resume trading first."}, status_code=403)
    try:
        body = await request.json()
        sym = body.get("symbol")
        side = body.get("side")
        qty = float(body.get("qty", 0.01))
        sl = float(body.get("sl", 0.0))
        tp = float(body.get("tp", 0.0)) if body.get("tp") else None
        price = float(body.get("price", 0.0)) if body.get("price") else None

        req = OrderRequest(symbol=sym, side=side, qty=qty, sl=sl, tp=tp, price=price)
        res = await asyncio.to_thread(broker.submit_order, req)
        return JSONResponse(asdict(res))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


# Knowledge Base REST Endpoints
def api_kb(request):  # sync: Starlette runs it in a worker thread
    query = request.query_params.get("q", "")
    if query:
        return JSONResponse(search_knowledge_base(query))
    return JSONResponse(get_all_documents())


# Machine Learning REST Endpoints
def api_ml_predict(request):  # sync: Starlette runs it in a worker thread
    sym = request.query_params.get("symbol", WATCHLIST[0])
    candles = fetch_universal_candles(sym, "H1", count=100)
    res = predict_barrier_probability(candles)
    return JSONResponse(res)


def api_ml_train(request):  # sync: Starlette runs it in a worker thread
    sym = request.query_params.get("symbol", WATCHLIST[0])
    candles = fetch_universal_candles(sym, "H1", count=300)
    eval_res = train_barrier_model(candles)
    return JSONResponse(asdict(eval_res))


@asynccontextmanager
async def lifespan(app):
    # Start live WebSocket tick streaming worker on startup
    stream_task = asyncio.create_task(stream_manager.stream_worker(interval_seconds=3.0))
    yield
    stream_manager.stop()
    stream_task.cancel()


routes = [
    Route("/", serve_index),
    Route("/login", login_page),
    Route("/healthz", healthz),
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/logout", api_logout, methods=["POST"]),
    Route("/api/me", api_me),
    Route("/api/password", api_password, methods=["POST"]),
    Route("/api/admin/users", admin_only(api_admin_users), methods=["GET", "POST"]),
    Route("/api/coach", api_coach, methods=["POST"]),
    Route("/api/close", api_close, methods=["POST"]),
    WebSocketRoute("/ws/live", ws_live),
    Route("/api/status", api_status),
    Route("/api/intelligence", api_intelligence),
    Route("/api/scan", api_scan, methods=["POST", "GET"]),
    Route("/api/backtest", api_backtest),
    Route("/api/positions", api_positions),
    Route("/api/trades", api_trades),
    Route("/api/history", api_history),
    Route("/api/search", api_search),
    Route("/api/emergency_stop", api_emergency_stop, methods=["POST"]),
    Route("/api/resume", api_resume, methods=["POST"]),
    Route("/api/execute", api_execute, methods=["POST"]),
    Route("/api/kb", api_kb),
    Route("/api/ml/predict", api_ml_predict),
    Route("/api/ml/train", admin_only(api_ml_train), methods=["POST"]),
]

middleware = [Middleware(AuthMiddleware)]  # same-origin only: no CORS, so other sites can't use a client's cookie

app = Starlette(debug=False, routes=routes, middleware=middleware, lifespan=lifespan)

if __name__ == "__main__":
    import threading
    import time
    import webbrowser

    def _open_ui():
        time.sleep(1.2)
        webbrowser.open(f"http://127.0.0.1:{port}")

    host = os.getenv("HOST", "127.0.0.1")  # the cloud sets HOST=0.0.0.0; locally stay private
    port = int(os.getenv("PORT", "8765"))
    if host == "127.0.0.1":
        threading.Thread(target=_open_ui, daemon=True).start()
    if not auth.users():
        print("  No logins yet: set ADMIN_USER and ADMIN_PASSWORD in .env, then restart.")
    print("=" * 60)
    print("  CODECAFE SIGNALS — AUTONOMOUS TRADING PLATFORM")
    print(f"  Dashboard URL: http://{host}:{port}")
    print(f"  Active Broker: {TRADING_MODE.upper()}")
    print("  Press Ctrl+C to stop the platform.")
    print("=" * 60)
    uvicorn.run(app, host=host, port=port, log_level="warning", proxy_headers=True, forwarded_allow_ips="*")
