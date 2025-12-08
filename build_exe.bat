@echo off
REM Build script for BlocSimPy executable
REM This batch file runs the Python build script

echo ========================================
echo BlocSimPy - Executable Build
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

echo Running build script...
echo.

REM Run the build script
python build_exe.py

echo.
echo ========================================
echo Build process completed
echo ========================================
echo.
pause
