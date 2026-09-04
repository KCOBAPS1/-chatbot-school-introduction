import os
import json
import re
import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 讀取 Vercel 環境變數
POE_API_KEY = os.environ.get("POE_API_KEY")
POE_BOT_NAME = os.environ.get("POE_BOT_NAME", "GPT-4o-Mini")

CANTONESE_AI_API_KEY = os.environ.get("CANTONESE_AI_API_KEY")
CANTONESE_AI_VOICE = os.environ.get("CANTONESE_AI_VOICE")


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

        # 呼叫 Poe 相容接口
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

        # 解析 Poe 回傳內容
        raw_text = ""
        if "choices" in res_data and len(res_data["choices"]) > 0:
            raw_text = res_data["choices"][0].get("message", {}).get("content", "")
        elif "text" in res_data:
            raw_text = res_data["text"]

        display_text = raw_text
        spoken_text = raw_text

        # 嘗試解開雙語 JSON (text 與 speech)
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


@app.route('/api/tts', methods=['POST'])
def tts():
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"audio_url": None}), 400

        if not CANTONESE_AI_API_KEY:
            print("Missing CANTONESE_AI_API_KEY in environment variables.")
            return jsonify({"audio_url": None, "error": "未設定 CANTONESE_AI_API_KEY"}), 500

        # 呼叫 Cantonese.ai 官方語音生成接口
        headers = {
            "Authorization": f"Bearer {CANTONESE_AI_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "text": text
        }
        if CANTONESE_AI_VOICE:
            payload["voice"] = CANTONESE_AI_VOICE

        tts_res = requests.post(
            "https://api.cantonese.ai/v1/tts",
            headers=headers,
            json=payload,
            timeout=8.0
        )

        if tts_res.status_code != 200:
            print(f"Cantonese.ai API Error ({tts_res.status_code}): {tts_res.text}")
            return jsonify({"audio_url": None, "error": tts_res.text}), 500

        # 處理 Cantonese.ai 回傳格式（JSON 或 二進制音訊）
        content_type = tts_res.headers.get("content-type", "")
        if "application/json" in content_type:
            res_json = tts_res.json()
            audio_url = res_json.get("audio_url") or res_json.get("url")
            if not audio_url and "audio" in res_json:
                audio_url = f"data:audio/mp3;base64,{res_json['audio']}"
            return jsonify({"audio_url": audio_url})
        else:
            # 直接回傳音訊檔案時轉為 Base64 供前端播放
            b64_audio = base64.b64encode(tts_res.content).decode("utf-8")
            return jsonify({"audio_url": f"data:audio/mp3;base64,{b64_audio}"})

    except Exception as e:
        print("Cantonese.ai TTS Fetch Error:", str(e))
        return jsonify({"audio_url": None, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
