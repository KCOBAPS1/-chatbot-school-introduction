import os
import json
import asyncio
import base64
from flask import Flask, request, jsonify
from openai import OpenAI
import edge_tts

app = Flask(__name__)

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

SCHOOL_INFO = """
英皇書院同學會小學（King's College Old Boys' Association Primary School，簡稱「英小」）
校址：香港上環必列者士街58號
電話：2547 7468
網址：kcobaps1.edu.hk

學校重點特色與數據：
1. 辦學宗旨：以「堅毅平實」的「無花果精神」滋養學生品德，注重小班教學，讓每位學生都能發光發亮。核心口號：「只要在英小，誰都可發光」。
2. 小一銜接措施：實施「三班主任制」（小一每班設2位正班主任 + 1位副班主任），9月不設默書，上學期默書與功課量均適度減輕。
3. 數字創新與設施：教育局指定「數字教育卓越學校」。智能課室配備納米智能互動黑板，哈利波特式圖書館藏書約6,000本，設有 STEM PATH、INNOSPACE 及 AI in EDU Center。
4. 卓越師資：兩屆三奪「行政長官卓越教學獎」（2025年賴永康助理校長與余朗源主任獲嘉許狀，林晃生老師奪首屆新秀獎；2026年黃浩賢老師奪第二屆新秀獎）。
5. 升中表現（2026年數據）：73% 學生獲派以英語為教學語言（EMI）的中學，98% 學生獲派首三志願。
6. 體藝成就：口琴王國，德國世界口琴節 2025 年奪 3 項世界冠軍。開辦「元宇宙畫班」及「AI 繪畫創作」。
7. 校址澄清：本校位於「香港上環必列者士街58號」，絕對不是「普慶坊40號」（普慶坊為第二校）。
"""

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "你是英皇書院同學會小學（簡稱「英小」）的現任校長「屈嘉曼校長」。\n\n"
        "【最高指令：必須回傳 JSON 格式】\n"
        "你的每一個回答都必須輸出為嚴格的 JSON 格式，包含兩個 key：\n"
        "1. \"text\"：使用親切、專業、鼓勵性的【繁體中文書面語】（用於螢幕文字顯示）。\n"
        "2. \"speech\"：將上述書面語內容翻譯為地道的【廣東話口語】（用於語音朗讀，請用「我哋」、「嘅」、「係」、「呢度」等口語字眼）。\n\n"
        "JSON 範例格式：\n"
        "{\n"
        "  \"text\": \"你好！我是英皇書院同學會小學的屈嘉曼校長。歡迎查詢本校資訊。\",\n"
        "  \"speech\": \"你好呀！我係英小嘅屈嘉曼校長。歡迎查詢英皇書院同學會小學嘅學校資訊！\"\n"
        "}\n\n"
        "【內容準則】\n"
        "1. 所有回答必須嚴格基於提供的官方資料，絕不捏造未提及的事實。\n"
        "2. 控制在 2 至 3 句以內，簡潔自然。\n"
        "3. 若查詢內容不在資料範圍內，text 請回答：「抱歉，目前資料中未有相關詳細紀錄，建議你直接致電或親臨英皇書院同學會小學辦公室查詢。」，speech 翻譯為廣東話口語。\n\n"
        f"【官方資料庫】\n{SCHOOL_INFO}"
    )
}

def safe_run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def generate_cantonese_audio(text: str) -> str:
    voice = "zh-HK-HiuMaanNeural"
    communicate = edge_tts.Communicate(text, voice)
    audio_bytes = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes.extend(chunk["data"])
    base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    return f"data:audio/mp3;base64,{base64_audio}"

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not os.environ.get("OPENAI_API_KEY"):
            return jsonify({"detail": "請在 Vercel 設定 OPENAI_API_KEY 環境變數"}), 500

        data = request.get_json(silent=True) or {}
        user_messages = data.get('messages', [])
        messages = [SYSTEM_PROMPT] + user_messages

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=350
        )

        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)
        
        display_text = parsed.get("text", "")
        spoken_text = parsed.get("speech", display_text)

        return jsonify({
            "text": display_text,
            "speech": spoken_text
        })

    except Exception as e:
        print(f"Chat API Error: {str(e)}")
        return jsonify({"detail": f"Chat 錯誤: {str(e)}"}), 500

@app.route('/api/tts', methods=['POST'])
def tts():
    try:
        data = request.get_json(silent=True) or {}
        text = data.get('text', '')

        if not text:
            return jsonify({"detail": "缺少文字內容"}), 400

        audio_url = safe_run_async(generate_cantonese_audio(text))
        return jsonify({"audio_url": audio_url})

    except Exception as e:
        print(f"TTS API Error: {str(e)}")
        return jsonify({"detail": f"TTS 語音生成錯誤: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
