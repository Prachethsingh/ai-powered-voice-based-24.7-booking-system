@echo off
REM Stop all ai powered voice based 24.7 booking system services on Windows

echo Stopping ai powered voice based 24.7 booking system services...

REM Kill PowerShell windows running our services
taskkill /fi "WindowTitle eq Python-AI*" /t 2>nul
taskkill /fi "WindowTitle eq Node-Server*" /t 2>nul  
taskkill /fi "WindowTitle eq React-Dev*" /t 2>nul

echo.
echo Services stopped.