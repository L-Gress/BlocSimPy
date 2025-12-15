"""
OPTIMIZED Build script for BlocSimPy.

Usage:
    python build_exe_fast.py --target [client|server|all] --platform [current|debug]
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

def check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            return True
        except:
            return False

def clean_build_artifacts():
    print("Cleaning artifacts...")
    for artifact in ["build", "dist", "__pycache__"]:
        if os.path.exists(artifact):
            try:
                if os.path.isdir(artifact): shutil.rmtree(artifact)
                else: os.remove(artifact)
            except: pass
    for spec in Path(".").glob("*.spec"):
        try: spec.unlink()
        except: pass

def build_client(platform_mode="current"):
    print(f"\nBuilding CLIENT (Platform: {platform_mode})...")
    
    # Base args
    args = [
        "pyinstaller",
        "--name=BlocSimPy",
        "--onefile",
        "--noconfirm",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=matplotlib.backends.backend_qt5agg",
        "--add-data=config;config",
        "--add-data=user_library;user_library",
        "--add-data=logo.png;.",
        "--icon=logo.png",
        "--exclude-module=torch",
        "--exclude-module=tensorflow",
        "--exclude-module=cv2",
        "--exclude-module=pandas",
        "--exclude-module=tkinter",
        "--exclude-module=notebook",
        "--exclude-module=pytest",
        "main.py"
    ]
    
    if platform_mode != "debug":
        args.insert(3, "--windowed") # GUI mode
    else:
        print("  -> Debug mode: Console enabled")

    subprocess.check_call(args)

def build_server(platform_mode="current"):
    print(f"\nBuilding SERVER (Platform: {platform_mode})...")
    
    # Server needs access to engine and minimal libs
    args = [
        "pyinstaller",
        "--name=BlocSimServer",
        "--onefile",
        "--noconfirm",
        "--console", # Server always console
        # Server needs block definitions
        "--hidden-import=engine",
        "--hidden-import=engine.blocks",
        # Add basic blocks explicitly if needed, but engine.blocks.__init__ should cover it
        
        # Data? Server might need config
        "--add-data=config;config",
        
        "--exclude-module=PySide6", # Server doesn't need GUI
        "--exclude-module=matplotlib",
        "--exclude-module=cv2",
        "--exclude-module=pandas",
        
        "server/main.py"
    ]
    
    subprocess.check_call(args)

def main():
    parser = argparse.ArgumentParser(description="BlocSimPy Builder")
    parser.add_argument("--target", choices=["client", "server", "all"], default="all", help="Build target")
    parser.add_argument("--platform", default="current", help="Platform mode (use 'debug' for console output)")
    
    args = parser.parse_args()
    
    if not check_pyinstaller():
        return 1
        
    clean_build_artifacts()
    
    try:
        if args.target in ["client", "all"]:
            build_client(args.platform)
            
        if args.target in ["server", "all"]:
            build_server(args.platform)
            
        print("\n\u2713 Build process completed.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n\u2717 Build failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
