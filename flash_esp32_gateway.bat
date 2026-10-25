@echo off
chcp 65001 >nul
title Nạp Firmware ESP32 Gateway (Xiaozhi AI)
echo ========================================================
echo   HOMING - NẠP FIRMWARE ESP32 GATEWAY AI (COM3)
echo ========================================================
echo.
echo [1] Đảm bảo mạch ESP32 đang cắm vào cổng USB (COM3).
echo [2] Khi màn hình hiện "Connecting.....", nếu mạch không tự
echo     chuyển chế độ nạp, bạn hãy NHẤN GIỮ NÚT BOOT (IO0) 1-2 giây.
echo.
pause

echo.
echo [1/2] Đang kiểm tra / biên dịch firmware sang build_gw...
arduino-cli compile --fqbn esp32:esp32:esp32:UploadSpeed=115200,PartitionScheme=huge_app,FlashMode=dio --output-dir build_gw src/firmware/esp32_xiaozhi_gateway

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ [LỖI]: Biên dịch firmware thất bại! Vui lòng kiểm tra lại mã nguồn.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Đang nạp firmware vào ESP32 (COM3, tốc độ ổn định 115200)...
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32:UploadSpeed=115200,PartitionScheme=huge_app,FlashMode=dio --input-dir build_gw

if %ERRORLEVEL% EQU 0 (
    echo.
    echo 🎉 NẠP FIRMWARE THÀNH CÔNG 100%!
    echo ESP32 Gateway đã sẵn sàng nhận diện giọng nói Tiếng Việt.
) else (
    echo.
    echo ⚠️ Nạp chưa thành công. Bạn hãy rút cáp USB cắm lại hoặc nhấn giữ nút BOOT khi chạy lại script nhé.
)

echo.
pause
