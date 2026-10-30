@echo off
cd /d "%~dp0"

echo ======================================================================
echo             KIEM TRA HE THONG GEMINIBRIDGE (AUTOMATED TESTS)
echo ======================================================================
echo.

if not exist "venv" (
    echo [LOI] Chua co moi truong ao venv.
    echo Vui long chay setup.bat truoc.
    pause
    exit /b 1
)

call .\venv\Scripts\activate.bat

echo Dang chay bo kiem tra tu dong voi pytest...
echo.
python -m pytest -v tests/
if errorlevel 1 goto :failed

echo.
echo ======================================================================
echo  [THANH CONG] TOAN BO 24/24 BAI KIEM TRA DEU DAT CHUAN HOAN HAO
echo ======================================================================
goto :end

:failed
echo.
echo ======================================================================
echo  [CANH BAO] Co bai kiem tra chua dat. Vui long xem thong bao tren.
echo ======================================================================

:end
echo.
pause
