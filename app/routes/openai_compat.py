import time
import uuid
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import (
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
    OpenAIChoice,
    OpenAIMessage,
    OpenAIUsage,
    OpenAIModelListResponse,
    OpenAIModelItem,
    ChatMessage,
)
from app.clients.factory import get_gemini_client
from app.config import settings

openai_router = APIRouter(prefix="/v1", tags=["Chuẩn OpenAI Tương Thích"])


@openai_router.post("/chat/completions", summary="OpenAI-compatible Chat Completion")
async def chat_completions(req: OpenAIChatCompletionRequest):
    """Endpoint tương thích 100% định dạng OpenAI /v1/chat/completions.

    Hỗ trợ cả chế độ chuẩn (JSON) lẫn chế độ truyền phát trực tiếp (Server-Sent Events stream: true)
    cho hầu hết các ứng dụng AI như:
    - Chatbox
    - NextChat (ChatGPT-Next-Web)
    - Cherry Studio
    - LibreChat
    - Dify
    - Continue.dev
    - Obsidian Copilot, Cursor, v.v.
    """
    client = get_gemini_client()

    # Chuyển đổi định dạng tin nhắn OpenAI sang ChatMessage nội bộ
    internal_messages = []
    for msg in req.messages:
        text_content = ""
        if msg.content is None:
            text_content = ""
        elif isinstance(msg.content, str):
            text_content = msg.content
        elif isinstance(msg.content, list):
            parts = []
            for item in msg.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif "text" in item:
                        parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    parts.append(item)
            text_content = "\n".join(parts)
        else:
            text_content = str(msg.content)
        internal_messages.append(ChatMessage(role=msg.role, content=text_content))

    target_model = req.model or settings.DEFAULT_MODEL

    # Chế độ streaming (SSE)
    if req.stream:
        async def event_generator():
            chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            created = int(time.time())

            # Chunk đầu tiên định danh vai trò assistant
            first_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": target_model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }],
            }
            yield f"data: {json.dumps(first_chunk, ensure_ascii=False)}\n\n"

            try:
                async for text_delta in client.chat_stream(
                    messages=internal_messages,
                    model=target_model,
                    temperature=req.temperature if req.temperature is not None else 0.7,
                    max_tokens=req.max_tokens if req.max_tokens is not None else 2048,
                ):
                    chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": target_model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": text_delta},
                            "finish_reason": None,
                        }],
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as exc:
                err_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": target_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"\n\n[Lỗi kết nối AI: {str(exc)}]"},
                        "finish_reason": "stop",
                    }],
                }
                yield f"data: {json.dumps(err_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Chunk kết thúc
            final_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": target_model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }],
            }
            yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Chế độ non-streaming (trả về full JSON)
    try:
        reply = await client.chat(
            messages=internal_messages,
            model=target_model,
            temperature=req.temperature if req.temperature is not None else 0.7,
            max_tokens=req.max_tokens if req.max_tokens is not None else 2048,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": {"message": str(e), "type": "invalid_request_error"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "api_error"}})

    # Ước lượng số lượng token xấp xỉ cho phản hồi chuẩn OpenAI
    prompt_chars = sum(len(m.content) for m in internal_messages)
    reply_chars = len(reply)
    prompt_tokens = max(1, prompt_chars // 4)
    completion_tokens = max(1, reply_chars // 4)

    return OpenAIChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        object="chat.completion",
        created=int(time.time()),
        model=target_model,
        choices=[
            OpenAIChoice(
                index=0,
                message=OpenAIMessage(role="assistant", content=reply),
                finish_reason="stop",
            )
        ],
        usage=OpenAIUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


@openai_router.get("/models", response_model=OpenAIModelListResponse, summary="OpenAI-compatible Models List")
async def list_openai_models():
    """Trả về danh sách mô hình theo chuẩn OpenAI để các phần mềm AI tự động nhận diện."""
    client = get_gemini_client()
    models = await client.list_models()
    data = [
        OpenAIModelItem(id=m.id, owned_by="google-gemini")
        for m in models
    ]
    existing_ids = {m.id for m in models}
    for extra_id in ["google-flow", "google-vids"]:
        if extra_id not in existing_ids:
            data.append(OpenAIModelItem(id=extra_id, owned_by="google-video"))

    return OpenAIModelListResponse(
        object="list",
        data=data
    )


@openai_router.post("/images/generations", summary="OpenAI-compatible Image Generation")
async def generate_images(req: dict):
    """Endpoint tạo ảnh theo chuẩn OpenAI (/v1/images/generations).

    Hỗ trợ tạo ảnh AI miễn phí chất lượng cao (FLUX / Imagen), không giới hạn và không cần key phụ.
    """
    client = get_gemini_client()
    prompt = req.get("prompt", "")
    n = req.get("n", 1)

    if not prompt:
        raise HTTPException(status_code=400, detail={"error": {"message": "Thiếu prompt mô tả ảnh."}})

    try:
        # Thử lấy ảnh từ backend (Browser Imagen 3 / Official / WebAPI)
        image_urls = await client.generate_images(prompt, n=n)

        # Nếu dùng trình duyệt hoặc official mà không lấy được ảnh, báo lỗi rõ ràng thay vì fallback ảnh xấu
        if not image_urls and getattr(client, "backend_name", "") in ("browser", "official"):
            raise HTTPException(
                status_code=500,
                detail={"error": {"message": "Gemini Web trên trình duyệt không tạo được ảnh cho prompt này. Vui lòng kiểm tra cửa sổ Microsoft Edge.", "type": "browser_generation_error"}}
            )

        # Nếu backend khác không hỗ trợ sinh ảnh, thông báo hoặc fallback nếu có
        if not image_urls:
            import urllib.parse
            import random

            size = req.get("size", "1024x1024")
            w, h = 1024, 1024
            if "x" in str(size):
                try:
                    parts = str(size).split("x")
                    w, h = int(parts[0]), int(parts[1])
                except Exception:
                    w, h = 1024, 1024

            encoded_prompt = urllib.parse.quote(prompt.strip())
            seed = random.randint(1000, 999999)
            fallback_url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?width={w}&height={h}&nologo=true&seed={seed}&model=flux"
            )
            image_urls = [fallback_url]

        return {
            "created": int(time.time()),
            "data": [{"url": url} for url in image_urls]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "image_generation_error"}})


@openai_router.post("/videos/generations", summary="OpenAI-compatible Video Generation")
async def generate_videos_openai(req: dict):
    """Endpoint tạo video theo chuẩn OpenAI tương thích (/v1/videos/generations).

    Hỗ trợ tạo video AI từ Google Flow và Google Vids bằng tài khoản cá nhân.
    """
    prompt = req.get("prompt", "")
    if not prompt or not str(prompt).strip():
        raise HTTPException(status_code=400, detail={"error": {"message": "Thiếu prompt mô tả video.", "type": "invalid_request_error"}})

    model = str(req.get("model", "google-vids")).lower()
    service = "vids" if "vid" in model else "flow"
    aspect_ratio = req.get("aspect_ratio", req.get("size", "16:9"))
    duration = req.get("duration", 10)
    try:
        duration = int(duration)
    except Exception:
        duration = 10

    from app.clients.video_generator import video_manager

    try:
        video_url = await video_manager.generate_video(
            prompt=str(prompt),
            service=service,
            aspect_ratio=str(aspect_ratio),
            duration=duration,
        )
        return {
            "created": int(time.time()),
            "data": [{"url": video_url}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"message": str(e), "type": "video_generation_error"}})
