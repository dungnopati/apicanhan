import logging
logging.basicConfig(level=logging.INFO)
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.config import settings
from app.routes.health import health_router
from app.routes.chat import chat_router
from app.routes.openai_compat import openai_router
from app.routes.video import video_router
from app.routes.payment import payment_router


import sys

# Đảm bảo console trên Windows không bị lỗi UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động máy chủ
    print("\n" + "=" * 60)
    print(" [*] GEMINIBRIDGE DA SAN SANG HOAT DONG")
    print(f" [*] Dia chi Server: http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}")
    print(f" [*] Giao dien Test (Swagger UI): http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}/docs")
    print(f" [*] Endpoint OpenAI tuong thich: http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}/v1")
    print(f" [*] Cong Nap Game / VietQR: http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}/payment-demo")
    print(f" [*] Endpoint Video tuong thich: http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}/v1/videos/generations")
    print(f" [*] Trang thai API Key: {settings.safe_api_key_preview}")
    print(f" [*] Mo hinh mac dinh: {settings.DEFAULT_MODEL}")
    print(f" [*] Kieu Backend: {settings.GEMINI_BACKEND_TYPE}")
    import asyncio
    import webbrowser
    from app.clients.factory import get_gemini_client, _cached_clients
    import os
    if not os.getenv("RENDER") and getattr(settings, 'GEMINI_BACKEND_TYPE', '') == 'browser':
        try:
            print(f" [*] Dang mo va giu san cua so trinh duyet {settings.BROWSER_CHANNEL.upper()} cho tinh nang tao anh va video...")
            browser_adapter = get_gemini_client("browser")
            asyncio.create_task(browser_adapter._ensure_browser())
        except Exception as e:
            print(f" [!] Khong the khoi dong trinh duyet tren Cloud: {e}")

    async def _auto_open_dashboard():
        await asyncio.sleep(1.0)
        try:
            webbrowser.open(f"http://{getattr(settings, 'HOST', '127.0.0.1')}:{settings.PORT}")
        except Exception:
            pass
    asyncio.create_task(_auto_open_dashboard())

    yield
    # Khi tắt máy chủ: đóng an toàn mọi client có kết nối nền
    for c in list(_cached_clients.values()):
        if hasattr(c, "close"):
            try:
                await c.close()
            except Exception:
                pass
    print("\n[GeminiBridge] May chu da dung an toan.\n")


app = FastAPI(
    title="GeminiBridge",
    description=(
        "Cổng kết nối GeminiClient trung tâm dùng chung cho nhiều công cụ AI.\n\n"
        "Hỗ trợ cả chuẩn REST API trực tiếp và chuẩn tương thích OpenAI (/v1/chat/completions, /v1/images/generations, /v1/videos/generations)."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# Cấu hình CORS để mọi phần mềm AI trên máy hoặc web đều có thể gọi API mà không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn các router chức năng
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(openai_router)
app.include_router(video_router)
app.include_router(payment_router)

from fastapi.staticfiles import StaticFiles
BASE_OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"
OUTPUTS_IMAGES_DIR = BASE_OUTPUTS / "generated_images"
OUTPUTS_VIDEOS_DIR = BASE_OUTPUTS / "generated_videos"
OUTPUTS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Mount các thư mục phục vụ static URL
app.mount("/outputs/videos", StaticFiles(directory=str(OUTPUTS_VIDEOS_DIR)), name="outputs_videos")
app.mount("/outputs/images", StaticFiles(directory=str(OUTPUTS_IMAGES_DIR)), name="outputs_images")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_IMAGES_DIR)), name="outputs")



