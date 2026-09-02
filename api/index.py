import os
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

# Read school context file from repository root
SCHOOL_INFO = ""
info_path = os.path.join(os.path.dirname(__file__), "..", "schoolintroduction")
if os.path.exists(info_path):
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            SCHOOL_INFO = f.read()
    except Exception as e:
        print(f"Could not read schoolintroduction: {e}")

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "你係英皇書院同學會小學嘅「余主任」。\n"
        "【嚴格規則】\n"
        "1. 你必須只回答與「英皇書院同學會小學」相關嘅問題（例如學校特色、課程、升中資訊、校園生活）。\n"
        "2. 如果問題與本校無關（例如詢問其他無關人物、娛樂、政治、一般知識等），你必須禮貌地婉拒並簡短回答：「我係英小嘅余主任，我只可以解答與英皇書院同學會小學相關嘅查詢。請問有咩關於英小嘅問題想了解？」\n"
        "3. 請用親切、專業同禮貌嘅廣東話（繁體中文）回答。\n\n"
        f"【學校官方參考資料】\n{SCHOOL_INFO}"
    )
}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    poe_api_key = os.getenv("POE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not poe_api_key:
        raise HTTPException(status_code=500, detail="POE_API_KEY is not configured in Vercel Environment Variables")

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
                    "temperature": 0.3
                }
            )

            if response.status_code == 200:
                data = response.json()
                reply_text = data["choices"][0]["message"]["content"]
                return {"text": reply_text}

            openai_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {poe_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": formatted_messages,
                    "temperature": 0.3
                }
            )

            if openai_response.status_code == 200:
                data = openai_response.json()
                reply_text = data["choices"][0]["message"]["content"]
                return {"text": reply_text}

            raise HTTPException(
                status_code=response.status_code,
                detail=f"API Request Failed: {response.text}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts")
async def generate_tts(request: TTSRequest):
    cantonese_api_key = os.getenv("CANTONESE_AI_API_KEY")
    voice_id = os.getenv("CANTONESE_AI_VOICE", "default")

    if not cantonese_api_key:
        return {"audio_url": None}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.cantonese.ai/v1/tts",
                headers={
                    "Authorization": f"Bearer {cantonese_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": request.text,
                    "voice": voice_id
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {"audio_url": data.get("audio_url")}

            return {"audio_url": None}

    except Exception as e:
        print(f"TTS Error: {e}")
        return {"audio_url": None}
