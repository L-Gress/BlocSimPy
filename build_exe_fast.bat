@echo off
REM OPTIMIZED Build script for BlocSimPy executable
REM This version is much faster!

echo ========================================
echo BlocSimPy - FAST Executable Build
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

echo Running OPTIMIZED build script...
echo This should be much faster than the regular build!
echo.

REM Run the optimized build script
python build_exe_fast.py

echo.
echo ========================================
echo Build process completed
echo ========================================
echo.
pause
