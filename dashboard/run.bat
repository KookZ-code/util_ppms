@echo off
echo ========================================
echo  Machine Utilization Dashboard
echo ========================================
echo.
cd /d "%~dp0"

if "%1"=="--prod" (
    echo Starting in PRODUCTION mode...
    python app.py --prod
) else (
    echo Starting in DEVELOPMENT mode...
    echo Open http://localhost:8050 in your browser
    echo.
    python app.py
)
pause
