"""Explicit opt-in live probe. Sends generated pictures only; no business data."""
import argparse
import asyncio
import base64
from datetime import UTC, datetime
import io
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from app.config import get_settings
from app.services.ai_provider import get_llm_provider
from app.services.investigation_vision import semantic_analysis


async def probe():
    nonce = secrets.token_hex(3).upper()
    image = Image.new("RGB", (512, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.text((35, 80), nonce, fill="black", font_size=60)
    draw.ellipse((370, 70, 470, 170), fill="red")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    provider = get_llm_provider()
    report = {"at": datetime.now(UTC).isoformat(), "model": get_settings().ai_model,
              "data_kind": "generated_probe_not_agriculture_validation", "passed": False}
    try:
        reply = await provider.chat([{"role": "user", "content": [
            {"type": "text", "text": 'Read the six-character code in the image. Return only JSON {"code":"..."}.'},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode()}}
        ]}], [])
        raw = (reply.get("content") or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        report["image_challenge_passed"] = json.loads(raw).get("code") == nonce
        report["challenge_usage"] = getattr(provider, "last_usage", {})
        # The production structured symptom adapter must also actually accept images.
        features = await semantic_analysis(image)
        report["structured_features"] = [f.model_dump() for f in features]
        report["passed"] = report["image_challenge_passed"] and bool(features)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["reason"] = "实际调用失败；未保存密钥、请求头或可能包含敏感信息的服务错误正文"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-configured-model", action="store_true", help="Authorize two potentially billed calls to the configured model")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_configured_model:
        parser.error("Live probe requires --allow-configured-model; no model was called")
    result = asyncio.run(probe())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
