from fastapi import APIRouter
from app.models.chat import HealthResponse
from app.config import settings
from app.clients.factory import get_gemini_client

health_router = APIRouter(tags=["Hệ thống"])


@health_router.get("/health", response_model=HealthResponse, summary="Kiểm tra trạng thái server")
@health_router.get("/api/status", response_model=HealthResponse, summary="Kiểm tra trạng thái API chi tiết")
async def health_check():
    """Kiểm tra máy chủ GeminiBridge có đang hoạt động tốt hay không và xem trạng thái cấu hình API Key."""
    client = get_gemini_client()
    return HealthResponse(
        status="running",
        version="1.0.0",
        backend=client.backend_name,
        api_key_configured=settings.is_api_key_valid,
        api_key_preview=settings.safe_api_key_preview,
        default_model=settings.DEFAULT_MODEL,
    )
