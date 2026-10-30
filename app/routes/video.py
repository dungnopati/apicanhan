import time
import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException

from app.models.video import VideoGenerationRequest, DirectVideoResponse, VideoItemInfo
from app.clients.factory import get_gemini_client
from app.clients.video_generator import video_manager, VIDEOS_DIR
from app.config import settings

video_router = APIRouter(prefix="/api/video", tags=["Tạo Video AI (Vids & Flow)"])


@video_router.post("/generate", response_model=DirectVideoResponse, summary="Tạo video AI trực tiếp bằng Google Vids hoặc Google Flow")
async def generate_video(req: VideoGenerationRequest):
    """Endpoint tạo video bằng tài khoản Google cá nhân (hỗ trợ Google Vids và Google Flow).
    
    - service: 'flow' (mặc định - cinematic / Veo) hoặc 'vids' (Google Workspace Omni)
    - prompt: Nội dung mô tả video
    - aspect_ratio: '16:9', '9:16', '1:1'
    """
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập prompt mô tả video.")

    # Xác định dịch vụ mục tiêu từ service hoặc model (mặc định ưu tiên Flow)
    target_service = (req.service or req.model or "muse").lower().strip()
    if "muse" in target_service:
        service_name = "Muse.ai"
        key = "muse"
    elif "vid" in target_service and "flow" not in target_service:
        service_name = "Google Vids"
        key = "vids"
    else:
        service_name = "Google Flow"
        key = "flow"

    try:
        # Nếu đang dùng browser adapter hoặc gọi trực tiếp video_manager
        video_url = await video_manager.generate_video(
            prompt=req.prompt,
            service=key,
            aspect_ratio=req.aspect_ratio or "16:9",
            duration=req.duration or 10,
        )

        file_name = video_url.split("/")[-1] if "/" in video_url else ""
        return DirectVideoResponse(
            success=True,
            service=service_name,
            prompt=req.prompt,
            video_url=video_url,
            file_name=file_name,
            message=f"Đã tạo video thành công từ {service_name}!",
            video_urls=getattr(video_manager, "_last_downloaded_urls", [video_url])
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo video trên {service_name}: {str(exc)}")


@video_router.get("/list", response_model=List[VideoItemInfo], summary="Danh sách video AI đã tạo lưu trong outputs")
async def list_generated_videos():
    """Lấy danh sách toàn bộ video MP4 đã tạo trong thư mục outputs/generated_videos."""
    if not VIDEOS_DIR.exists():
        return []

    files = []
    for f in VIDEOS_DIR.glob("*.mp4"):
        stat = f.stat()
        files.append(
            VideoItemInfo(
                file_name=f.name,
                video_url=f"http://127.0.0.1:{settings.PORT}/outputs/videos/{f.name}",
                size_bytes=stat.st_size,
                created_at=stat.st_mtime,
            )
        )
    # Sắp xếp mới nhất lên đầu
    files.sort(key=lambda x: x.created_at, reverse=True)
    return files
