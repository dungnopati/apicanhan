@echo off
cd /d "%~dp0"
echo ======================================================================
echo          MO CUA SO TRINH DUYET GOOGLE CA NHAN (EDGE)
echo ======================================================================
echo Dang mo Microsoft Edge voi ho so ca nhan...
echo Co san cac tab: Gemini Web, Google Flow, Google Vids.
echo Port dieu khien tu dong hoa: 9222
echo ======================================================================
echo.

start "" msedge.exe --remote-debugging-port=9222 --user-data-dir="%~dp0browser_profile" --start-maximized "https://gemini.google.com/app" "https://flow.google.com" "https://vids.new"

echo Cua so trinh duyet Edge da duoc mo tren man hinh!
timeout /t 3 >nul
exit /b 0
