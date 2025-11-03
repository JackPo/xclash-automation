@echo off
echo ========================================
echo XClash Zoom Discovery
echo ========================================
echo.
echo This will:
echo - Find BlueStacks window
echo - Click it to focus
echo - Press Shift+Z 40 times (zoom out)
echo - Press Shift+A 20 times (zoom in)
echo - Take screenshots at each step
echo.
echo Make sure BlueStacks is running!
echo.
pause

"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0discover_zoom_v2.py"

echo.
echo ========================================
echo COMPLETE!
echo ========================================
pause
