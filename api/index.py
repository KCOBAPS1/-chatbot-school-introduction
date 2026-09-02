import asyncio
import base64
import os
import re
import logging
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxI-n1nmYW43zAo-fShO7jCx1azXbL0EUo4W3HHibYU5epakHByMGjinEvG95jOX_da0w/exec"

class Query(BaseModel):
    messages: List[Dict[str, str]]

class TTSRequest(BaseModel):
    text: str

async def send_log_to_google_sheet(user_id: str, user_msg: str, bot_msg: str):
    if not WEBHOOK_URL:
        return
    try:
        payload = {
            "user_id": user_id,
            "user_msg": user_msg,
            "bot_msg": bot_msg
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.error(f"[Google Sheet Log Error]: {str(e)}")

def prepare_tts_text(text: str) -> str:
    cleaned = re.sub(r'\\[\(\)\[\]]', '', text)
    cleaned = re.sub(r'[\$\\]', '', cleaned)
    cleaned = re.sub(r'[「」『』“”"\'`]', '', cleaned)
    
    num_map = {
        '1960': '一九六零', '2025': '二零二五', '2026': '二零二六',
        '6000': '六千', '150': '一百五十', '90': '九十', '14': '十四',
        '60': '六十', '17': '十七', '27': '二十七', '73%': '百分之七十三',
        '93%': '百分之九十三', '98%': '百分之九十八', '0': '零', '1': '一',
        '2': '二', '3': '三', '4': '四', '5': '五', '6': '六', '7': '七',
        '8': '八', '9': '九'
    }
    for k, v in num_map.items():
        cleaned = cleaned.replace(k, v)

    return cleaned.strip()


@app.post("/api/chat")
async def chat(query: Query):
    poe_key = os.environ.get("POE_API_KEY", "").strip()

    if not poe_key:
        return {"text": "錯誤：未設定 POE_API_KEY 環境變數。"}

    cleaned_messages = [
        {"role": msg.get("role", "user"), "content": str(msg.get("content", "")).strip()}
        for msg in query.messages
        if str(msg.get("content", "")).strip()
    ]

    if not cleaned_messages:
        return {"text": "請輸入提問內容。"}

    system_instruction = {
        "role": "system",
        "content": (
            "你係英皇書院同學會小學（簡稱「英小」）嘅「余主任」。\n"
            "【角色與回答規則】：\n"
            "1. 必須嚴格基於學校官方資料回答，絕不可捏造或自行想像任何未提及嘅內容。\n"
            "2. 若查詢內容不在官方資料內，請禮貌回應：「抱歉，資料中暫未有相關詳細紀錄，建議向學校辦公室直接查詢。」\n"
            "3. 請用親切、專業嘅繁體廣東話回答，內容清晰簡潔，展現「只要在英小，誰都可發光」嘅辦學精神。"
        )
    }
    formatted_messages = [system_instruction] + cleaned_messages

    try:
        poe_client = AsyncOpenAI(
            api_key=poe_key,
            base_url="https://api.poe.com/v1",
            timeout=8.0
        )

        response = await poe_client.chat.completions.create(
            model="schoolchatbotyu",
            messages=formatted_messages,
            temperature=0.2,
            max_tokens=250
        )

        reply_text = ""
        if response.choices:
            msg = response.choices[0].message
            reply_text = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()

        if not reply_text:
            reply_text = "余主任暫時未有回應，請確認 Poe Bot 名稱及點數餘額。"

        user_last_msg = cleaned_messages[-1]["content"] if cleaned_messages else ""
        asyncio.create_task(send_log_to_google_sheet("Web_User", user_last_msg, reply_text))

        return {"text": reply_text}

    except Exception as e:
        logger.error(f"[Poe Error]: {str(e)}")
        return {"text": f"Poe 連線失敗：{str(e)}"}


@app.post("/api/tts")
async def generate_tts(req: TTSRequest):
    cantonese_key = os.environ.get("CANTONESE_AI_API_KEY", "").strip()
    cantonese_voice = os.environ.get("CANTONESE_AI_VOICE", "").strip()

    if not cantonese_key or not req.text:
        return {"audio_url": None}

    tts_text = prepare_tts_text(req.text)

    try:
        tts_url = "https://cantonese.ai/api/tts"
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        payload = {
            "api_key": cantonese_key,
            "text": tts_text,
            "output_extension": "mp3",
        }
        if cantonese_voice:
            payload["voice_id"] = cantonese_voice

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(tts_url, json=payload, headers=headers)
            if res.status_code == 200:
                audio_b64 = base64.b64encode(res.content).decode("utf-8")
                return {"audio_url": f"data:audio/mp3;base64,{audio_b64}"}
            else:
                logger.error(f"[TTS Failed]: {res.status_code} - {res.text}")
    except Exception as tts_err:
        logger.error(f"[TTS Exception]: {str(tts_err)}")

    return {"audio_url": None}
