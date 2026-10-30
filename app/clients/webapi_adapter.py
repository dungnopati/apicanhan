import asyncio
from typing import List, Optional
from app.clients.base import BaseGeminiClient
from app.models.chat import ChatMessage, ModelInfo
from app.config import settings

# Danh sách các model hỗ trợ trên giao diện Gemini Web
WEB_MODELS = [
    ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash (Web)",
        description="Mô hình nhanh và thông minh nhất chạy qua tài khoản Gemini Web cá nhân."
    ),
    ModelInfo(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash (Web)",
        description="Mô hình nhanh, nhẹ phù hợp cho đa tác vụ."
    ),
    ModelInfo(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro (Web)",
        description="Mô hình tư duy chuyên sâu với ngữ cảnh siêu dài."
    ),
]


class WebAPIAdapter(BaseGeminiClient):
    """Bộ điều hợp kết nối trực tiếp đến tài khoản Gemini Web cá nhân qua Cookie.

    Đặc điểm:
    - Sử dụng thư viện gemini-webapi kết nối qua giao thức web ngầm của Google.
    - Duy trì phiên làm việc (Session) liên tục để tăng tốc độ phản hồi.
    - Tự động chuẩn hóa câu hỏi đa lượt (Multi-turn chat) gửi lên Gemini.
    """

    def __init__(
        self,
        secure_1psid: Optional[str] = None,
        secure_1psidts: Optional[str] = None,
    ):
        self._secure_1psid = settings.GEMINI_SECURE_1PSID if secure_1psid is None else secure_1psid
        self._secure_1psidts = settings.GEMINI_SECURE_1PSIDTS if secure_1psidts is None else secure_1psidts
        self._client = None
        self._lock = asyncio.Lock()

    @property
    def backend_name(self) -> str:
        return "webapi"

    async def _ensure_client(self):
        """Khởi tạo phiên Gemini Web nếu chưa có hoặc tái sử dụng phiên hiện tại."""
        if not self._secure_1psid:
            raise ValueError(
                "Chưa cấu hình GEMINI_SECURE_1PSID! "
                "Vui lòng điền mã cookie __Secure-1PSID của bạn vào file .env."
            )

        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is not None:
                return self._client

            try:
                import gemini_webapi
                client = gemini_webapi.GeminiClient(
                    secure_1psid=self._secure_1psid,
                    secure_1psidts=self._secure_1psidts if self._secure_1psidts else None,
                )
                await client.init(timeout=30)
                self._client = client
                return self._client
            except ImportError:
                raise RuntimeError("Thư viện 'gemini-webapi' chưa được cài đặt trong môi trường!")
            except Exception as e:
                raise RuntimeError(
                    f"Không thể kết nối đến tài khoản Gemini Web: {e}. "
                    "Vui lòng kiểm tra lại cookie __Secure-1PSID trong file .env xem có còn hiệu lực không."
                )

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        client = await self._ensure_client()

        final_prompt = prompt
        if system_instruction:
            final_prompt = f"[System Instruction: {system_instruction}]\n\n{prompt}"

        try:
            response = await client.generate_content(final_prompt)
            result_text = response.text if (hasattr(response, "text") and response.text) else ""

            # Nếu Gemini sinh ảnh kèm theo (Imagen 3), gắn link Markdown để ứng dụng AI tự động hiển thị
            if hasattr(response, "images") and response.images:
                img_markdowns = [
                    f"![Ảnh được tạo bởi Gemini]({img.url})"
                    for img in response.images
                    if hasattr(img, "url") and img.url
                ]
                if img_markdowns:
                    images_block = "\n\n".join(img_markdowns)
                    result_text = f"{result_text}\n\n{images_block}" if result_text else images_block

            return result_text or str(response)
        except Exception as e:
            # Nếu gặp lỗi phiên, giải phóng client để lần gọi sau tự động kết nối lại
            self._client = None
            raise RuntimeError(f"Lỗi khi nhận phản hồi từ Gemini Web: {e}")

    async def generate_images(self, prompt: str, n: int = 1) -> List[str]:
        """Tạo ảnh từ văn bản mô tả và trả về danh sách URL ảnh (Imagen 3)."""
        client = await self._ensure_client()
        try:
            response = await client.generate_content(prompt)
            if hasattr(response, "images") and response.images:
                return [img.url for img in response.images if hasattr(img, "url") and img.url]
            return []
        except Exception as e:
            self._client = None
            raise RuntimeError(f"Lỗi khi tạo ảnh qua Gemini Web: {e}")

    async def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not messages:
            return ""

        # Nếu chỉ có 1 tin nhắn user, gửi trực tiếp
        if len(messages) == 1 and messages[0].role.lower() in ("user", "human"):
            return await self.generate_content(
                prompt=messages[0].content,
                model=model,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # Định dạng chuỗi lịch sử hội thoại nhiều lượt cho Gemini Web
        prompt_lines = []
        if system_instruction:
            prompt_lines.append(f"[System Instruction: {system_instruction}]\n")

        for msg in messages:
            role = msg.role.lower().strip()
            if role in ("assistant", "model"):
                prompt_lines.append(f"Gemini: {msg.content}")
            elif role == "system":
                prompt_lines.append(f"[System: {msg.content}]")
            else:
                prompt_lines.append(f"User: {msg.content}")

        prompt_lines.append("Gemini:")
        combined_prompt = "\n\n".join(prompt_lines)

        return await self.generate_content(
            prompt=combined_prompt,
            model=model,
            system_instruction=None,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def list_models(self) -> List[ModelInfo]:
        return WEB_MODELS

    async def health_check(self) -> bool:
        return bool(self._secure_1psid)
