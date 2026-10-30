import asyncio

# Khóa đồng bộ đơn luồng trình duyệt (Lock) đảm bảo gửi tuần tự từng phân cảnh 1
browser_lock = asyncio.Lock()
