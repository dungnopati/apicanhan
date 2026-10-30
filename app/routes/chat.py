from typing import List
from fastapi import APIRouter, HTTPException
from app.models.chat import (
    GenerateRequest,
    GenerateResponse,
    ChatRequest,
    ChatResponse,
    ModelInfo,
)
from app.clients.factory import get_gemini_client
from app.config import settings

chat_router = APIRouter(prefix="/api", tags=["Gemini Trực tiếp"])


@chat_router.post("/generate", response_model=GenerateResponse, summary="Tạo văn bản với câu lệnh đơn lẻ")
async def generate_text(req: GenerateRequest):
    """Gửi một prompt đơn lẻ đến Gemini và nhận câu trả lời."""
    client = get_gemini_client()
    try:
        reply = await client.generate_content(
            prompt=req.prompt,
            model=req.model or settings.DEFAULT_MODEL,
            system_instruction=req.system_instruction,
            temperature=req.temperature or 0.7,
            max_tokens=req.max_tokens or 2048,
        )
        return GenerateResponse(
            text=reply,
            model=req.model or settings.DEFAULT_MODEL,
            backend=client.backend_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý yêu cầu: {str(e)}")


@chat_router.post("/chat", response_model=ChatResponse, summary="Hội thoại nhiều lượt")
async def chat_conversation(req: ChatRequest):
    """Hội thoại nhiều lượt với chuỗi lịch sử tin nhắn."""
    client = get_gemini_client()
    try:
        reply = await client.chat(
            messages=req.messages,
            model=req.model or settings.DEFAULT_MODEL,
            system_instruction=req.system_instruction,
            temperature=req.temperature or 0.7,
            max_tokens=req.max_tokens or 2048,
        )
        return ChatResponse(
            reply=reply,
            model=req.model or settings.DEFAULT_MODEL,
            backend=client.backend_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý cuộc hội thoại: {str(e)}")


@chat_router.get("/models", response_model=List[ModelInfo], summary="Danh sách mô hình có sẵn")
async def list_models():
    """Xem danh sách các model Gemini được hỗ trợ."""
    client = get_gemini_client()
    return await client.list_models()
