from typing import List, Optional
from pydantic import BaseModel, Field


class VideoGenerationRequest(BaseModel):
    """Yêu cầu tạo video theo định dạng tương thích OpenAI hoặc REST."""
    prompt: str = Field(..., description="Văn bản mô tả nội dung video muốn AI tạo.")
    model: Optional[str] = Field("google-flow", description="Tên mô hình hoặc dịch vụ ('google-flow', 'google-vids', 'flow', 'vids').")
    service: Optional[str] = Field("flow", description="Dịch vụ ('flow' hoặc 'vids', mặc định 'flow').")
    aspect_ratio: Optional[str] = Field("16:9", description="Tỉ lệ khung hình ('16:9', '9:16', '1:1').")
    duration: Optional[int] = Field(10, description="Độ dài video (giây, mặc định 10s).")


class VideoDataItem(BaseModel):
    """Mục video trong phản hồi."""
    url: str
    revised_prompt: Optional[str] = None


class VideoGenerationResponse(BaseModel):
    """Phản hồi tạo video theo chuẩn OpenAI (/v1/videos/generations)."""
    created: int
    data: List[VideoDataItem]


class DirectVideoResponse(BaseModel):
    """Phản hồi tạo video chi tiết (/api/video/generate)."""
    success: bool
    service: str
    prompt: str
    video_url: str
    file_name: str
    message: Optional[str] = None
    video_urls: Optional[List[str]] = None


class VideoItemInfo(BaseModel):
    """Thông tin video đã tạo lưu trong outputs."""
    file_name: str
    video_url: str
    size_bytes: int
    created_at: float