@app.get("/", response_class=HTMLResponse, tags=["Trang chủ"])
async def root():
    """Trang chủ trực quan giới thiệu và hướng dẫn nhanh cho người dùng."""
    key_status = "ĐÃ CẤU HÌNH (Sẵn sàng)" if settings.is_api_key_valid else "CHƯA CẤU HÌNH (Cần điền vào .env)"
    key_color = "#10b981" if settings.is_api_key_valid else "#ef4444"

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GeminiBridge - Cổng kết nối AI & Video</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                color: #f8fafc;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
            }}
            .card {{
                background: rgba(30, 41, 59, 0.7);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 32px;
                max-width: 680px;
                width: 100%;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 9999px;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 12px;
                background: #3b82f6;
                color: #fff;
            }}
            h1 {{ font-size: 26px; margin-bottom: 10px; font-weight: 700; color: #fff; }}
            p.sub {{ color: #94a3b8; margin-bottom: 24px; font-size: 15px; }}
            .status-box {{
                background: rgba(15, 23, 42, 0.6);
                border-radius: 10px;
                padding: 16px;
                margin-bottom: 24px;
                border-left: 4px solid {key_color};
            }}
            .status-item {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }}
            .status-item:last-child {{ margin-bottom: 0; }}
            .status-label {{ color: #94a3b8; }}
            .status-value {{ font-weight: 600; color: #e2e8f0; }}
            .btn-group {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
            .btn {{
                flex: 1;
                min-width: 180px;
                text-align: center;
                padding: 12px 18px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
                transition: all 0.2s;
            }}
            .btn-primary {{ background: #3b82f6; color: #fff; }}
            .btn-primary:hover {{ background: #2563eb; transform: translateY(-2px); }}
            .btn-secondary {{ background: rgba(255, 255, 255, 0.1); color: #e2e8f0; }}
            .btn-secondary:hover {{ background: rgba(255, 255, 255, 0.2); transform: translateY(-2px); }}
            .feature-box {{
                margin-bottom: 24px;
                background: rgba(15, 23, 42, 0.6);
                padding: 20px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            .quick-guide {{
                background: rgba(15, 23, 42, 0.4);
                border-radius: 10px;
                padding: 16px;
                font-size: 13px;
                color: #cbd5e1;
                line-height: 1.6;
            }}
            .quick-guide code {{
                background: rgba(0, 0, 0, 0.4);
                padding: 2px 6px;
                border-radius: 4px;
                color: #60a5fa;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">GeminiBridge v1.1.0</span>
            <h1>Cổng Kết Nối Gemini & Tạo Video Dùng Chung</h1>
            <p class="sub">Kết nối Google Gemini, Imagen 3, Google Flow & Google Vids cho mọi ứng dụng AI.</p>

            <div class="status-box">
                <div class="status-item">
                    <span class="status-label">Trạng thái Server:</span>
                    <span class="status-value" style="color: #10b981;">● Đang hoạt động (Running)</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Trạng thái API Key:</span>
                    <span class="status-value" style="color: {key_color};">{key_status}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">API Key hiện tại:</span>
                    <span class="status-value"><code>{settings.safe_api_key_preview}</code></span>
                </div>
                <div class="status-item">
                    <span class="status-label">Mô hình mặc định:</span>
                    <span class="status-value">{settings.DEFAULT_MODEL}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Kiểu Backend:</span>
                    <span class="status-value">{settings.GEMINI_BACKEND_TYPE}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Tạo Video AI:</span>
                    <span class="status-value" style="color: #a855f7;">Google Flow (Veo) & Google Vids</span>
                </div>
            </div>

            <div class="btn-group" style="flex-wrap: wrap; gap: 10px;">
                <a href="/docs" class="btn btn-primary" target="_blank">📖 Swagger UI (Thử API ngay)</a>
                <a href="/health" class="btn btn-secondary" target="_blank">🔍 Kiểm tra Health Check</a>
                <a href="/open-browser?target=all" class="btn" style="background: #10b981; color: #fff;" target="_blank">🌐 Mở Cửa Sổ Trình Duyệt Cá Nhân</a>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; font-size: 13px;">
                <span style="color: #94a3b8; align-self: center;">Mở nhanh tab:</span>
                <a href="/open-browser?target=flow" target="_blank" style="padding: 6px 12px; border-radius: 6px; background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.4); color: #d8b4fe; text-decoration: none; font-weight: 500;">🎬 Google Flow</a>
                <a href="/open-browser?target=vids" target="_blank" style="padding: 6px 12px; border-radius: 6px; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4); color: #93c5fd; text-decoration: none; font-weight: 500;">📹 Google Vids</a>
                <a href="/open-browser?target=gemini" target="_blank" style="padding: 6px 12px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #6ee7b7; text-decoration: none; font-weight: 500;">🎨 Gemini Web</a>
            </div>

            <!-- Khối tạo Video AI trực tiếp -->
            <div class="feature-box" style="border-left: 4px solid #a855f7;">
                <h3 style="font-size: 16px; margin-bottom: 12px; color: #c084fc; display: flex; align-items: center; gap: 8px;">
                    🎬 Thử Tạo Video AI Trực Tiếp (Google Flow & Google Vids)
                </h3>
                <div style="display: flex; gap: 16px; margin-bottom: 12px; font-size: 13px;">
                    <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                        <input type="radio" name="videoService" value="flow" checked /> 
                        <span><b>Google Flow</b> (Cinematic / Veo Studio)</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                        <input type="radio" name="videoService" value="vids" /> 
                        <span><b>Google Vids</b> (Workspace / Omni Editor)</span>
                    </label>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input id="videoPromptInput" type="text" placeholder="Nhập mô tả cảnh video muốn AI tạo..." style="flex: 1; min-width: 240px; padding: 12px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.3); color: #fff; font-size: 14px;" value="Cinematic drone shot of turquoise ocean waves gently crashing onto tropical beach at sunset" />
                    <button onclick="generateVideo()" id="genVideoBtn" style="padding: 12px 22px; border-radius: 8px; border: none; background: #a855f7; color: #fff; font-weight: 600; cursor: pointer; transition: background 0.2s;">Tạo Video Ngay</button>
                </div>
                <div id="videoResult" style="margin-top: 14px; display: none; text-align: center;">
                    <p id="videoStatus" style="font-size: 13px; color: #94a3b8; margin-bottom: 10px; line-height: 1.5;"></p>
                    <video id="playerVideo" controls autoplay loop style="max-width: 100%; max-height: 360px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); display: none; margin: 0 auto;"></video>
                    <img id="playerImage" style="max-width: 100%; max-height: 360px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); display: none; margin: 0 auto;" />
                    <div style="margin-top: 10px;">
                        <a id="downloadVideoLink" href="" target="_blank" download style="display: none; color: #38bdf8; font-size: 13px; font-weight: 600; text-decoration: none;">⬇ Tải file media về máy</a>
                    </div>
                </div>
                <script>
                    async function generateVideo() {{
                        const prompt = document.getElementById('videoPromptInput').value.trim();
                        if (!prompt) return alert('Vui lòng nhập mô tả video!');
                        const service = document.querySelector('input[name="videoService"]:checked').value;
                        const btn = document.getElementById('genVideoBtn');
                        const resDiv = document.getElementById('videoResult');
                        const statusP = document.getElementById('videoStatus');
                        const video = document.getElementById('playerVideo');
                        const img = document.getElementById('playerImage');
                        const dlLink = document.getElementById('downloadVideoLink');

                        btn.disabled = true;
                        btn.innerText = 'Đang tạo video...';
                        resDiv.style.display = 'block';
                        video.style.display = 'none';
                        img.style.display = 'none';
                        dlLink.style.display = 'none';
                        const svcTitle = service === 'flow' ? 'Google Flow' : 'Google Vids';
                        statusP.innerHTML = `⏳ <b>Đang tạo video trên ${{svcTitle}}...</b><br><span style="font-size: 12px; color: #cbd5e1; margin-top: 4px; display: inline-block;">Cửa sổ Edge đang hiển thị trên màn hình. Nếu hệ thống cần đăng nhập tài khoản Google, bạn chỉ cần đăng nhập trực tiếp trên cửa sổ đó, công cụ sẽ tự động nhận diện và tiếp tục xử lý!</span>`;

                        try {{
                            const res = await fetch('/api/video/generate', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{prompt: prompt, service: service}})
                            }});
                            const data = await res.json();
                            if (res.ok && data.success && data.video_url) {{
                                statusP.innerHTML = `✅ <b>Tạo video thành công từ ${{data.service}}!</b>`;
                                const isImg = data.video_url.endsWith('.webp') || data.video_url.endsWith('.png') || data.video_url.endsWith('.jpg');
                                if (isImg) {{
                                    img.src = data.video_url;
                                    img.style.display = 'block';
                                    video.style.display = 'none';
                                }} else {{
                                    video.src = data.video_url;
                                    video.style.display = 'block';
                                    img.style.display = 'none';
                                }}
                                dlLink.href = data.video_url;
                                dlLink.style.display = 'inline-block';
                            }} else {{
                                statusP.innerHTML = `❌ <b>Lỗi:</b> ${{data.detail || JSON.stringify(data)}}<br><span style="font-size: 12px; color: #fca5a5; margin-top: 6px; display: inline-block;">💡 Mẹo: Bạn có thể bấm nút <a href="/open-browser?target=${{service}}" target="_blank" style="color: #38bdf8; text-decoration: underline;">Mở Trình Duyệt Cá Nhân</a> ở trên để kiểm tra đăng nhập tài khoản Google rồi bấm Thử lại.</span>`;
                            }}
                        }} catch (err) {{
                            statusP.innerHTML = `❌ <b>Lỗi kết nối:</b> ${{err.message}}<br><span style="font-size: 12px; color: #fca5a5; margin-top: 6px; display: inline-block;">💡 Vui lòng đảm bảo máy chủ đang chạy và nhấp <a href="/open-browser" target="_blank" style="color: #38bdf8; text-decoration: underline;">Mở Trình Duyệt</a> để kiểm tra.</span>`;
                        }} finally {{
                            btn.disabled = false;
                            btn.innerText = 'Tạo Video Ngay';
                        }}
                    }}
                </script>
            </div>

            <!-- Khối tạo ảnh trực tiếp ngay trên trang chủ -->
            <div class="feature-box" style="border-left: 4px solid #38bdf8;">
                <h3 style="font-size: 16px; margin-bottom: 12px; color: #38bdf8; display: flex; align-items: center; gap: 8px;">
                    🎨 Thử Tạo Ảnh Imagen 3 Trực Tiếp (Không Cần Mở Phần Mềm Khác)
                </h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <input id="promptInput" type="text" placeholder="Nhập mô tả ảnh tiếng Anh hoặc tiếng Việt..." style="flex: 1; min-width: 260px; padding: 12px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.3); color: #fff; font-size: 14px;" value="A cute cat wearing sunglasses on a beach" />
                    <button onclick="generateImage()" id="genBtn" style="padding: 12px 22px; border-radius: 8px; border: none; background: #3b82f6; color: #fff; font-weight: 600; cursor: pointer; transition: background 0.2s;">Tạo Ảnh Ngay</button>
                </div>
                <div id="genResult" style="margin-top: 14px; display: none; text-align: center;">
                    <p id="genStatus" style="font-size: 13px; color: #94a3b8; margin-bottom: 10px;"></p>
                    <a id="genLink" href="" target="_blank" style="display: inline-block;">
                        <img id="genImg" src="" style="max-width: 100%; max-height: 380px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); display: none;" />
                    </a>
                </div>
                <script>
                    async function generateImage() {{
                        const prompt = document.getElementById('promptInput').value.trim();
                        if (!prompt) return alert('Vui lòng nhập mô tả ảnh!');
                        const btn = document.getElementById('genBtn');
                        const resDiv = document.getElementById('genResult');
                        const statusP = document.getElementById('genStatus');
                        const img = document.getElementById('genImg');
                        const link = document.getElementById('genLink');
                        btn.disabled = true;
                        btn.innerText = 'Đang vẽ ảnh...';
                        resDiv.style.display = 'block';
                        img.style.display = 'none';
                        statusP.innerText = '⏳ Đang gửi yêu cầu tới Gemini Imagen 3, vui lòng chờ khoảng 20 giây...';
                        try {{
                            const res = await fetch('/v1/images/generations', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{prompt: prompt}})
                            }});
                            const data = await res.json();
                            if (res.ok && data.data && data.data[0]) {{
                                statusP.innerHTML = '✅ <b>Tạo ảnh thành công!</b> (Nhấp vào ảnh để xem kích thước gốc)';
                                img.src = data.data[0].url;
                                link.href = data.data[0].url;
                                img.style.display = 'inline-block';
                            }} else {{
                                statusP.innerText = '❌ Lỗi: ' + (data.error ? (data.error.message || JSON.stringify(data.error)) : 'Không tạo được ảnh');
                            }}
                        }} catch (err) {{
                            statusP.innerText = '❌ Lỗi kết nối: ' + err.message;
                        }} finally {{
                            btn.disabled = false;
                            btn.innerText = 'Tạo Ảnh Ngay';
                        }}
                    }}
                </script>
            </div>

            <div class="quick-guide">
                <strong>🔗 Kết nối vào phần mềm AI của bạn:</strong><br>
                • Base URL: <code>http://127.0.0.1:{settings.PORT}/v1</code><br>
                • Model Chat: <code>{settings.DEFAULT_MODEL}</code><br>
                • Model Video: <code>google-flow</code> hoặc <code>google-vids</code><br>
                • Video Endpoint: <code>POST /v1/videos/generations</code> hoặc <code>POST /api/video/generate</code><br>
                • Thử API bằng trình duyệt: Bấm nút <b>Swagger UI</b> ở trên để kiểm tra trực tiếp không cần code!
            </div>
        </div>
    </body>
    </html>
    """



@app.get("/api/debug-browser", tags=["Debug"])
async def debug_browser():
    """Kiểm tra trạng thái Edge và chụp màn hình debug."""
    from app.clients.factory import get_gemini_client
    client = get_gemini_client("browser")
    if hasattr(client, "_page") and client._page:
        ss_path = OUTPUTS_DIR / "edge_debug.png"
        try:
            await client._page.screenshot(path=str(ss_path))
        except Exception as e:
            return {"error": str(e)}
        url = client._page.url
        texts = []
        try:
            for el in await client._page.query_selector_all(".model-response-text, .message-content, message-content, p"):
                t = (await el.inner_text()).strip()
                if t:
                    texts.append(t)
        except Exception:
            pass
        img_srcs = []
        for img in await client._page.query_selector_all('img'):
            s = await img.get_attribute('src')
            if s: img_srcs.append(s[:120])
        return {"url": url, "screenshot": str(ss_path), "texts": texts[-5:], "img_srcs": img_srcs}
    return {"error": "Chưa có trang trình duyệt"}


@app.get("/open-browser", response_class=HTMLResponse, tags=["Trình duyệt"])
async def open_browser(target: str = "all"):
    """Mở hoặc đưa cửa sổ Microsoft Edge kết nối Gemini Web, Google Flow và Google Vids lên màn hình."""
    from app.clients.factory import get_gemini_client
    browser_adapter = get_gemini_client("browser")
    await browser_adapter._ensure_browser()
    context = browser_adapter._context

    if context:
        target_clean = target.lower().strip()
        if target_clean == "flow":
            flow_page = None
            for p in context.pages:
                if "flow.google.com" in p.url:
                    flow_page = p
                    break
            if not flow_page:
                flow_page = await context.new_page()
                await flow_page.goto("https://flow.google.com", wait_until="domcontentloaded")
            await flow_page.bring_to_front()
        elif target_clean == "vids":
            vids_page = None
            for p in context.pages:
                if "docs.google.com/videos" in p.url or "vids" in p.url:
                    vids_page = p
                    break
            if not vids_page:
                vids_page = await context.new_page()
                await vids_page.goto("https://vids.new", wait_until="domcontentloaded")
            await vids_page.bring_to_front()
        elif target_clean == "gemini":
            gemini_page = None
            for p in context.pages:
                if "gemini.google.com" in p.url:
                    gemini_page = p
                    break
            if not gemini_page:
                gemini_page = await context.new_page()
                await gemini_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            await gemini_page.bring_to_front()
        else:
            # target == "all"
            targets_to_ensure = [
                ("https://gemini.google.com/app", "gemini.google.com"),
                ("https://flow.google.com", "flow.google.com"),
                ("https://vids.new", "docs.google.com/videos")
            ]
            for url, domain in targets_to_ensure:
                exists = any(domain in p.url for p in context.pages)
                if not exists:
                    try:
                        np = await context.new_page()
                        await np.goto(url, wait_until="domcontentloaded")
                    except Exception:
                        pass
            if context.pages:
                await context.pages[0].bring_to_front()

    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Trình Duyệt Google Cá Nhân Đã Sẵn Sàng</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #fff; text-align: center; padding: 50px 20px; }
            .card { max-width: 620px; margin: 0 auto; background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 32px; box-shadow: 0 15px 35px rgba(0,0,0,0.4); }
            h2 { color: #10b981; margin-bottom: 12px; font-size: 22px; }
            p { color: #94a3b8; font-size: 15px; line-height: 1.6; margin-bottom: 24px; }
            .btn-links { display: flex; flex-direction: column; gap: 10px; margin-bottom: 25px; }
            .link-btn { display: block; padding: 12px 18px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; color: #fff; transition: opacity 0.2s; }
            .link-btn:hover { opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>✓ Cửa Sổ Trình Duyệt Cá Nhân Đang Mở!</h2>
            <p>Cửa sổ Microsoft Edge thật đang hiển thị trên màn hình với hồ sơ người dùng cá nhân của bạn.<br>Nếu tài khoản cần đăng nhập, bạn chỉ cần đăng nhập Google 1 lần, hệ thống sẽ tự động lưu lại và tiếp tục xử lý mọi tác vụ tạo ảnh & video!</p>
            <div class="btn-links">
                <a href="/open-browser?target=gemini" class="link-btn" style="background: #0284c7;">🎨 Chuyển sang tab Gemini Web (Tạo ảnh Imagen 3)</a>
                <a href="/open-browser?target=flow" class="link-btn" style="background: #9333ea;">🎬 Chuyển sang tab Google Flow (Tạo video AI Veo)</a>
                <a href="/open-browser?target=vids" class="link-btn" style="background: #2563eb;">📹 Chuyển sang tab Google Vids (Video Trình chiếu)</a>
            </div>
            <a href="/" style="color: #38bdf8; text-decoration: none; font-size: 14px; font-weight: 600;">← Quay lại Trang Chủ GeminiBridge</a>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=getattr(settings, "HOST", "127.0.0.1"), port=getattr(settings, "PORT", 8200), reload=getattr(settings, "DEBUG", False))
