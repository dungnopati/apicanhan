@echo off
cd /d "%~dp0"

echo ======================================================================
echo                   KHOI DONG MAY CHU GEMINIBRIDGE
echo ======================================================================
echo.

if not exist "venv" goto :no_venv

if not exist ".env" (
    echo [THONG BAO] Chua co file .env. Dang tao tu file mau .env.example...
    copy ".env.example" ".env" >nul
)

call .\venv\Scripts\activate.bat

echo Dang khoi dong may chu tai dia chi http://127.0.0.1:8200 ...
echo (Giao dien dieu khien web se tu dong mo tren trinh duyet trong vai giay)
echo.
echo ======================================================================
echo  HUONG DAN:
echo  - Giao dien dieu khien: http://127.0.0.1:8200
echo  - Swagger UI thu API truc quan: http://127.0.0.1:8200/docs
echo  - File mo rieng trinh duyet Edge ca nhan de dang nhap: mo_trinh_duyet.bat
echo  - Nhan to hop phim Ctrl + C tai day khi ban muon tat may chu.
echo ======================================================================
echo.

rem Tu dong giai phong cong 8200 neu co tien trinh cu dang chay ngam
powershell -Command "Get-NetTCPConnection -LocalPort 8200 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

rem Tu dong mo giao dien dashboard tren trinh duyet
start "" "http://127.0.0.1:8200"

python -m app.main
pause
exit /b 0

:no_venv
echo [LOI] Chua tim thay thu muc moi truong ao venv!
echo Vui long nhap dup vao file setup.bat truoc de he thong tu cai dat.
pause
exit /b 1
