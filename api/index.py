import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(title="英皇書院同學會小學 余主任 Chatbot API")

# Enable CORS for frontend requests
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

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "你係英皇書院同學會小學嘅「余主任」。"
        "請用親切、專業同鼓舞嘅廣東話（繁體中文）回答家長同學生嘅查詢。"
        "解答關於學校特色、課程安排、升中資訊、校園生活等問題。"
        "說話要口語化、禮貌，符合香港小學主任嘅形象。"
    )
}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    poe_api_key = os.getenv("POE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not poe_api_key:
        raise HTTPException(status_code=500, detail="POE_API_KEY is not configured in Vercel Environment Variables")

    # Construct conversation payload with system prompt
    formatted_messages = [SYSTEM_PROMPT]
    for msg in request.messages:
        formatted_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try Poe API Endpoint (OpenAI-compatible)
            response = await client.post(
                "https://api.poe.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {poe_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "GPT-4o-Mini",
                    "messages": formatted_messages,
                    "temperature": 0.7
                }
            )

            # Fallback to OpenAI API if Poe endpoint returns non-200
            if response.status_code != 200:
                openai_response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {poe_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": formatted_messages,
                        "temperature": 0.7
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

            data = response.json()
            reply_text = data["choices"][0]["message"]["content"]
            return {"text": reply_text}

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
