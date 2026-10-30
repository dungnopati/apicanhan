import re
import asyncio
import base64
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
VIDEOS_DIR = BASE_DIR / "outputs" / "generated_videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


from app.clients.locks import browser_lock


class VideoAutomationManager:
    """Quản lý tự động hóa tạo video AI trên Google Vids và Google Flow qua trình duyệt Edge/Chrome trực quan."""

    _vids_disabled_until: float = 0.0
    _flow_disabled_until: float = 0.0

    def __init__(self):
        self._lock = browser_lock
        self._profile_dir = BASE_DIR / settings.BROWSER_PROFILE_DIR
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context = None

    def _cleanup_orphaned_locks(self):
        """Xóa lockfile nếu phiên trước bị dừng đột ngột."""
        lock = self._profile_dir / "lockfile"
        if lock.exists():
            try:
                lock.unlink()
            except Exception:
                pass

    async def _ensure_browser_context(self):
        """Khởi động hoặc tái sử dụng context trình duyệt Edge/Chrome trực quan trên màn hình."""
        if self._context is not None:
            try:
                if self._context.pages:
                    return self._context
            except Exception:
                self._context = None

        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        # 1. Kết nối vào cửa sổ trình duyệt Edge đang mở sẵn qua remote debugging port 9222
        try:
            cdp_browser = await self._playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=2000)
            if cdp_browser.contexts:
                self._context = cdp_browser.contexts[0]
                logger.info("[VideoManager] Đã kết nối vào cửa sổ Edge đang mở sẵn trên màn hình (CDP:9222)!")
                return self._context
        except Exception:
            pass

        # 2. Nếu chưa mở, thử khởi động Edge qua Windows shell để đảm bảo hiển thị cửa sổ thật trên màn hình
        import sys, subprocess
        if sys.platform == "win32":
            try:
                self._cleanup_orphaned_locks()
                edge_exe = 'msedge.exe'
                for ep in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
                    if Path(ep).exists():
                        edge_exe = f'"{ep}"'
                        break
                cmd = f'start "" {edge_exe} --remote-debugging-port=9222 --user-data-dir="{self._profile_dir}" --start-maximized "https://muse.ai" "https://gemini.google.com/app"'
                subprocess.Popen(cmd, shell=True)
                for _ in range(16):
                    await asyncio.sleep(0.5)
                    try:
                        cdp_browser = await self._playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=1500)
                        if cdp_browser.contexts:
                            self._context = cdp_browser.contexts[0]
                            logger.info("[VideoManager] Đã kết nối vào cửa sổ Edge vừa mở trên màn hình!")
                            return self._context
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(f"[VideoManager] Mở Edge qua Windows shell không thành công: {exc}")

        # 3. Dự phòng mở qua Playwright launch_persistent_context (headless=False)
        self._cleanup_orphaned_locks()
        args = [
            "--remote-debugging-port=9222",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--start-maximized",
            "--disable-background-mode",
        ]

        channel = settings.BROWSER_CHANNEL
        channels_to_try = [channel]
        if channel == "msedge" and "chrome" not in channels_to_try:
            channels_to_try.append("chrome")
        elif channel == "chrome" and "msedge" not in channels_to_try:
            channels_to_try.append("msedge")
        channels_to_try.append(None)

        for ch in channels_to_try:
            try:
                self._cleanup_orphaned_locks()
                launch_kwargs = {
                    "user_data_dir": str(self._profile_dir),
                    "headless": False,  # Luôn giữ cửa sổ thật trên màn hình để người dùng thấy và đăng nhập
                    "no_viewport": True,
                    "args": args,
                    "timeout": 45000,
                }
                if ch:
                    launch_kwargs["channel"] = ch
                self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
                logger.info(f"[VideoManager] Đã mở cửa sổ trình duyệt {str(ch).upper()} trên màn hình!")
                return self._context
            except Exception as exc:
                logger.warning(f"[VideoManager] Kênh {ch} không khởi động được: {exc}")
                await asyncio.sleep(0.5)

        raise RuntimeError("Không thể mở cửa sổ trình duyệt Edge/Chrome. Vui lòng kiểm tra lại trình duyệt của bạn.")

    async def _wait_for_user_login(self, page, service_name: str, max_wait_login_secs: int = 180):
        """Kiểm tra và chờ người dùng đăng nhập tài khoản Google nếu cần thiết."""
        await page.bring_to_front()
        start_t = asyncio.get_event_loop().time()
        notified = False

        while (asyncio.get_event_loop().time() - start_t) < max_wait_login_secs:
            url = page.url
            is_login_page = ("accounts.google.com" in url) or ("login" in url.lower())
            
            has_signin_btn = await page.evaluate('''() => {
                const hasLoginPane = !!document.querySelector('[data-testid="native-auth-access-pane"]');
                const btns = Array.from(document.querySelectorAll('button, a'));
                const hasBtn = btns.some(b => {
                    const txt = (b.innerText || '').toLowerCase().trim();
                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                    return txt === 'log in' || txt === 'sign in' || txt.includes('đăng nhập') || aria.includes('sign in') || aria.includes('log in');
                });
                return hasLoginPane || hasBtn;
            }''')

            if is_login_page or has_signin_btn:
                if not notified:
                    logger.info(
                        f"[{service_name}] Cửa sổ trình duyệt đã được đưa lên màn hình. "
                        f"Vui lòng nhấp vào cửa sổ trình duyệt để đăng nhập tài khoản {service_name} của bạn. "
                        f"Hệ thống đang chờ và sẽ tự động tiếp tục ngay khi bạn đăng nhập xong..."
                    )
                    notified = True
                await page.wait_for_timeout(3000)
                continue

            if not is_login_page and not has_signin_btn:
                if notified:
                    logger.info(f"[{service_name}] Phát hiện đăng nhập tài khoản thành công! Tiếp tục xử lý...")
                    await page.wait_for_timeout(2000)
                return True

            await page.wait_for_timeout(2000)

        raise RuntimeError(
            f"Đã hết thời gian chờ đăng nhập tài khoản Google trên {service_name}. "
            f"Vui lòng hoàn tất đăng nhập trên cửa sổ trình duyệt đang mở trên màn hình rồi thử lại."
        )

    async def generate_video_flow(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 10,
        max_wait_seconds: int = 300,
    ) -> str:
        """Tạo video tự động tối ưu siêu tốc trên Google Flow (Veo 3.1) với cửa sổ trực quan mở trên màn hình."""
        # Thích ứng thời lượng: Google Flow Veo chỉ hỗ trợ 4s, 6s, 8s, 10s
        clean_dur = float(duration or 5.0)
        supported_dur = 10 if clean_dur >= 10.0 else min([4, 6, 8, 10], key=lambda x: abs(x - clean_dur))
        
        # Tối ưu prompt cho Google Flow: súc tích, lược bỏ các cụm trùng lặp gây cảnh báo hoạt động bất thường
        clean_prompt = prompt.strip()
        clean_prompt = re.sub(r'\b\d+-second clip\b', f'{supported_dur}-second clip', clean_prompt, flags=re.IGNORECASE)
        clean_prompt = re.sub(r'\bcontinuous motion over \d+ seconds\b', f'continuous motion over {supported_dur} seconds', clean_prompt, flags=re.IGNORECASE)
        # Lược bớt câu lặp nếu quá dài (>400 chars)
        if len(clean_prompt) > 400:
            clean_prompt = re.sub(r'(Vibrant saturated colors|rich textures|smooth physics|zero blur|sharp focus)[, ]*', '', clean_prompt, count=1, flags=re.IGNORECASE)
            clean_prompt = re.sub(r'\s+', ' ', clean_prompt).strip()

        async with self._lock:
            context = await self._ensure_browser_context()

            # Tìm tab flow.google.com đã mở sẵn hoặc mở tab mới
            page = None
            for p in context.pages:
                if "flow.google.com" in p.url:
                    page = p
                    break

            if not page:
                page = await context.new_page()
                logger.info("[Google Flow] Đang mở trang https://flow.google.com...")
                await page.goto("https://flow.google.com", wait_until="domcontentloaded", timeout=45000)

            await page.bring_to_front()
            await page.wait_for_timeout(1000)

            # 1. Kiểm tra trạng thái đăng nhập tài khoản Google
            await self._wait_for_user_login(page, "Google Flow")

            # 2. Nếu đang ở trang chủ, tái sử dụng dự án gần nhất thay vì tạo mới tràn lan
            if "/project/" not in page.url:
                recent_card = await page.query_selector('.project-card, a[href*="/project/"], [data-test-id*="project"]')
                if recent_card:
                    logger.info("[Google Flow] Đang mở dự án sẵn có gần nhất...")
                    await recent_card.click()
                    await page.wait_for_timeout(2500)
                else:
                    logger.info("[Google Flow] Đang tạo dự án mới...")
                    fab = await page.wait_for_selector(
                        'button.mat-mdc-fab, button:has-text("Dự án mới"), [aria-label*="Dự án mới"]',
                        timeout=12000
                    )
                    if fab:
                        await fab.click()
                        await page.wait_for_timeout(2500)

            # 3. Đóng các popup giới thiệu nếu có
            for sel in ['button:has-text("Bắt đầu")', 'button:has-text("Tôi hiểu")', 'button[aria-label*="Đóng"]']:
                try:
                    popup_btn = await page.query_selector(sel)
                    if popup_btn and await popup_btn.is_visible():
                        await popup_btn.click()
                        await page.wait_for_timeout(300)
                except Exception:
                    pass

            # 4. Tìm ô soạn thảo prompt câu lệnh sáng tạo
            editor = await page.wait_for_selector(
                '.ProseMirror, [aria-label*="Bạn muốn tạo gì"], [contenteditable="true"]',
                timeout=15000
            )
            if not editor:
                raise RuntimeError("Không tìm thấy ô nhập câu lệnh sáng tạo trên Google Flow.")

            await editor.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(100)
            
            # Gõ siêu tốc không chờ delay từng ký tự
            try:
                await page.keyboard.insert_text(clean_prompt)
            except Exception:
                await page.keyboard.type(clean_prompt, delay=2)
            await page.wait_for_timeout(500)

            # Ghi nhận các media đã có trước để không nhặt nhầm video cũ
            existing_vids = set(await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('video')).map(v => v.src || v.currentSrc || '').filter(Boolean);
            }'''))

            # 5. Bấm nút Bắt đầu tạo (arrow_forward)
            send_btn = await page.wait_for_selector(
                'button[aria-label*="Bắt đầu tạo"], button:has-text("arrow_forward"), .generate-icon-button',
                timeout=6000
            )
            if send_btn and await send_btn.is_enabled():
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")

            logger.info(f"[Google Flow] Đã gửi yêu cầu tạo video Veo: '{clean_prompt[:60]}...'. Đang theo dõi...")
            await page.wait_for_timeout(2000)

            # 6. Chờ AI tư duy, tự động duyệt tín dụng & lấy video thành phẩm
            start_t = asyncio.get_event_loop().time()
            video_data = None

            while (asyncio.get_event_loop().time() - start_t) < max_wait_seconds:
                # A. Tự động xử lý nút 'Thử lại' nếu có cảnh báo tạm thời
                try:
                    retry_btn = page.get_by_text("Thử lại", exact=True)
                    if await retry_btn.count() > 0 and await retry_btn.last.is_visible():
                        await retry_btn.last.click(force=True)
                        logger.info("[Google Flow] Đã tự động nhấp 'Thử lại'...")
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # B. Tự động phê duyệt tín dụng (chỉ click khi có tùy chọn radio chưa chọn)
                try:
                    unselected_radio = page.locator('div[role="radio"][aria-checked="false"]:has-text("Luôn phê duyệt"), div[role="radio"][aria-checked="false"]:has-text("Phê duyệt"), .option-row:not(.selected):has-text("phê duyệt")').last
                    if await unselected_radio.count() > 0 and await unselected_radio.is_visible():
                        await unselected_radio.scroll_into_view_if_needed()
                        await unselected_radio.click(force=True)
                        logger.info("[Google Flow] Đã tự động phê duyệt tín dụng bằng lựa chọn 'Luôn phê duyệt'!")
                        await page.wait_for_timeout(1500)
                except Exception as app_e:
                    logger.debug(f"[Google Flow] Lỗi nhẹ kiểm tra phê duyệt: {app_e}")

                # C. Rà soát video trên canvas: hover vào flow-video-tile đầu tiên để mount thẻ video
                try:
                    first_tile = page.locator('flow-video-tile').first
                    if await first_tile.count() > 0:
                        await first_tile.hover()
                except Exception:
                    pass

                # D. Kiểm tra trạng thái và tìm video mới
                status = await page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const isThinking = buttons.some(b => {
                        const txt = b.innerText || '';
                        const aria = b.getAttribute('aria-label') || '';
                        return txt.includes('Dừng') || txt.includes('Stop') || aria.includes('Dừng') || aria.includes('Stop');
                    });

                    // Tìm tất cả thẻ video hiện có
                    const vids = [];
                    document.querySelectorAll('video').forEach(v => {
                        const src = v.src || v.currentSrc || '';
                        if (src) vids.push(src);
                    });

                    return {isThinking, vids};
                }''')

                # Lấy video mới chưa có từ trước
                all_current_vids = [s for s in status.get("vids", []) if s and s not in existing_vids]
                if all_current_vids:
                    target_src = all_current_vids[-1]
                    logger.info(f"[Google Flow] Phát hiện video mới hoàn thành: {target_src[:80]}...")
                    try:
                        video_b64 = await page.evaluate('''async (url) => {
                            const resp = await fetch(url);
                            const blob = await resp.blob();
                            return new Promise((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                reader.onerror = reject;
                                reader.readAsDataURL(blob);
                            });
                        }''', target_src)
                        if video_b64:
                            video_data = base64.b64decode(video_b64)
                            break
                    except Exception as exc:
                        logger.warning(f"[Google Flow] Lỗi trích xuất video src: {exc}")

                await page.wait_for_timeout(2000)

            if not video_data:
                err_shot = VIDEOS_DIR / f"flow_timeout_{uuid.uuid4().hex[:6]}.png"
                await page.screenshot(path=str(err_shot))
                raise RuntimeError(
                    f"Google Flow chưa hoàn tất tạo video sau {max_wait_seconds}s. "
                    f"Cửa sổ Edge vẫn được giữ nguyên trên màn hình để bạn xem trực tiếp."
                )

            # Xác định định dạng tệp thực tế (MP4 hoặc WebP animation/video)
            is_webp = video_data.startswith(b"RIFF") and b"WEBP" in video_data[:16]
            ext = "webp" if is_webp else "mp4"
            filename = f"flow_{uuid.uuid4().hex[:12]}.{ext}"
            output_path = VIDEOS_DIR / filename
            with open(output_path, "wb") as f:
                f.write(video_data)

            local_url = f"http://127.0.0.1:{settings.PORT}/outputs/videos/{filename}"
            logger.info(f"[Google Flow] Đã lưu thành công video vào: {output_path} ({len(video_data):,} bytes)")
            return local_url

    async def generate_video_muse(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: int = 10,
        max_wait_seconds: int = 300,
    ) -> str:
        """Tạo video tự động trên Muse.ai với cửa sổ trình duyệt Edge trực quan mở trên màn hình."""
        clean_dur = float(duration or 5.0)
        supported_dur = max(4, min(15, int(round(clean_dur))))
        clean_prompt = prompt.strip()

        async with self._lock:
            context = await self._ensure_browser_context()

            # 1. Tìm tab muse.ai đã mở sẵn hoặc mở tab mới
            page = None
            for p in context.pages:
                if "muse.ai" in p.url.lower():
                    page = p
                    break

            if not page:
                page = await context.new_page()
                logger.info("[Muse.ai] Đang mở trang https://muse.ai...")
                await page.goto("https://muse.ai", wait_until="domcontentloaded", timeout=45000)

            await page.bring_to_front()
            await page.wait_for_timeout(1500)

            # 2. Kiểm tra trạng thái đăng nhập
            await self._wait_for_user_login(page, "Muse.ai")

            # 3. Ghi nhận các video đã có trước trên trang để không lấy nhầm (bỏ qua avatar/mascot)
            existing_vids = set(await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('video'))
                    .filter(v => {
                        if (v.closest('.rounded-full, [class*="avatar"], [class*="mascot"], [class*="rocky"], header, nav')) return false;
                        const vw = v.videoWidth || 0;
                        const vh = v.videoHeight || 0;
                        if (vw > 0 && vh > 0 && Math.abs(vw - vh) < 20) return false;
                        return true;
                    })
                    .map(v => v.src || v.currentSrc || '')
                    .filter(Boolean);
            }'''))

            # 4. Định vị ô nhập prompt trên muse.ai
            editor = None
            selectors = [
                'textarea',
                'div[contenteditable="true"]',
                'input[placeholder*="Ask"]',
                'input[placeholder*="task"]',
                'input[placeholder*="Message"]',
                'input[placeholder*="Prompt"]',
                'input[placeholder*="goal"]',
                '[role="textbox"]',
                'input[type="text"]:not([autocomplete="username"]):not([inputmode="email"])'
            ]
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el and await el.is_visible():
                        editor = el
                        break
                except Exception:
                    pass

            if not editor:
                for btn_sel in ['button:has-text("Try Muse")', 'a:has-text("Try Muse")', 'button:has-text("Get started")', 'button:has-text("New task")']:
                    try:
                        b = await page.query_selector(btn_sel)
                        if b and await b.is_visible():
                            await b.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
                
                for sel in selectors:
                    try:
                        el = await page.wait_for_selector(sel, timeout=3000)
                        if el and await el.is_visible():
                            editor = el
                            break
                    except Exception:
                        pass

            if not editor:
                err_shot = VIDEOS_DIR / f"muse_no_editor_{uuid.uuid4().hex[:6]}.png"
                await page.screenshot(path=str(err_shot))
                raise RuntimeError(
                    "Không tìm thấy ô nhập câu lệnh trên Muse.ai. "
                    "Vui lòng đảm bảo bạn đã đăng nhập và đang ở trang chính của Muse.ai trên cửa sổ Edge."
                )

            # 5. Nhập câu lệnh
            await editor.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(100)

            try:
                await page.keyboard.insert_text(clean_prompt)
            except Exception:
                await page.keyboard.type(clean_prompt, delay=2)
            await page.wait_for_timeout(500)

            # 6. Gửi câu lệnh (Enter hoặc Click nút Send)
            send_btn = None
            for b_sel in ['button[type="submit"]', 'button[aria-label*="Send"]', 'button[aria-label*="Generate"]', 'button:has-text("Send")']:
                try:
                    b = await page.query_selector(b_sel)
                    if b and await b.is_enabled():
                        send_btn = b
                        break
                except Exception:
                    pass

            if send_btn:
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")

            logger.info(f"[Muse.ai] Đã gửi yêu cầu tạo video: '{clean_prompt[:60]}...'. Đang theo dõi tiến trình...")
            await page.wait_for_timeout(3000)

            # 7. Theo dõi Rocky xử lý và trích xuất video thành phẩm
            start_t = asyncio.get_event_loop().time()
            video_data = None
            idle_streak = 0
            scene_markers = re.findall(r'\[Phân cảnh \d+', clean_prompt)
            expected_count = max(1, len(scene_markers))
            logger.info(f"[Muse.ai] Kỳ vọng nhận {expected_count} video clip độc lập cho các phân cảnh...")

            # Đợi 3 giây để Rocky cập nhật trạng thái bắt đầu tạo
            await page.wait_for_timeout(3000)

            while (asyncio.get_event_loop().time() - start_t) < max_wait_seconds:
                state = await page.evaluate('''() => {
                    const stopBtn = document.querySelector('button[aria-label*="Stop"], button[aria-label*="Arrêter"]');
                    const allText = document.body.innerText || '';
                    const isBusy = !!stopBtn || allText.includes('Creating video') || allText.includes('Creating ') || allText.includes('Thinking') || allText.includes('Generating');
                    const vids = Array.from(document.querySelectorAll('video'))
                        .filter(v => {
                            if (v.closest('.rounded-full, [class*="avatar"], [class*="mascot"], [class*="rocky"], header, nav')) return false;
                            const vw = v.videoWidth || 0;
                            const vh = v.videoHeight || 0;
                            if (vw > 0 && vh > 0 && Math.abs(vw - vh) < 20) return false;
                            return true;
                        })
                        .map(v => v.src || v.currentSrc || '')
                        .filter(Boolean);
                    const dlBtns = Array.from(document.querySelectorAll('button[aria-label*="Download"], button[aria-label*="Télécharger"]'));
                    
                    const msgs = Array.from(document.querySelectorAll('div[class*="message"], p')).map(e => e.innerText || '');
                    const lastMsg = msgs.length ? msgs[msgs.length - 1] : '';
                    const isRefused = lastMsg.includes('ne peux pas') || lastMsg.includes('cannot generate') || lastMsg.includes('unable to');
                    
                    return { isBusy, isRefused, lastMsg, vidCount: vids.length, dlCount: dlBtns.length, vids };
                }''')

                elapsed = int(asyncio.get_event_loop().time() - start_t)

                if state.get('isRefused'):
                    refused_msg = state.get('lastMsg', '')[:120]
                    raise RuntimeError(f"Muse.ai Rocky từ chối tạo video: {refused_msg}")

                # Lọc chính xác các video mới tạo, TUYỆT ĐỐI không lấy lại video cũ đã có từ trước
                current_vids = state.get('vids', [])
                new_vids = [v for v in current_vids if v and v not in existing_vids]
                has_new_vid = bool(new_vids) or (len(current_vids) > len(existing_vids))
                is_busy = state.get('isBusy')

                if not is_busy and has_new_vid:
                    idle_streak += 1
                else:
                    idle_streak = 0

                # Chỉ hoàn tất khi:
                # 1. Đã nhận đủ số lượng video kỳ vọng (ví dụ: đủ 5 video cho lô 5 cảnh)
                # 2. Hoặc Rocky đã hoàn toàn ngừng tạo (idle liên tục 15s) và có ít nhất 1 video mới
                is_count_ready = len(new_vids) >= expected_count and elapsed >= 10
                is_idle_ready = idle_streak >= 5 and has_new_vid and elapsed >= 20
                is_force_ready = (elapsed >= max_wait_seconds - 15) and has_new_vid

                if is_count_ready or is_idle_ready or is_force_ready:
                    download_targets = list(new_vids)
                    if not download_targets:
                        if is_force_ready:
                            logger.warning(f"[Muse.ai] Hết thời gian chờ nhưng không có video mới hợp lệ nào từ Rocky.")
                            break
                        continue

                    logger.info(f"[Muse.ai] Rocky đã hoàn tất {len(download_targets)} video MỚI sau {elapsed}s...")
                    downloaded_files = []
                    for v_src in download_targets:
                        try:
                            video_b64 = await page.evaluate('''async (url) => {
                                const resp = await fetch(url);
                                const blob = await resp.blob();
                                return new Promise((resolve, reject) => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                    reader.onerror = reject;
                                    reader.readAsDataURL(blob);
                                });
                            }''', v_src)
                            if video_b64:
                                raw_bytes = base64.b64decode(video_b64)
                                # Bỏ qua avatar mascot Rocky (< 450KB hoặc byte size cố định của avatar)
                                AVATAR_SIZES = {366749, 189619, 77099}
                                if len(raw_bytes) < 450_000 or len(raw_bytes) in AVATAR_SIZES:
                                    logger.warning(f"[Muse.ai] Bỏ qua video không hợp lệ ({len(raw_bytes)} bytes - avatar mascot Rocky)")
                                    continue
                                fn = f"muse_{uuid.uuid4().hex[:12]}.mp4"
                                out_p = VIDEOS_DIR / fn
                                with open(out_p, "wb") as f:
                                    f.write(raw_bytes)
                                downloaded_files.append(f"http://127.0.0.1:{settings.PORT}/outputs/videos/{fn}")
                        except Exception as exc:
                            logger.warning(f"[Muse.ai] Dang thu trich xuat video blob: {exc}")

                    if downloaded_files:
                        self._last_downloaded_urls = downloaded_files
                        video_data = True
                        local_url = downloaded_files[0]
                        break

                if elapsed % 15 == 0 and elapsed > 0:
                    logger.info(f"[Muse.ai] Dang cho Rocky ket xuat video moi... ({elapsed}s, busy={state.get('isBusy')}, new_vids={len(new_vids)})")

                await page.wait_for_timeout(3000)

            if not video_data:
                err_shot = VIDEOS_DIR / f"muse_timeout_{uuid.uuid4().hex[:6]}.png"
                await page.screenshot(path=str(err_shot))
                raise RuntimeError(
                    f"Muse.ai chua hoan tat tao video sau {max_wait_seconds}s. "
                    f"Cua so Edge van duoc giu nguyen tren man hinh de ban theo doi truc tiep."
                )

            logger.info(f"[Muse.ai] Da trich xuat thanh cong {len(self._last_downloaded_urls)} video tu Muse.ai Rocky!")
            return local_url

    async def generate_video(
        self,
        prompt: str,
        service: str = "muse",
        aspect_ratio: str = "16:9",
        duration: int = 10,
    ) -> str:
        """Bộ điều phối chọn dịch vụ tạo video (Ưu tiên Muse.ai số 1)."""
        target = (service or "muse").lower().strip()

        if "muse" in target:
            return await self.generate_video_muse(prompt, aspect_ratio=aspect_ratio, duration=duration)

        if "vid" in target or "flow" in target:
            return await self.generate_video_flow(prompt, aspect_ratio=aspect_ratio, duration=duration)

        return await self.generate_video_muse(prompt, aspect_ratio=aspect_ratio, duration=duration)


video_manager = VideoAutomationManager()
