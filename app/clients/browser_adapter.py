import base64
import os
import asyncio
import logging
import uuid
import urllib.parse
from pathlib import Path
from typing import List, Optional
import httpx

from app.clients.base import BaseGeminiClient
from app.models.chat import ChatMessage, ModelInfo
from app.config import settings
from app.clients.locks import browser_lock

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "generated_images"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

BROWSER_MODELS = [
    ModelInfo(
        id="gemini-web-browser",
        name="Gemini Web (Trình duyệt cá nhân)",
        description="Điều khiển trực tiếp tài khoản Google Gemini cá nhân trên Microsoft Edge / Chrome."
    ),
    ModelInfo(
        id="google-flow",
        name="Google Flow (AI Video Studio)",
        description="Tạo video cinematic bằng Gemini Omni / Veo trên Google Flow cá nhân."
    ),
    ModelInfo(
        id="google-vids",
        name="Google Vids (AI Video Editor)",
        description="Tạo video và phân cảnh thuyết trình bằng tài khoản Google Vids cá nhân."
    ),
]


class BrowserAdapter(BaseGeminiClient):
    """Bộ điều hợp tự động hóa trình duyệt (Microsoft Edge / Google Chrome).

    Đặc điểm:
    - Mở cửa sổ trình duyệt thật với hồ sơ người dùng cá nhân (chỉ cần đăng nhập Google 1 lần).
    - Tạo ảnh Imagen 3 trực tiếp từ tài khoản Gemini cá nhân mà không bị Google chặn.
    - Không lo bị hết hạn cookie __Secure-1PSIDTS sau vài tiếng.
    """

    def __init__(self):
        self._playwright = None
        self._context = None
        self._page = None
        self._lock = browser_lock
        self._profile_dir = BASE_DIR / settings.BROWSER_PROFILE_DIR
        self._profile_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "browser"

    def _cleanup_orphaned_locks(self):
        """Dọn dẹp lockfile mồ côi nếu phiên trước bị tắt đột ngột mà không kill tiến trình trình duyệt."""
        lock = self._profile_dir / "lockfile"
        if lock.exists():
            try:
                lock.unlink()
            except Exception:
                pass

    async def _ensure_browser(self):
        """Khởi động hoặc tái sử dụng cửa sổ trình duyệt Edge/Chrome cố định trên màn hình."""
        if self._page is not None and not self._page.is_closed():
            return self._page

        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        # 1. Thử kết nối vào trình duyệt Edge đã mở sẵn qua remote debugging port 9222
        try:
            cdp_browser = await self._playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=1500)
            if cdp_browser.contexts:
                self._context = cdp_browser.contexts[0]
                pages = self._context.pages
                for p in pages:
                    if "gemini.google.com" in p.url:
                        self._page = p
                        break
                if not self._page and pages:
                    self._page = pages[0]
                if self._page:
                    logger.info("Đã kết nối vào cửa sổ trình duyệt Edge đang mở sẵn (CDP:9222)!")
                    if "gemini.google.com" not in self._page.url:
                        await self._page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=45000)
                    return self._page
        except Exception:
            pass

        # 2. Nếu chưa mở, thử khởi động Edge trực tiếp qua Windows shell để đảm bảo hiển thị cửa sổ thật trên màn hình
        import sys, subprocess
        if sys.platform == "win32":
            try:
                self._cleanup_orphaned_locks()
                cmd = f'start "" msedge.exe --remote-debugging-port=9222 --user-data-dir="{self._profile_dir}" --start-maximized "https://gemini.google.com/app"'
                subprocess.Popen(cmd, shell=True)
                for _ in range(8):
                    await asyncio.sleep(0.5)
                    try:
                        cdp_browser = await self._playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=1500)
                        if cdp_browser.contexts:
                            self._context = cdp_browser.contexts[0]
                            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
                            logger.info("Đã kết nối thành công vào cửa sổ Edge vừa mở trên màn hình!")
                            return self._page
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Không thể mở Edge qua Windows shell: {e}")

        channel = settings.BROWSER_CHANNEL
        headless = settings.BROWSER_HEADLESS

        logger.info(f"Đang mở cửa sổ trình duyệt {channel.upper()} (headless={headless})...")

        args = [
            "--remote-debugging-port=9222",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--start-maximized",
            "--disable-background-mode",
            "--disable-backgrounding-occluded-windows",
        ]

        # Kiểm tra xem có tiến trình nào đang chiếm lockfile không
        lock = self._profile_dir / "lockfile"
        if lock.exists():
            self._cleanup_orphaned_locks()

        channels_to_try = [channel]
        if channel == "msedge" and "chrome" not in channels_to_try:
            channels_to_try.append("chrome")
        elif channel == "chrome" and "msedge" not in channels_to_try:
            channels_to_try.append("msedge")
        channels_to_try.append(None)  # None = default bundled chromium

        self._context = None
        last_launch_err = None
        for ch in channels_to_try:
            try:
                self._cleanup_orphaned_locks()
                launch_kwargs = {
                    "user_data_dir": str(self._profile_dir),
                    "headless": headless,
                    "no_viewport": True,
                    "args": args,
                    "timeout": 45000,
                }
                if ch:
                    launch_kwargs["channel"] = ch
                self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
                break
            except Exception as e:
                last_launch_err = e
                logger.warning(f"Mở trình duyệt với channel '{ch}' không thành công: {e}. Thử kênh tiếp theo...")
                await asyncio.sleep(0.5)

        if not self._context:
            raise RuntimeError(f"Không thể khởi động trình duyệt sau khi thử các kênh {channels_to_try}: {last_launch_err}")

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()

        # Điều hướng đến Gemini nếu chưa ở trang đó
        if "gemini.google.com" not in self._page.url:
            logger.info("Đang mở trang https://gemini.google.com/app ...")
            try:
                await self._page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                logger.warning(f"Cảnh báo khi tải trang Gemini: {exc}")

        return self._page

    async def check_login_status(self) -> bool:
        """Kiểm tra xem người dùng đã đăng nhập Google trên trình duyệt chưa."""
        page = await self._ensure_browser()
        try:
            # Nếu xuất hiện ô soạn prompt (div.ql-editor hoặc div[contenteditable]) thì đã sẵn sàng
            editor = await page.query_selector('rich-textarea, div.ql-editor, [contenteditable="true"]')
            if editor:
                return True

            # Kiểm tra nút Sign in / Đăng nhập
            sign_in_btns = await page.query_selector_all('button:has-text("Sign in"), a:has-text("Sign in"), button:has-text("Đăng nhập")')
            if sign_in_btns:
                return False

            # Chờ thêm 3 giây phòng trường hợp đang tải
            await page.wait_for_timeout(3000)
            editor = await page.query_selector('rich-textarea, div.ql-editor, [contenteditable="true"]')
            return bool(editor)
        except Exception:
            return False

    async def generate_images(self, prompt: str, n: int = 1) -> List[str]:
        """Tạo ảnh từ Gemini Web (Imagen 3) và tải về URL máy chủ cục bộ chất lượng cao."""
        async with self._lock:
            page = await self._ensure_browser()

            is_logged = await self.check_login_status()
            if not is_logged:
                raise RuntimeError(
                    "Cửa sổ Microsoft Edge đã được mở nhưng bạn chưa đăng nhập tài khoản Google! "
                    "Vui lòng nhấp vào cửa sổ Microsoft Edge trên màn hình, đăng nhập tài khoản Google của bạn một lần duy nhất."
                )

            # Chuẩn bị prompt rõ ràng cho Imagen 3
            clean_prompt = prompt.strip()
            if not clean_prompt.lower().startswith(("create an image", "generate an image", "tạo ảnh", "vẽ ảnh")):
                final_prompt = f"Create an image: {clean_prompt}"
            else:
                final_prompt = clean_prompt

            # Bấm Cuộc trò chuyện mới nếu có
            try:
                new_chat_btn = await page.query_selector('a[href="/app"], button[aria-label*="New chat"], button[aria-label*="Cuộc trò chuyện mới"], [data-test-id="new-chat-button"]')
                if new_chat_btn:
                    await new_chat_btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

            # Thu thập tất cả các URL ảnh hiện có trên trang trước khi gửi prompt mới
            initial_gg_srcs = set()
            try:
                for img in await page.query_selector_all('img'):
                    src = await img.get_attribute("src") or ""
                    if src:
                        initial_gg_srcs.add(src)
            except Exception:
                pass

            # Tìm ô nhập liệu
            editor = await page.wait_for_selector('rich-textarea, div.ql-editor, [contenteditable="true"]', timeout=20000)
            if not editor:
                raise RuntimeError("Không tìm thấy ô nhập prompt trên Gemini Web!")

            # Focus và điền prompt chuẩn xác
            await editor.click()
            await page.wait_for_timeout(300)
            try:
                await page.keyboard.insert_text(final_prompt)
            except Exception:
                await editor.fill(final_prompt)
            await page.wait_for_timeout(600)

            # Thử click nút Send nếu có, hoặc nhấn Enter
            send_btn = await page.query_selector('button[aria-label*="Send message"], button[aria-label*="Gửi tin nhắn"], button[aria-label*="Send"], button[aria-label*="Gửi"], [data-test-id="send-button"]')
            if send_btn and await send_btn.is_enabled():
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")
            
            # Lưu ảnh chụp màn hình sau khi gửi prompt để theo dõi
            try:
                await page.screenshot(path=str(OUTPUTS_DIR / "after_send.png"))
            except Exception:
                pass
            logger.info(f"Đã gửi yêu cầu tạo ảnh tới Gemini Web: {final_prompt[:80]}...")

            image_urls = []
            max_wait_seconds = 180
            start_time = asyncio.get_event_loop().time()

            await page.wait_for_timeout(5000)

            while (asyncio.get_event_loop().time() - start_time) < max_wait_seconds:
                elapsed = asyncio.get_event_loop().time() - start_time

                # Tìm các thẻ img sinh ra (blob:, /gg/, hoặc img.image), lọc bỏ các ảnh đã có sẵn từ trước
                imgs = await page.query_selector_all('img.image, img[src*="/gg/"], img[src^="blob:"], img[src*="googleusercontent"]')
                img = None
                for cand in reversed(imgs):
                    cand_src = await cand.get_attribute("src") or ""
                    if cand_src and cand_src in initial_gg_srcs:
                        continue
                    is_loaded = await cand.evaluate("e => (e.naturalWidth > 200 || e.width > 200) && !e.classList.contains('animating')")
                    if is_loaded:
                        img = cand
                        break

                if img:
                        await page.wait_for_timeout(2000)
                        # Di chuyển chuột ra ngoài để tắt overlay hover buttons
                        await page.mouse.move(0, 0)
                        await page.wait_for_timeout(500)

                        try:
                            # 1. Trích xuất ảnh độ phân giải gốc thực sự (naturalWidth x naturalHeight) qua HTML5 Canvas
                            data_url = await img.evaluate('''e => {
                                try {
                                    const nw = e.naturalWidth || e.width;
                                    const nh = e.naturalHeight || e.height;
                                    const canvas = document.createElement('canvas');
                                    canvas.width = nw;
                                    canvas.height = nh;
                                    const ctx = canvas.getContext('2d');
                                    ctx.drawImage(e, 0, 0, nw, nh);
                                    return canvas.toDataURL('image/png');
                                } catch (err) {
                                    return null;
                                }
                            }''')
                            img_data = None
                            if data_url and data_url.startswith("data:image/"):
                                _, b64 = data_url.split(",", 1)
                                img_data = base64.b64decode(b64)

                            # Dự phòng chụp element nếu canvas gặp hạn chế
                            if not img_data or len(img_data) < 8000:
                                img_data = await img.screenshot()
                            if len(img_data) > 8000:
                                filename = f"imagen3_{uuid.uuid4().hex[:12]}.png"
                                out_file = OUTPUTS_DIR / filename
                                with open(out_file, "wb") as f:
                                    f.write(img_data)
                                local_url = f"http://127.0.0.1:{settings.PORT}/outputs/{filename}"
                                image_urls.append(local_url)
                                logger.info(f"Đã trích xuất thành công ảnh Imagen 3 sạch sẽ vào: {out_file} ({len(img_data):,} bytes)")
                                break
                        except Exception as err:
                            logger.warning(f"Lỗi khi chụp element screenshot: {err}")

                # Kiểm tra xem Gemini có trả lời văn bản từ chối hay không
                stop_btn = await page.query_selector('button[aria-label*="Stop"], button[aria-label*="Dừng"]')
                if not stop_btn and elapsed > 25:
                    send_btn_active = await page.query_selector('button[aria-label*="Send message"], button[aria-label*="Gửi tin nhắn"], button[aria-label*="Send"], button[aria-label*="Gửi"]')
                    if send_btn_active:
                        text_els = await page.query_selector_all('response-container, .model-response-text, .message-content, message-content')
                        last_text = ""
                        if text_els:
                            last_text = (await text_els[-1].inner_text()).strip()
                        if last_text and any(w in last_text.lower() for w in ["tôi không thể", "xin lỗi", "không thể tạo", "i cannot", "sorry"]):
                            raise RuntimeError(f"Gemini Web từ chối tạo ảnh: {last_text}")

                await page.wait_for_timeout(3000)

            if not image_urls:
                raise RuntimeError(
                    "Gemini Web không trả về hình ảnh nào cho prompt này sau thời gian chờ. "
                    "Vui lòng kiểm tra lại cửa sổ Microsoft Edge."
                )

            logger.info(f"Đã lấy thành công {len(image_urls)} ảnh từ Gemini Web (Imagen 3)!")
            return image_urls[:n] if n > 0 else image_urls

    async def generate_video(
        self,
        prompt: str,
        service: str = "flow",
        aspect_ratio: str = "16:9",
        duration: int = 10,
    ) -> str:
        """Tạo video từ Google Vids hoặc Google Flow bằng tài khoản cá nhân."""
        from app.clients.video_generator import video_manager
        return await video_manager.generate_video(
            prompt=prompt,
            service=service,
            aspect_ratio=aspect_ratio,
            duration=duration,
        )

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        logger.info(f"[generate_content] Nhận yêu cầu chat: {prompt[:60]}...")
        async with self._lock:
            page = await self._ensure_browser()
            is_logged = await self.check_login_status()
            logger.info(f"[generate_content] Trạng thái đăng nhập: {is_logged}")
            if not is_logged:
                raise RuntimeError("Vui lòng đăng nhập tài khoản Google trên cửa sổ Microsoft Edge đang mở.")

            final_prompt = prompt
            if system_instruction:
                final_prompt = f"[System: {system_instruction}]\n\n{prompt}"

            # Mở cuộc trò chuyện mới để tránh bị lẫn ngữ cảnh cũ
            try:
                new_chat_btn = await page.query_selector('a[href="/app"], button[aria-label*="New chat"], button[aria-label*="Cuộc trò chuyện mới"], [data-test-id="new-chat-button"]')
                if new_chat_btn:
                    logger.info("[generate_content] Đang bấm nút Cuộc trò chuyện mới...")
                    await new_chat_btn.click()
                    await page.wait_for_timeout(1500)
            except Exception as e:
                logger.warning(f"[generate_content] Không thể bấm new chat: {e}")

            logger.info("[generate_content] Đang tìm ô soạn thảo...")
            editor = await page.wait_for_selector('rich-textarea, div.ql-editor, [contenteditable="true"]', timeout=20000)
            await editor.click()
            await page.wait_for_timeout(300)
            logger.info("[generate_content] Đang điền nội dung prompt...")
            try:
                await page.keyboard.insert_text(final_prompt)
            except Exception:
                await editor.fill(final_prompt)
            await page.wait_for_timeout(500)

            # Click nút gửi tin nhắn hoặc nhấn Control+Enter
            send_btn = await page.query_selector('button[aria-label*="Send message"], button[aria-label*="Gửi tin nhắn"], button[aria-label*="Send"], button[aria-label*="Gửi"], [data-test-id="send-button"]')
            if send_btn and await send_btn.is_enabled():
                logger.info("[generate_content] Đang click nút Send...")
                await send_btn.click()
            else:
                logger.info("[generate_content] Không thấy Send btn, nhấn Enter...")
                await page.keyboard.press("Control+Enter")
                await page.wait_for_timeout(300)
                await page.keyboard.press("Enter")

            # Chờ Gemini Web xử lý và phản hồi
            logger.info("[generate_content] Đang chờ phản hồi từ Gemini Web...")
            await page.wait_for_timeout(2000)
            start_t = asyncio.get_event_loop().time()
            max_wait_secs = 180
            last_text = ""
            stable_ticks = 0

            while (asyncio.get_event_loop().time() - start_t) < max_wait_secs:
                is_pending = await page.query_selector('pending-response, button[aria-label*="Stop"], button[aria-label*="Dừng"]')
                text_els = await page.query_selector_all('model-response-content, .response-content, response-container, .model-response-text, message-content, .message-content')
                curr_text = ""
                if text_els:
                    curr_text = (await text_els[-1].inner_text()).strip()

                if not is_pending and curr_text:
                    if curr_text == last_text:
                        stable_ticks += 1
                        if stable_ticks >= 2:
                            logger.info(f"[generate_content] Hoàn tất phản hồi ({len(curr_text)} chars)!")
                            return curr_text
                    else:
                        stable_ticks = 0
                        last_text = curr_text
                elif curr_text:
                    last_text = curr_text

                await page.wait_for_timeout(1000)

            if last_text:
                logger.info(f"[generate_content] Hết giờ chờ, trả về kết quả cuối ({len(last_text)} chars)")
                return last_text
            return "Đã nhận được phản hồi từ Gemini Web."

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

        if len(messages) == 1:
            return await self.generate_content(
                prompt=messages[0].content,
                model=model,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        prompt_lines = []
        if system_instruction:
            prompt_lines.append(f"[System: {system_instruction}]")

        for msg in messages:
            role = msg.role.lower().strip()
            if role in ("assistant", "model"):
                prompt_lines.append(f"Gemini: {msg.content}")
            elif role in ("system", "developer"):
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
        return BROWSER_MODELS

    async def health_check(self) -> bool:
        try:
            return await self.check_login_status()
        except Exception:
            return False

    async def close(self):
        """Ngắt kết nối Playwright khi dừng server mà vẫn giữ nguyên cửa sổ trình duyệt cho người dùng."""
        try:
            # Không gọi self._context.close() để cửa sổ Edge luôn nằm nguyên trên màn hình
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Lỗi khi ngắt kết nối Playwright: {e}")
