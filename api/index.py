import os
import json
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

POE_API_KEY = os.environ.get("POE_API_KEY")
POE_BOT_NAME = os.environ.get("POE_BOT_NAME")

def clean_json_string(raw_str):
    """清除 Poe 可能附帶的 ```json ... ``` 標記"""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_str.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])
        
        if not messages:
            return jsonify({"detail": "缺少對話內容"}), 400

        if not POE_API_KEY or not POE_BOT_NAME:
            return jsonify({"detail": "Vercel 未設定 POE_API_KEY 或 POE_BOT_NAME"}), 500

        # 呼叫 Poe 官方 API
        headers = {
            "Authorization": f"Bearer {POE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "bot": POE_BOT_NAME,
            "messages": messages
        }

        # 設定 timeout 防止 Vercel 10 秒超時崩潰
        response = requests.post(
            "https://api.poe.com/v1/chat", 
            headers=headers, 
            json=payload, 
            timeout=8.0
        )

        if response.status_code != 200:
            return jsonify({"detail": f"Poe API 錯誤: {response.status_code} - {response.text}"}), 500

        res_data = response.json()
        raw_text = res_data.get("text", "")

        # 嘗試解析 Poe 回傳的雙語 JSON
        try:
            parsed = json.loads(clean_json_string(raw_text))
            display_text = parsed.get("text", raw_text)
            spoken_text = parsed.get("speech", display_text)
        except Exception:
            # 如果 Poe 回傳純文字而非 JSON，自動做降級處理，防止程式崩潰
            display_text = raw_text
            spoken_text = raw_text

        return jsonify({
            "text": display_text,
            "speech": spoken_text
        })

    except requests.exceptions.Timeout:
        return jsonify({"detail": "請求 Poe 逾時，請再試一次"}), 504
    except Exception as e:
        # 攔截所有未知異常，回傳 JSON 錯誤訊息，避免拋出 500 崩潰頁面
        return jsonify({"detail": f"後端處理異常: {str(e)}"}), 500


@app.route('/api/tts', methods=['POST'])
def tts():
    # 如有使用本地 TTS，可在這裡串接；若無則回傳空網址
    return jsonify({"audio_url": None})
