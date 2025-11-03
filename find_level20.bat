@echo off
REM XClash Level 20 Castle Finder
REM Usage: find_level20.bat scan001

if "%~1"=="" (
    echo Usage: find_level20.bat RUN_ID
    echo Example: find_level20.bat scan001
    exit /b 1
)

"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0find_level20.py" --run-id %*
pause
