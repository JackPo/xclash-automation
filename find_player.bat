@echo off
REM XClash Player Finder - Convenience launcher
REM Usage: find_player.bat PlayerName

if "%~1"=="" (
    echo Usage: find_player.bat PlayerName
    echo Example: find_player.bat Angelbear666
    exit /b 1
)

"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0find_player.py" %*
