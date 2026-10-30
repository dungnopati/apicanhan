from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.chat import ChatMessage, ModelInfo


class BaseGeminiClient(ABC):
    """Lớp trừu tượng định nghĩa giao diện chung cho mọi kết nối Gemini.

    Nhờ lớp này, bạn có thể dễ dàng đổi từ Gemini API chính thức sang bất kỳ
    phương thức kết nối nào khác mà không phải sửa đổi code của FastAPI server.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Tên định danh của phương thức kết nối (vd: 'official', 'webapi')."""
        pass

    @abstractmethod
    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Gửi prompt đơn lẻ và nhận về câu trả lời bằng văn bản."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Gửi chuỗi lịch sử hội thoại nhiều lượt và nhận về câu trả lời."""
        pass

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """Streaming generator: gửi chuỗi hội thoại và trả về từng phần văn bản."""
        reply = await self.chat(
            messages=messages,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        words = reply.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """Trả về danh sách các mô hình Gemini được hỗ trợ."""
        pass

    async def generate_images(self, prompt: str, n: int = 1) -> List[str]:
        """Tạo ảnh từ văn bản mô tả và trả về danh sách URL ảnh."""
        return []

    async def generate_video(
        self,
        prompt: str,
        service: str = "flow",
        aspect_ratio: str = "16:9",
        duration: int = 10,
    ) -> str:
        """Tạo video từ văn bản mô tả và trả về URL video MP4."""
        return ""

    @abstractmethod
    async def health_check(self) -> bool:
        """Kiểm tra kết nối và tính sẵn sàng của client."""
        pass
