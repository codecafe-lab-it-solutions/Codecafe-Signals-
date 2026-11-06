"""Optical Screen & Chart Analyzer (Pillow + NumPy).

Analyzes screen-shared chart frames to detect:
1. Candlestick dominance (Bullish Green vs Bearish Red)
2. Recent price momentum trajectory (rightmost 25% of canvas)
3. Actionable trading tips (CALL/BUY, PUT/SELL, WAIT) with confidence %
"""
import base64
import io
import numpy as np
from PIL import Image


def analyze_chart_frame(image_bytes: bytes) -> dict:
    """Analyze a captured chart image frame from the browser screen share."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        arr = np.array(img)

        # Focus on the chart area (crop outer 10% margins to avoid browser chrome / tabs)
        chart_top = int(h * 0.10)
        chart_bot = int(h * 0.90)
        chart_left = int(w * 0.05)
        chart_right = int(w * 0.95)
        cropped = arr[chart_top:chart_bot, chart_left:chart_right]

        ch_h, ch_w, _ = cropped.shape

        # Sample colors across chart
        r, g, b = cropped[:, :, 0].astype(int), cropped[:, :, 1].astype(int), cropped[:, :, 2].astype(int)

        # Green candle detection: accepts pure green (0, 230, 118) and teal/mint green (38, 166, 154)
        green_mask = (g > 90) & (g > r * 1.15) & ((g > b * 1.1) | ((g > 140) & (b > 100) & (g >= b)))
        # Red candle detection: accepts red (239, 83, 80) and orange-red (248, 81, 73)
        red_mask = (r > 100) & (r > g * 1.20) & (r > b * 1.20)

        # Focus heavily on the rightmost 25% (latest 3-8 candles)
        recent_w = int(ch_w * 0.25)
        recent_greens = np.sum(green_mask[:, -recent_w:])
        recent_reds = np.sum(red_mask[:, -recent_w:])
        total_recent_candle_px = recent_greens + recent_reds

        # Trajectory estimation: average vertical position of candle pixels over horizontal slices
        x_slices = np.linspace(ch_w - recent_w, ch_w - 5, 8, dtype=int)
        y_centers = []
        for x in x_slices:
            col_mask = green_mask[:, x : x + 4] | red_mask[:, x : x + 4]
            y_indices = np.where(col_mask)[0]
            if len(y_indices) > 5:
                y_centers.append(float(np.mean(y_indices)))

        # Invert Y because pixel 0 is top (higher price = lower Y index)
        slope = 0.0
        if len(y_centers) >= 3:
            slope = -(y_centers[-1] - y_centers[0])  # positive = price rising up

        # Decision Engine
        action = "WAIT"
        confidence = 50
        reasons = []

        if total_recent_candle_px < 30:
            reasons.append("No clear candlestick colors detected on rightmost chart. Make sure chart is visible.")
            confidence = 30
        else:
            green_ratio = recent_greens / total_recent_candle_px
            red_ratio = recent_reds / total_recent_candle_px

            if green_ratio > 0.65 and slope >= 0:
                action = "CALL / BUY"
                confidence = min(92, int(60 + green_ratio * 35))
                reasons.append(f"Strong Bullish momentum: {int(green_ratio*100)}% green candle dominance on recent bars.")
                if slope > 5:
                    reasons.append("Upward price trajectory confirmed.")
            elif red_ratio > 0.65 and slope <= 0:
                action = "PUT / SELL"
                confidence = min(92, int(60 + red_ratio * 35))
                reasons.append(f"Strong Bearish momentum: {int(red_ratio*100)}% red candle dominance on recent bars.")
                if slope < -5:
                    reasons.append("Downward price trajectory confirmed.")
            elif slope > 15:
                action = "CALL / BUY"
                confidence = 72
                reasons.append("Fast upward breakout slope detected.")
            elif slope < -15:
                action = "PUT / SELL"
                confidence = 72
                reasons.append("Fast downward drop slope detected.")
            else:
                reasons.append("Market in consolidation / mixed candles. Wait for clean breakout.")
                confidence = 52

        return {
            "action": action,
            "confidence": confidence,
            "green_ratio": round(float(recent_greens / (total_recent_candle_px or 1)), 2),
            "red_ratio": round(float(recent_reds / (total_recent_candle_px or 1)), 2),
            "slope": round(float(slope), 2),
            "reasons": reasons,
            "tip": (
                "Suggested entry: Next 1-2 candles. Keep risk under 1-2%."
                if action != "WAIT"
                else "Patience: Do not chase choppy markets."
            ),
        }
    except Exception as e:
        return {"action": "WAIT", "confidence": 0, "error": str(e), "reasons": [f"Analysis error: {e}"]}


def decode_base64_image(data_url: str) -> bytes:
    """Extract raw image bytes from data:image/png;base64,... string."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)
