"""Web Trading Copilot Server (Starlette + Uvicorn).

Serves the Web UI and provides real-time REST endpoints for:
1. Chart frame visual analysis
2. Button coordinate calibration
3. One-click / automated trade execution
4. Real-time news & macro sentiment
"""
import json
import os
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from click_agent import execute_action, load_calibration, save_calibration
from news_scraper import get_market_news_brief
from screen_vision import analyze_chart_frame, decode_base64_image

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_platform", "static")
HTML_FILE = os.path.join(STATIC_DIR, "index.html")


async def index(request):
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Web Trading Copilot UI</h1><p>index.html not found</p>")


async def api_analyze_frame(request):
    try:
        body = await request.json()
        data_url = body.get("image", "")
        if not data_url:
            return JSONResponse({"ok": False, "error": "No image data provided"}, status_code=400)
        img_bytes = decode_base64_image(data_url)
        analysis = analyze_chart_frame(img_bytes)

        # Check if auto-click is enabled and confidence >= 80%
        calib = load_calibration()
        auto_clicked = None
        if calib.get("auto_click_enabled") and analysis["action"] in ("CALL / BUY", "PUT / SELL"):
            if analysis["confidence"] >= 80:
                action_type = "CALL" if "CALL" in analysis["action"] else "PUT"
                auto_clicked = execute_action(action_type, dry_run=False)

        return JSONResponse({"ok": True, "analysis": analysis, "auto_clicked": auto_clicked})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def api_calibrate(request):
    try:
        body = await request.json()
        calib = load_calibration()
        btn_type = body.get("type", "").lower()
        if btn_type in ("call", "put"):
            calib[f"{btn_type}_button"] = {"x": body.get("x"), "y": body.get("y")}
        if "auto_click_enabled" in body:
            calib["auto_click_enabled"] = bool(body["auto_click_enabled"])
        save_calibration(calib)
        return JSONResponse({"ok": True, "calibration": calib})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def api_get_calibration(request):
    return JSONResponse({"ok": True, "calibration": load_calibration()})


async def api_execute_click(request):
    try:
        body = await request.json()
        action = body.get("action", "CALL")
        dry_run = body.get("dry_run", False)
        res = execute_action(action, dry_run=dry_run)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def api_news(request):
    try:
        sym = request.query_params.get("symbol")
        data = get_market_news_brief(sym)
        return JSONResponse({"ok": True, "news": data})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


routes = [
    Route("/", index, methods=["GET"]),
    Route("/api/analyze-frame", api_analyze_frame, methods=["POST"]),
    Route("/api/calibrate", api_calibrate, methods=["POST"]),
    Route("/api/calibration", api_get_calibration, methods=["GET"]),
    Route("/api/execute-click", api_execute_click, methods=["POST"]),
    Route("/api/news", api_news, methods=["GET"]),
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8088))
    print(f"Trading Copilot Web Platform running at: http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

