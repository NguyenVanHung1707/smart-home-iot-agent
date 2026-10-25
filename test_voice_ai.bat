@echo off
chcp 65001 >nul
title Homing Smart Home - ESP32 AI Voice Testing Suite
echo =======================================================
echo   HOMING SMART HOME - BỘ CÔNG CỤ TEST VOICE AI
echo   (Sử dụng Loa máy tính và Mic máy tính kiểm tra ESP32)
echo =======================================================
echo.

python scripts/test_voice_ai.py %*

echo.
pause
