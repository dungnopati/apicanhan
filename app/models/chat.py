from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel, Field


# ===================================================================
# 1. Các Schema thuần túy cho GeminiBridge (Native REST API)
# ===================================================================

class ChatMessage(BaseModel):
    """Một tin nhắn trong phiên hội thoại."""
    role: str = Field(..., description="Vai trò: 'user', 'model' hoặc 'assistant', 'system'")
    content: str = Field(..., description="Nội dung văn bản của tin nhắn")


class GenerateRequest(BaseModel):
    """Yêu cầu tạo văn bản đơn giản (Prompt duy nhất)."""
    prompt: str = Field(..., description="Câu hỏi hoặc lệnh muốn Gemini trả lời")
    model: Optional[str] = Field(None, description="Tên mô hình Gemini, vd: gemini-2.0-flash")
    system_instruction: Optional[str] = Field(None, description="Chỉ dẫn hệ thống định hình phong cách phản hồi")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Độ sáng tạo (0.0 đến 2.0)")
    max_tokens: Optional[int] = Field(2048, ge=1, le=8192, description="Số lượng token tối đa trong câu trả lời")


class GenerateResponse(BaseModel):
    """Kết quả trả về từ yêu cầu tạo văn bản."""
    text: str = Field(..., description="Nội dung câu trả lời từ mô hình")
    model: str = Field(..., description="Mô hình đã được sử dụng")
    backend: str = Field(..., description="Bộ điều hợp kết nối (official / webapi)")


class ChatRequest(BaseModel):
    """Yêu cầu đối thoại đa lượt (Conversation context)."""
    messages: List[ChatMessage] = Field(..., description="Lịch sử các tin nhắn trong phiên trò chuyện")
    model: Optional[str] = Field(None, description="Tên mô hình Gemini")
    system_instruction: Optional[str] = Field(None, description="Chỉ dẫn hệ thống")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(2048, ge=1, le=8192)


class ChatResponse(BaseModel):
    """Kết quả phản hồi đối thoại."""
    reply: str = Field(..., description="Tin nhắn phản hồi từ trợ lý AI")
    model: str = Field(..., description="Mô hình đã sử dụng")
    backend: str = Field(..., description="Kiểu backend")


class ModelInfo(BaseModel):
    """Thông tin về một mô hình AI có sẵn."""
    id: str
    name: str
    description: str


class HealthResponse(BaseModel):
    """Thông tin trạng thái hoạt động của hệ thống."""
    status: str
    version: str
    backend: str
    api_key_configured: bool
    api_key_preview: str
    default_model: str


# ===================================================================
# 2. Các Schema tương thích chuẩn OpenAI (OpenAI-Compatible API)
# Giúp các công cụ như Chatbox, NextChat, Dify, Continue, Cursor kết nối dễ dàng
# ===================================================================

class OpenAIMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[Any], Dict[str, Any]]] = ""


class OpenAIChatCompletionRequest(BaseModel):
    model: Optional[str] = "gemini-2.0-flash"
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False


class OpenAIChoice(BaseModel):
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"


class OpenAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage


class OpenAIModelItem(BaseModel):
    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "google-gemini"


class OpenAIModelListResponse(BaseModel):
    object: str = "list"
    data: List[OpenAIModelItem]


class OpenAIImageGenerationRequest(BaseModel):
    prompt: str
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    model: Optional[str] = "imagen-3"


class OpenAIImageData(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None


class OpenAIImageGenerationResponse(BaseModel):
    created: int
    data: List[OpenAIImageData]
