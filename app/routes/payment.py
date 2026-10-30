import base64
import secrets
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.config import settings
from app.models.payment_db import PaymentDB

logger = logging.getLogger("payment")
payment_router = APIRouter(tags=["Cổng Thanh Toán & Nạp Game 24/7"])

# Lưu trữ token hợp lệ tạm thời trong bộ nhớ
ACTIVE_VQR_TOKENS = set()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


# ==================== PYDANTIC MODELS ====================

class CreateOrderRequest(BaseModel):
    player_id: str = Field(..., description="ID hoặc Tên nhân vật của người chơi trong game / khách mua hàng")
    amount: int = Field(..., gt=0, description="Số tiền cần nạp (VND), ví dụ: 20000, 50000, 100000")
    game_id: Optional[str] = Field("DEFAULT_GAME", description="Mã phân loại game hoặc shop (ví dụ: ROBLOX, MINECRAFT, SHOP_ACC)")
    product_name: Optional[str] = Field("Nạp số dư game", description="Tên gói nạp hoặc tên vật phẩm")
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dữ liệu tùy chọn (vật phẩm, gói VIP, số lượng vàng...)")


class MockDepositRequest(BaseModel):
    order_id: str = Field(..., description="Mã đơn hàng cần giả lập nạp tiền")
    amount: Optional[int] = Field(None, description="Số tiền giả lập (mặc định lấy đúng số tiền của đơn)")


# ==================== HÀM TIỆN ÍCH CỘNG ĐỒ CHO GAME ====================

def grant_player_reward(order: Dict[str, Any], transaction: Dict[str, Any]):
    """
    Hàm tự động kích hoạt khi tiền về tài khoản ngân hàng thành công!
    Người anh em có thể tùy biến logic cộng vàng / trao vật phẩm ở đây:
    - Gửi request đến server Roblox / Minecraft / Web Game
    - Cập nhật database MySQL / SQLite của Game
    - Gửi tin nhắn Bot Discord / Telegram thông báo
    """
    player_id = order["player_id"]
    game_id = order["game_id"]
    amount = order["amount"]
    metadata = order.get("metadata", {})

    logger.info(f" [VẬT PHẨM GAME] ĐANG CỘNG ĐỒ: Người chơi={player_id} | Game={game_id} | Tiền={amount:,} VND | Chi tiết={metadata}")
    print(f"\n==================================================")
    print(f" [XÁC NHẬN TIỀN VỀ 24/7] NẠP THÀNH CÔNG!")
    print(f" -> Game: {game_id}")
    print(f" -> Tài khoản người chơi: {player_id}")
    print(f" -> Số tiền thực nhận: {amount:,} VND")
    print(f" -> Nội dung chuyển: {transaction.get('content')}")
    print(f" -> Đã kích hoạt trả vật phẩm tự động cho người chơi.")
    print(f"==================================================\n")


# ==================== CHUẨN VIETQR (TINGO PAY) ====================

@payment_router.post("/vqr/api/token_generate", summary="VietQR - Lấy Token xác thực (Basic Auth)")
@payment_router.post("/api/token_generate", summary="VietQR - Lấy Token xác thực")
async def vqr_token_generate(authorization: Optional[str] = Header(None)):
    """
    Endpoint chuẩn VietQR yêu cầu để kích hoạt nút 'Test Get Token'.
    Sử dụng HTTP Basic Authentication (Username & Password do bạn cài đặt).
    """
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu xác thực Basic Authentication (Thiếu Authorization header)"
        )

    try:
        encoded_creds = authorization.split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
        username, password = decoded_creds.split(":", 1)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng Basic Auth không hợp lệ"
        )

    # Kiểm tra Username và Password khớp với cấu hình
    expected_user = settings.VIETQR_USERNAME
    expected_pass = settings.VIETQR_PASSWORD

    if username != expected_user or password != expected_pass:
        logger.warning(f"VietQR Token Generate thất bại: Sai username/password ({username})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai Username hoặc Password hệ thống!"
        )

    # Sinh Bearer Token ngẫu nhiên cấp cho VietQR
    token = secrets.token_hex(24)
    ACTIVE_VQR_TOKENS.add(token)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "merchant": settings.VIETQR_MERCHANT_NAME,
        "status": "success"
    }


