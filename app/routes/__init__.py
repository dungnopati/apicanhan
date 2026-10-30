from app.routes.health import health_router
from app.routes.chat import chat_router
from app.routes.openai_compat import openai_router
from app.routes.video import video_router
from app.routes.payment import payment_router

__all__ = [
    "health_router",
    "chat_router",
    "openai_router",
    "video_router",
    "payment_router"
]
