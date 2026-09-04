import os
import json
import re
import asyncio
import base64
import requests
import edge_tts
from flask import Flask, request, jsonify

app = Flask(__name__)

# Fetch environment variables set in Vercel
POE_API_KEY = os.environ.get("POE_API_KEY") or os.environ.get("CANTONESE_AI_API_KEY")
POE_BOT_NAME = os.environ.get("POE_BOT_NAME", "GPT-4o-Mini")


def clean_json_string(raw_str: str) -> str:
    """Removes Markdown codeblock formatting like ```json ... ``` if present."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_str.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


async def generate_cantonese_tts_base64(text_to_speak: str) -> str:
    """Generates Cantonese TTS audio using Edge TTS and returns a Base64 data URI."""
    voice = os.environ.get("CANTONESE_AI_VOICE", "zh-HK-HiuMaanNeural")
    communicate = edge_tts.Communicate(text_to_speak, voice)
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    return f"data:audio/mp3;base64,{b64_audio}"


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])

        if not messages:
            return jsonify({"detail": "缺少對話內容 (messages content missing)"}), 400

        if not POE_API_KEY:
            return jsonify({"detail": "Vercel 未設定 POE_API_KEY 環境變數"}), 500

        # Call Poe API via OpenAI-compatible endpoint
        headers = {
            "Authorization": f"Bearer {POE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": POE_BOT_NAME,
            "messages": messages
        }

        response = requests.post(
            "https://api.poe.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=8.5
        )

        if response.status_code != 200:
            return jsonify({"detail": f"Poe API 錯誤 ({response.status_code}): {response.text}"}), 500

        res_data = response.json()

        # Extract text response from Poe response format
        raw_text = ""
        if "choices" in res_data and len(res_data["choices"]) > 0:
            raw_text = res_data["choices"][0].get("message", {}).get("content", "")
        elif "text" in res_data:
            raw_text = res_data["text"]

        # Parse JSON output (text and speech) from bot
        display_text = raw_text
        spoken_text = raw_text

        try:
            cleaned_text = clean_json_string(raw_text)
            parsed = json.loads(cleaned_text)
            if isinstance(parsed, dict):
                display_text = parsed.get("text", raw_text)
                spoken_text = parsed.get("speech", display_text)
        except Exception:
            # Fallback if bot didn't output structured JSON
            display_text = raw_text
            spoken_text = raw_text

        return jsonify({
            "text": display_text,
            "speech": spoken_text
        })

    except requests.exceptions.Timeout:
        return jsonify({"detail": "請求 Poe 逾時 (Timeout)，請再試一次"}), 504
    except Exception as e:
        return jsonify({"detail": f"後端處理異常: {str(e)}"}), 500


@app.route('/api/tts', methods=['POST'])
def tts():
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"audio_url": None}), 400

        # Execute async Edge TTS generator inside synchronous Flask route
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            audio_url = loop.run_until_complete(generate_cantonese_tts_base64(text))
        finally:
            loop.close()

        return jsonify({"audio_url": audio_url})

    except Exception as e:
        print("TTS Generation Error:", str(e))
        return jsonify({"audio_url": None, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
