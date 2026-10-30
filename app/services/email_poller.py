import imaplib
import email
from email.header import decode_header
import re
import asyncio
import logging
from typing import Optional, Dict, Any, List
from app.config import settings
from app.models.payment_db import PaymentDB
from app.routes.payment import grant_player_reward

logger = logging.getLogger("email_poller")

# Lưu danh sách UID các email đã xử lý để không bao giờ cộng tiền 2 lần
PROCESSED_EMAIL_UIDS = set()


def decode_str(header_str: str) -> str:
    """Giải mã tiêu đề email tiếng Việt có dấu."""
    if not header_str:
        return ""
    decoded_fragments = decode_header(header_str)
    result = ""
    for frag, encoding in decoded_fragments:
        if isinstance(frag, bytes):
            result += frag.decode(encoding or "utf-8", errors="ignore")
        else:
            result += str(frag)
    return result


def extract_email_body(msg: email.message.Message) -> str:
    """Lấy nội dung văn bản từ email (cả plain text và html)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore") + "\n"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="ignore")
    return body


def parse_bank_transaction(subject: str, body: str) -> Optional[Dict[str, Any]]:
    """
    Tự động phân tích nội dung email từ Techcombank, MoMo, MBBank, v.v.
    Bóc tách: Số tiền nhận được và Nội dung chuyển khoản.
    """
    raw_source = f"{subject}\n{body}"
    # Loại bỏ triệt để thẻ style, script của email HTML
    no_style = re.sub(r'<style[^>]*>.*?</style>', ' ', raw_source, flags=re.DOTALL | re.IGNORECASE)
    no_script = re.sub(r'<script[^>]*>.*?</script>', ' ', no_style, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', no_script)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    # 1. Tìm số tiền nạp: +50,000 VND hoặc 50.000 VND hoặc 50000 d
    # Thường Techcombank/MoMo ghi: "Số tiền: +50,000 VND" hoặc "PS: +50,000 VND"
    amount = 0
    amount_matches = re.findall(r'(?:\+|\b)(\d{1,3}(?:[.,]\d{3})+|\d{4,9})\s*(?:VND|VNĐ|đ|d\b)', clean_text, re.IGNORECASE)
    if amount_matches:
        raw_val = amount_matches[0].replace('.', '').replace(',', '').strip()
        try:
            amount = int(raw_val)
        except Exception:
            pass

    # Nếu không thấy định dạng có chữ VND, tìm sau các từ khóa "Số tiền" / "Giao dịch"
    if amount <= 0:
        keyword_match = re.search(r'(?:Số tiền|Giao dịch|Số tiền GD|So tien)[\s:]*([+\d,.]+)', clean_text, re.IGNORECASE)
        if keyword_match:
            raw_val = re.sub(r'[^\d]', '', keyword_match.group(1))
            try:
                amount = int(raw_val)
            except Exception:
                pass

    if amount <= 0:
        return None

    # 2. Tìm nội dung chuyển khoản (Ví dụ: NAP1234, NAP 5678, MUA ACC10)
    # Lấy từ khóa "Nội dung" / "Lời nhắn" / "Chi tiết" hoặc quét trực tiếp tiền tố NAP
    content = ""
    content_match = re.search(r'(?:Nội dung|Noi dung|Lời nhắn|Loi nhan|Mo ta|ND)[\s:]*([^\n\r<]{3,80})', clean_text, re.IGNORECASE)
    if content_match:
        content = content_match.group(1).strip()
    else:
        # Quét trực tiếp xem có chữ NAP... trong toàn văn bản không
        nap_match = re.search(r'\b(NAP\s*\d{3,8})\b', clean_text, re.IGNORECASE)
        if nap_match:
            content = nap_match.group(1).strip()

    return {
        "amount": amount,
        "content": content or clean_text[:100],
        "subject": subject
    }


def scan_gmail_inbox() -> List[Dict[str, Any]]:
    """
    Kết nối vào Gmail qua giao thức IMAP an toàn, quét các email biến động số dư mới nhất.
    """
    gmail_user = settings.GMAIL_EMAIL
    gmail_pass = settings.GMAIL_APP_PASSWORD

    if not gmail_user or not gmail_pass:
        return []

    processed_transactions = []

    try:
        # Kết nối tới máy chủ IMAP của Google
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_user, gmail_pass)
        mail.select("INBOX")

        # Lấy danh sách các email gần đây nhất (an toàn không lỗi ký tự)
        status, messages = mail.search(None, "ALL")

        if status != "OK" or not messages[0]:
            mail.close()
            mail.logout()
            return []

        email_ids = messages[0].split()
        # Chỉ quét tối đa 15 email gần đây nhất để đạt tốc độ cao nhất
        recent_ids = email_ids[-15:]

        for e_id in reversed(recent_ids):
            e_id_str = e_id.decode()
            if e_id_str in PROCESSED_EMAIL_UIDS:
                continue

            status, data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = decode_str(msg.get("Subject", ""))
            sender = decode_str(msg.get("From", ""))
            body = extract_email_body(msg)

            # Phân tích xem có phải email nạp tiền không
            parsed = parse_bank_transaction(subject=subject, body=body)
            if parsed and parsed["amount"] > 0:
                PROCESSED_EMAIL_UIDS.add(e_id_str)
                parsed["id"] = e_id_str
                parsed["sender"] = sender
                processed_transactions.append(parsed)

                # Ghi log giao dịch vào cơ sở dữ liệu
                PaymentDB.record_transaction(
                    amount=parsed["amount"],
                    content=parsed["content"],
                    transaction_id=f"GMAIL_{e_id_str}",
                    bank_account=settings.VIETQR_ACCOUNT_NO,
                    gateway="GMAIL_AUTO_BOT",
                    raw_data={"subject": subject, "sender": sender}
                )

                # Tìm và cộng đồ cho đơn hàng trong game ngay lập tức!
                matched_order = PaymentDB.find_pending_order_by_content(
                    content=parsed["content"],
                    amount=parsed["amount"]
                )
                if matched_order:
                    PaymentDB.mark_order_paid(matched_order["order_id"])
                    grant_player_reward(
                        order=matched_order,
                        transaction={"amount": parsed["amount"], "content": parsed["content"], "trans_id": f"GMAIL_{e_id_str}"}
                    )
                    logger.info(f"🎉 [GMAIL BOT 24/7] ĐÃ TỰ ĐỘNG CỘNG ĐỒ CHO ĐƠN: {matched_order['order_id']}")

        mail.close()
        mail.logout()
    except Exception as e:
        logger.error(f"[GMAIL BOT] Lỗi kết nối Gmail: {e}")

    return processed_transactions


async def run_email_poller_background():
    """Vòng lặp chạy ngầm 24/7 trên Cloud/VPS, quét email định kỳ."""
    await asyncio.sleep(5)  # Chờ server khởi động ổn định
    logger.info(" [*] BOT DOC GMAIL BIEN DONG SO DU 24/7 DA KHOI CHAY!")
    
    while True:
        try:
            if settings.ENABLE_EMAIL_AUTO_BANK and settings.GMAIL_EMAIL and settings.GMAIL_APP_PASSWORD:
                scan_gmail_inbox()
        except Exception as e:
            logger.error(f"[GMAIL LOOP ERROR]: {e}")
        
        # Quét lặp lại mỗi 10 giây
        await asyncio.sleep(settings.EMAIL_CHECK_INTERVAL)

