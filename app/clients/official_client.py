import logging
logger = logging.getLogger(__name__)
from typing import List, Optional, Dict, Any
import httpx
from app.clients.base import BaseGeminiClient
from app.models.chat import ChatMessage, ModelInfo
from app.config import settings

# Danh sách các model chính thức phổ biến của Google Gemini
DEFAULT_MODELS = [
    ModelInfo(
        id="gemini-3.8-flash",
        name="Gemini 3.8 Flash",
        description="Mô hình thế hệ mới nhất của Google: Siêu nhanh, thông minh và tiết kiệm tài nguyên."
    ),
    ModelInfo(
        id="gemini-flash-latest",
        name="Gemini Flash Latest",
        description="Phiên bản Flash mới nhất tự động cập nhật của Google."
    ),
    ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash (Tự động ánh xạ sang 3.8 Flash)",
        description="Tương thích ngược cho các công cụ AI yêu cầu gemini-2.0-flash."
    ),
]


class OfficialGeminiClient(BaseGeminiClient):
    """Client kết nối trực tiếp đến Google Gemini API chính thức qua HTTP REST.

    Đặc điểm:
    - Sử dụng chuẩn API v1beta của Google.
    - Không phụ thuộc vào thư viện bên ngoài cồng kềnh, hoạt động cực nhanh qua HTTPX Async.
    - Tự động chuyển đổi vai trò (role) từ chuẩn OpenAI (user, assistant, system) sang chuẩn Gemini (user, model).
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def backend_name(self) -> str:
        return "official"

    def _resolve_model(self, model: Optional[str]) -> str:
        """Chuẩn hóa tên model, nếu model là tên từ OpenAI (như gpt-4) thì chuyển về model mặc định."""
        if not model or model.strip() == "":
            return settings.DEFAULT_MODEL
        m = model.strip()
        # Nếu công cụ AI gửi model dạng OpenAI, ta tự động dùng default model
        if m.startswith("gpt-") or m.startswith("text-davinci") or m.startswith("claude"):
            return settings.DEFAULT_MODEL
        # Bỏ tiền tố models/ nếu có
        if m.startswith("models/"):
            m = m[len("models/"):]
        return m

    def _convert_messages(self, messages: List[ChatMessage]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Chuyển đổi danh sách tin nhắn sang định dạng contents và systemInstruction của Gemini."""
        contents: List[Dict[str, Any]] = []
        system_instructions: List[str] = []

        for msg in messages:
            role = msg.role.lower().strip()
            text = msg.content

            if role in ("system", "developer"):
                system_instructions.append(text)
            elif role in ("assistant", "model"):
                contents.append({
                    "role": "model",
                    "parts": [{"text": text}]
                })
            else:
                # Mọi vai trò khác (user, human, ...) xem là user
                contents.append({
                    "role": "user",
                    "parts": [{"text": text}]
                })

        combined_system = "\n\n".join(system_instructions) if system_instructions else None
        return contents, combined_system

    async def _call_gemini_api(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Gửi request HTTP đến Google Gemini API."""
        if not self._api_key or self._api_key in ("YOUR_GEMINI_API_KEY_HERE", "YOUR_API_KEY"):
            raise ValueError(
                "Chưa cấu hình GEMINI_API_KEY! "
                "Vui lòng mở file .env trong thư mục dự án và điền mã Gemini API Key của bạn."
            )

        endpoint = f"{self.base_url}/models/{model}:generateContent"
        params = {"key": self._api_key}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        candidate_models = [model]
        if settings.DEFAULT_MODEL not in candidate_models:
            candidate_models.append(settings.DEFAULT_MODEL)
        for m_name in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.8-flash"]:
            if m_name not in candidate_models:
                candidate_models.append(m_name)

        response = None
        last_error_msg = ""
        for target_m in candidate_models:
            endpoint = f"{self.base_url}/models/{target_m}:generateContent"
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    res = await client.post(endpoint, params=params, headers=headers, json=body)
                    if res.status_code == 200:
                        response = res
                        break
                    else:
                        try:
                            last_error_msg = res.json().get("error", {}).get("message", res.text)
                        except Exception:
                            last_error_msg = res.text
                except httpx.RequestError as exc:
                    last_error_msg = str(exc)

        if response is None or response.status_code != 200:
            raise RuntimeError(f"Google Gemini trả về lỗi: {last_error_msg}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "Không nhận được phản hồi từ mô hình."

        first_candidate = candidates[0]
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return ""

        return "".join(part.get("text", "") for part in parts)

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._resolve_model(model)
        contents = [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
        return await self._call_gemini_api(
            model=target_model,
            contents=contents,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._resolve_model(model)
        contents, extracted_system = self._convert_messages(messages)

        # Kết hợp system instruction truyền thêm (nếu có)
        final_system = system_instruction or extracted_system
        if system_instruction and extracted_system and system_instruction != extracted_system:
            final_system = f"{system_instruction}\n\n{extracted_system}"

        return await self._call_gemini_api(
            model=target_model,
            contents=contents,
            system_instruction=final_system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """Truyền phát trực tiếp từng token từ Google Gemini qua SSE."""
        if not self._api_key or self._api_key in ("YOUR_GEMINI_API_KEY_HERE", "YOUR_API_KEY"):
            raise ValueError(
                "Chưa cấu hình GEMINI_API_KEY! "
                "Vui lòng mở file .env trong thư mục dự án và điền mã Gemini API Key của bạn."
            )

        target_model = self._resolve_model(model)
        contents, extracted_system = self._convert_messages(messages)
        final_system = system_instruction or extracted_system
        if system_instruction and extracted_system and system_instruction != extracted_system:
            final_system = f"{system_instruction}\n\n{extracted_system}"

        params = {"key": self._api_key, "alt": "sse"}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if final_system:
            body["systemInstruction"] = {
                "parts": [{"text": final_system}]
            }

        candidate_models = [target_model]
        if settings.DEFAULT_MODEL not in candidate_models:
            candidate_models.append(settings.DEFAULT_MODEL)
        for m_name in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
            if m_name not in candidate_models:
                candidate_models.append(m_name)

        import json
        streamed_any = False
        for m in candidate_models:
            endpoint = f"{self.base_url}/models/{m}:streamGenerateContent"
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream("POST", endpoint, params=params, headers=headers, json=body) as res:
                        if res.status_code == 200:
                            async for line in res.aiter_lines():
                                if line.startswith("data:"):
                                    data_str = line[5:].strip()
                                    if not data_str:
                                        continue
                                    try:
                                        data = json.loads(data_str)
                                        candidates = data.get("candidates", [])
                                        if candidates:
                                            parts = candidates[0].get("content", {}).get("parts", [])
                                            for p in parts:
                                                txt = p.get("text", "")
                                                if txt:
                                                    streamed_any = True
                                                    yield txt
                                    except Exception:
                                        continue
                            if streamed_any:
                                return
            except Exception:
                continue

        # Fallback nếu stream thất bại
        if not streamed_any:
            reply = await self.chat(
                messages=messages,
                model=target_model,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            words = reply.split(" ")
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")


    async def generate_images(self, prompt: str, n: int = 1) -> List[str]:
        """Tạo ảnh AI - Tự động ủy quyền cho BrowserAdapter (Imagen 3) để tận dụng ảnh chất lượng cao nhất."""
        from app.clients.factory import get_gemini_client
        browser_client = get_gemini_client("browser")
        return await browser_client.generate_images(prompt, n=n)

    async def list_models(self) -> List[ModelInfo]:
        return DEFAULT_MODELS

    async def health_check(self) -> bool:
        """Kiểm tra tính hợp lệ cơ bản của API key."""
        return bool(self._api_key and self._api_key != "YOUR_GEMINI_API_KEY_HERE")
