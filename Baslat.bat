@echo off
echo Mevzuat Takip Sistemi Baslatiliyor...

start "Mevzuat Backend" cmd /k "cd /d C:\Users\gulte\mevzuat-takip-sistemi && python main.py"
timeout /t 3 >nul
start "Mevzuat UI" cmd /k "cd /d C:\Users\gulte\mevzuat-takip-sistemi\mevzuat_ui && flutter run -d windows"

exit