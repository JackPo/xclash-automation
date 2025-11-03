@echo off
REM XClash Phase 1: Interactive Calibration
REM Exploration and discovery tool
echo ========================================
echo XCLASH PHASE 1: INTERACTIVE CALIBRATION
echo ========================================
echo.
echo This tool helps discover game mechanics:
echo - World map view detection
echo - Zoom controls and levels
echo - Map navigation boundaries
echo - UI element locations
echo.
echo All findings will be logged to:
echo calibration_findings/
echo.
pause

"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0calibrate_interactive.py"
pause