@payment_router.post("/vqr/bank/api/test/transaction-callback", summary="VietQR - Nhận Webhook Biến Động Số Dư")
@payment_router.post("/bank/api/test/transaction-callback", summary="VietQR - Callback Alias")
@payment_router.post("/api/payment/webhook", summary="Webhook Nhận Biến Động Số Dư")
async def transaction_callback(request: Request):
    """
    Nhận thông báo khi khách hàng chuyển tiền thành công qua VietQR / Ngân hàng / MoMo.
    Hệ thống tự động lọc mã đơn, kiểm tra đúng số tiền và cộng đồ cho game.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    logger.info(f"Nhận Callback thanh toán: {payload}")

    # Chuẩn hóa dữ liệu nhận được (hỗ trợ cả chuẩn trực tiếp và lồng trong object data)
    data = payload.get("data", payload)

    # Tìm số tiền nhận được
    amount = 0
    for key in ["amount", "soTien", "money", "transferAmount"]:
        if key in data and data[key] is not None:
            try:
                amount = int(float(str(data[key]).replace(",", "")))
                break
            except Exception:
                pass

    # Tìm nội dung chuyển khoản
    content = ""
    for key in ["content", "description", "noiDung", "msg", "addInfo", "remark"]:
        if key in data and data[key]:
            content = str(data[key]).strip()
            break

    trans_id = str(data.get("transactionId") or data.get("id") or data.get("transId") or "")
    bank_acc = str(data.get("bankAccount") or data.get("accountNo") or settings.VIETQR_ACCOUNT_NO)
    gateway = str(data.get("gateway") or data.get("bankName") or settings.VIETQR_BANK_ID)

    # Ghi nhận giao dịch vào lịch sử DB
    PaymentDB.record_transaction(
        amount=amount,
        content=content,
        transaction_id=trans_id,
        bank_account=bank_acc,
        gateway=gateway,
        raw_data=payload
    )

    # Tìm kiếm đơn hàng PENDING khớp với nội dung chuyển khoản
    matched_order = PaymentDB.find_pending_order_by_content(content=content, amount=amount)

    if matched_order:
        order_id = matched_order["order_id"]
        # Đánh dấu đơn hàng thành công
        PaymentDB.mark_order_paid(order_id)
        # Thực hiện cộng tiền / trao vật phẩm game ngay lập tức!
        grant_player_reward(order=matched_order, transaction={"amount": amount, "content": content, "trans_id": trans_id})
        return {
            "status": "success",
            "message": f"Nạp tiền thành công cho đơn {order_id}",
            "order_id": order_id,
            "player_id": matched_order["player_id"]
        }

    return {
        "status": "received",
        "message": "Đã ghi nhận giao dịch (Chưa khớp đơn hàng cụ thể)",
        "amount": amount,
        "content": content
    }


# ==================== UNIVERSAL PAYMENT API CHO GAME & SHOP ====================

@payment_router.post("/api/payment/create-order", summary="Tạo Đơn Nạp Tiền & Mã QR Tự Động")
async def create_payment_order(req: CreateOrderRequest):
    """
    Dành cho mọi Game hoặc Website: Gọi endpoint này để tạo mã QR nạp tiền.
    Trả về mã đơn, mã QR VietQR (chuyển tiền tự điền nội dung & số tiền).
    """
    import random
    import string

    # Sinh mã đơn ngắn gọn: ví dụ NAP9281
    rand_code = ''.join(random.choices(string.digits, k=4))
    order_id = f"{settings.PAYMENT_PREFIX}{rand_code}"
    
    # Kiểm tra tránh trùng lặp
    while PaymentDB.get_order(order_id):
        rand_code = ''.join(random.choices(string.digits, k=5))
        order_id = f"{settings.PAYMENT_PREFIX}{rand_code}"

    # Cú pháp chuyển tiền chính là mã đơn
    transfer_content = order_id

    # Tạo link mã QR VietQR nhanh (Chuẩn NAPAS 247):
    # Khách quét bằng MoMo hoặc bất kỳ App ngân hàng nào cũng tự điền đúng Số tài khoản, Số tiền và Lời nhắn!
    bank_id = settings.VIETQR_BANK_ID or "MB"
    account_no = settings.VIETQR_ACCOUNT_NO or "0000000000"
    account_name = settings.VIETQR_ACCOUNT_NAME or "CHU TAI KHOAN"

    qr_url = (
        f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png"
        f"?amount={req.amount}&addInfo={transfer_content}&accountName={account_name}"
    )

    # Lưu đơn vào cơ sở dữ liệu
    order = PaymentDB.create_order(
        order_id=order_id,
        player_id=req.player_id,
        amount=req.amount,
        description=transfer_content,
        qr_url=qr_url,
        game_id=req.game_id or "DEFAULT_GAME",
        extra_data=req.extra_data
    )

    return {
        "status": "success",
        "order_id": order_id,
        "amount": req.amount,
        "transfer_content": transfer_content,
        "qr_code_url": qr_url,
        "bank_info": {
            "bank_id": bank_id,
            "account_no": account_no,
            "account_name": account_name
        },
        "order": order
    }


@payment_router.get("/api/payment/order/{order_id}", summary="Kiểm Tra Trạng Thái Đơn Nạp")
async def check_order_status(order_id: str):
    """Game hoặc Web gọi API này liên tục (polling) để biết người chơi đã thanh toán hay chưa."""
    order = PaymentDB.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã đơn hàng này")
    return {
        "order_id": order["order_id"],
        "status": order["status"],  # PENDING hoặc SUCCESS
        "player_id": order["player_id"],
        "amount": order["amount"],
        "created_at": order["created_at"],
        "paid_at": order["paid_at"]
    }


@payment_router.get("/api/payment/orders", summary="Danh Sách Đơn Hàng Gần Đây")
async def list_orders():
    return {"orders": PaymentDB.list_orders(limit=50)}


@payment_router.get("/api/payment/transactions", summary="Lịch Sử Biến Động Nhận Tiền")
async def list_transactions():
    return {"transactions": PaymentDB.list_transactions(limit=50)}


@payment_router.post("/api/payment/mock-deposit", summary="[Test] Giả Lập Nạp Tiền Thành Công (Không Cần Tiền Thật)")
async def mock_deposit(req: MockDepositRequest):
    """Dành riêng cho lập trình viên test thử luồng cộng tiền vào game mà không cần nạp tiền thật!"""
    order = PaymentDB.get_order(req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng này")

    amount = req.amount or order["amount"]
    PaymentDB.mark_order_paid(order["order_id"])
    PaymentDB.record_transaction(
        amount=amount,
        content=order["description"],
        transaction_id="MOCK_TEST_123",
        order_id=order["order_id"],
        gateway="TEST_SYSTEM",
        raw_data={"is_mock": True}
    )
    grant_player_reward(order=order, transaction={"amount": amount, "content": order["description"], "trans_id": "MOCK"})

    return {
        "status": "success",
        "message": f"Giả lập nạp tiền thành công cho người chơi {order['player_id']}!",
        "order_id": order["order_id"]
    }


@payment_router.get("/payment-demo", response_class=HTMLResponse, summary="Giao Diện Demo Nạp Game")
async def payment_demo_page():
    template_file = TEMPLATE_DIR / "payment_demo.html"
    if template_file.exists():
        content = template_file.read_text(encoding="utf-8")
        return content.replace("{{ MERCHANT_NAME }}", settings.VIETQR_MERCHANT_NAME)
    return "<h1>Giao diện Demo chưa sẵn sàng</h1>"
