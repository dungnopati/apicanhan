@echo off
cd /d "%~dp0"

echo ======================================================================
echo           CHUONG TRINH THIET LAP TU DONG - GEMINIBRIDGE
echo ======================================================================
echo.

echo [1/4] Dang kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 goto :no_python
python --version
echo Python da san sang.
echo.

echo [2/4] Dang thiet lap moi truong ao (venv)...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 goto :venv_fail
    echo Da tao thanh cong thu muc venv.
) else (
    echo Moi truong ao venv da co san.
)
echo.

echo [3/4] Dang cai dat cac thu vien can thiet...
call .\venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 goto :pip_fail
echo Cac thu vien da duoc cai dat hoan tat.
echo.

echo [4/4] Khoi tao file cau hinh .env...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Da tao file .env tu file mau .env.example.
    echo.
    echo ******************************************************************
    echo BUOC TIEP THEO RAT QUAN TRONG:
    echo 1. Mo file .env bang Notepad (hoac trinh soan thao bat ky).
    echo 2. Dien Gemini API Key cua ban vao muc GEMINI_API_KEY.
    echo    (Lay key mien phi tai: https://aistudio.google.com/app/apikey)
    echo 3. Luu file lai va nhap dup vao start.bat de khoi dong may chu.
    echo ******************************************************************
) else (
    echo File .env da co san. San sang hoat dong.
)

echo.
echo ======================================================================
echo                 CAI DAT HOAN TAT THANH CONG!
echo ======================================================================
echo.
pause
exit /b 0

:no_python
echo [LOI] Khong tim thay Python tren may tinh cua ban!
echo Vui long cai dat Python tu https://www.python.org/
echo (Nho tich chon: Add python.exe to PATH trong qua trinh cai)
pause
exit /b 1

:venv_fail
echo [LOI] Khong the tao thu muc moi truong ao venv.
pause
exit /b 1

:pip_fail
echo [LOI] Xay ra loi khi cai dat thu vien tu requirements.txt.
pause
exit /b 1
