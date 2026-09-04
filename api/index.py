import os
import json
import re
import asyncio
import base64
import requests
import edge_tts
from flask import Flask, request, jsonify

app = Flask(__name__)

# 讀取 Vercel 環境變數
POE_API_KEY = os.environ.get("POE_API_KEY") or os.environ.get("CANTONESE_AI_API_KEY")
POE_BOT_NAME = os.environ.get("POE_BOT_NAME", "GPT-4o-Mini")


def clean_json_string(raw_str: str) -> str:
    """清除 Poe 可能附帶的 ```json ... ``` Markdown 標記"""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_str.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


async def generate_cantonese_tts_base64(text_to_speak: str) -> str:
    """使用 Edge TTS 生成廣東話語音，並轉換為 Base64 Data URI"""
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

        # 解析 Poe 回傳之內容
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

        # 在 Vercel 環境下使用 asyncio.run 執行 Edge TTS 生成
        audio_url = asyncio.run(generate_cantonese_tts_base64(text))
        return jsonify({"audio_url": audio_url})

    except Exception as e:
        print("TTS Generation Error:", str(e))
        return jsonify({"audio_url": None, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
