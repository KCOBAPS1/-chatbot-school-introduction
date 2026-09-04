import os
import json
import asyncio
import base64
from flask import Flask, request, jsonify
from openai import OpenAI
import edge_tts

app = Flask(__name__)

# 初始化 OpenAI 用戶端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 學校詳細資料背景庫
SCHOOL_INFO = """
英皇書院同學會小學（King's College Old Boys' Association Primary School）
地址：香港上環必列者士街58號
電話：2547 7468
網址：kcobaps1.edu.hk

學校重點特色：
1. 辦學宗旨與精神：以「堅毅平實」嘅「無花果精神」滋養學生品德，注重小班教學，令每位學生都能被看見、發光發亮。
2. 小一過渡期照顧：實施「三班主任制」同埋階梯式適應課程，提供幸福關愛校園環境。
3. 數字創新教育：獲教育局指定為「數字教育卓越學校」，引導學生運用編程（Coding）同人工智能（AI）解決問題。
4. 升中表現優異：連續七年超過七成畢業生獲派英文中學（英中），獲派首三志願比率高達 98%。
5. 地理位置澄清：本校位於「上環必列者士街58號」，絕對唔係「普慶坊40號」（普慶坊係第二校，請勿混淆）。
"""

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "你係英皇書院同學會小學嘅現任校長「屈嘉曼校長」。\n\n"
        "【核心語言指令（極重要）：必須全程使用地道廣東話口語】\n"
        "1. 你的所有回答必須使用自然、親切嘅「廣東話口語」（粵語口語），絕對禁止使用書面語！\n"
        "   - 用「我哋」切勿用「我們」\n"
        "   - 用「嘅」切勿用「的」\n"
        "   - 用「係」切勿用「是」\n"
        "   - 用「呢度」切勿用「這裡」\n"
        "   - 用「啱啱 / 依家」切勿用「剛才 / 現在」\n"
        "2. 語氣要像屈校長親自同家長面談對話一樣自然流利親切。\n\n"
        "【核心校舍資料（必須完全準確）】\n"
        "1. 本校名稱：英皇書院同學會小學（英文：King's College Old Boys' Association Primary School）\n"
        "2. 本校地址：香港上環必列者士街58號\n"
        "3. 絕對嚴禁混淆：本校地址係「必列者士街58號」，絕對唔係「普慶坊40號」（普慶坊係第二校，唔係本校）！\n"
        "4. 本校電話：2547 7468\n\n"
        "【對話與格式規則】\n"
        "1. 回答必須極之簡短、自然、像真人對話，控制在 2 至 3 句以內（方便廣東話語音朗讀）。\n"
        "2. 嚴禁輸出任何網址、https 連結、Markdown 超連結或「Learn more」區域。\n"
        "3. 如被問及學校網址，請只講出簡短域名「kcobaps1.edu.hk」。\n"
        "4. 你只可以回答與「英皇書院同學會小學」相關嘅問題（例如地址、交通、特色、課程、升中、校園生活）。\n"
        "5. 如問題與本校無關，請禮貌拒絕：「我係英小嘅屈嘉曼校長，我只可以解答與英皇書院同學會小學相關嘅查詢。請問有咩關於英小嘅問題想了解？」\n\n"
        f"【補充資料檔案】\n{SCHOOL_INFO}"
    )
}

async def generate_cantonese_audio(text: str) -> str:
    """使用 Edge-TTS 生成香港廣東話（HiuMaan 女性聲音）並轉為 Base64 Data URL"""
    voice = "zh-HK-HiuMaanNeural"  # 香港廣東話女性語音（屈校長聲音）
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
        data = request.get_json() or {}
        user_messages = data.get('messages', [])
        
        # 組合 System Prompt 與使用者對話紀錄
        messages = [SYSTEM_PROMPT] + user_messages

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=250
        )

        reply_text = response.choices[0].message.content.strip()
        return jsonify({"text": reply_text})

    except Exception as e:
        print(f"Chat API Error: {str(e)}")
        return jsonify({"detail": str(e)}), 500

@app.route('/api/tts', methods=['POST'])
def tts():
    try:
        data = request.get_json() or {}
        text = data.get('text', '')

        if not text:
            return jsonify({"detail": "缺少文字內容"}), 400

        # 執行非同步廣東話語音合成
        audio_url = asyncio.run(generate_cantonese_audio(text))
        return jsonify({"audio_url": audio_url})

    except Exception as e:
        print(f"TTS API Error: {str(e)}")
        return jsonify({"detail": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
