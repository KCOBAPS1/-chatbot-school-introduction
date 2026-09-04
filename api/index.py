import os
import json
import re
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "英小屈嘉曼校長 Chatbot API 運作正常！"

POE_API_KEY = os.environ.get("POE_API_KEY", "").strip()
POE_BOT_NAME = os.environ.get("POE_BOT_NAME", "GPT-4o-Mini").strip()

CANTONESE_AI_API_KEY = os.environ.get("CANTONESE_AI_API_KEY", "").strip()
CANTONESE_AI_VOICE = os.environ.get("CANTONESE_AI_VOICE", "").strip()


def clean_json_string(raw_str: str) -> str:
    """清除 Poe 可能附帶的 ```json ... ``` Markdown 標記"""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_str.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])

        if not messages:
            return jsonify({"detail": "缺少對話內容 (messages content missing)"}), 400

        if not POE_API_KEY:
            return jsonify({"detail": "Vercel 未設定 POE_API_KEY 環境變數"}), 500

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

        raw_text = ""
        if "choices" in res_data and len(res_data["choices"]) > 0:
            raw_text = res_data["choices"][0].get("message", {}).get("content", "")
        elif "text" in res_data:
            raw_text = res_data["text"]

        display_text = raw_text
        spoken_text = raw_text

        try:
            cleaned_text = clean_json_string(raw_text)
            parsed = json.loads(cleaned_text)
            if isinstance(parsed, dict):
                display_text = parsed.get("text", raw_text)
                spoken_text = parsed.get("speech", display_text)
        except Exception:
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


@app.post("/api/tts")
async def generate_tts(request: TTSRequest):
    api_key = os.getenv("CANTONESE_AI_API_KEY")
    voice_id = os.getenv("CANTONESE_AI_VOICE")

    if not api_key or not voice_id:
        return {"audio_url": None}

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            payload = {
                "api_key": api_key,
                "text": request.text,
                "voice_id": voice_id,
                "output_extension": "mp3"
            }

            response = await client.post(
                "https://cantonese.ai/api/tts",
                headers={"Content-Type": "application/json"},
                json=payload
            )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = response.json()
                    return {"audio_url": data.get("audio_url")}
                else:
                    audio_b64 = base64.b64encode(response.content).decode("utf-8")
                    return {"audio_url": f"data:audio/mp3;base64,{audio_b64}"}

            print(f"Cantonese.ai API Error [{response.status_code}]: {response.text}")
            return {"audio_url": None}

    except Exception as e:
        print(f"TTS Request Exception: {e}")
        return {"audio_url": None}
    app.run(port=5000, debug=True)
