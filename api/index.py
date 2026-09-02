import os
import re
import base64
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(title="英皇書院同學會小學 余主任 Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]

class TTSRequest(BaseModel):
    text: str

def clean_response(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'---[\s\S]*$', '', text)
    text = re.sub(r'(?i)learn\s+more:[\s\S]*$', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = text.replace('**', '').replace('__', '').replace('*', '')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)

SCHOOL_INFO = ""
possible_paths = [
    os.path.join(os.path.dirname(__file__), "..", "schoolintroduction.txt"),
    os.path.join(os.path.dirname(__file__), "..", "schoolintroduction"),
    os.path.join(os.getcwd(), "schoolintroduction.txt"),
    os.path.join(os.getcwd(), "schoolintroduction"),
]

for path in possible_paths:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                SCHOOL_INFO = f.read().strip()
            if SCHOOL_INFO:
                break
        except Exception as e:
            print(f"Error reading {path}: {e}")

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "你係英皇書院同學會小學嘅「余主任」。\n\n"
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
        "5. 如問題與本校無關，請禮貌拒絕：「我係英小嘅余主任，我只可以解答與英皇書院同學會小學相關嘅查詢。請問有咩關於英小嘅問題想了解？」\n"
        "6. 請使用親切、專業同禮貌嘅廣東話（繁體中文）回答。\n\n"
        f"【補充資料檔案】\n{SCHOOL_INFO}"
    )
}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    poe_api_key = os.getenv("POE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not poe_api_key:
        raise HTTPException(status_code=500, detail="POE_API_KEY is not configured")

    poe_bot_handle = os.getenv("POE_BOT_NAME", "schoolchatbotyu")

    formatted_messages = [SYSTEM_PROMPT]
    for msg in request.messages:
        formatted_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.poe.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {poe_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": poe_bot_handle,
                    "messages": formatted_messages,
                    "temperature": 0.1
                }
            )

            if response.status_code == 200:
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"]
                return {"text": clean_response(raw_text)}

            openai_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {poe_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": formatted_messages,
                    "temperature": 0.1
                }
            )

            if openai_response.status_code == 200:
                data = openai_response.json()
                raw_text = data["choices"][0]["message"]["content"]
                return {"text": clean_response(raw_text)}

            raise HTTPException(
                status_code=response.status_code,
                detail=f"API Request Failed: {response.text}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts")
async def generate_tts(request: TTSRequest):
    api_key = os.getenv("CANTONESE_AI_API_KEY")
    voice_id = os.getenv("CANTONESE_AI_VOICE")

    if not api_key or not voice_id:
        return {"audio_url": None}

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
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
