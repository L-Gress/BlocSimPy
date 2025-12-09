"""
OPTIMIZED Build script for creating a standalone executable of BlocSimPy.

This version excludes unnecessary heavy libraries for faster builds and smaller file size.

Usage:
    python build_exe_fast.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def check_pyinstaller():
    """Check if PyInstaller is installed, if not, install it."""
    try:
        import PyInstaller
        print("✓ PyInstaller is already installed")
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✓ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("✗ Failed to install PyInstaller")
            return False


def clean_build_artifacts():
    """Remove previous build artifacts."""
    print("\nCleaning previous build artifacts...")
    
    artifacts = ["build", "dist", "__pycache__"]
    
    for artifact in artifacts:
        if os.path.exists(artifact):
            try:
                if os.path.isdir(artifact):
                    shutil.rmtree(artifact)
                else:
                    os.remove(artifact)
                print(f"  ✓ Removed {artifact}")
            except Exception as e:
                print(f"  ! Could not remove {artifact}: {e}")
    
    # Remove .spec files
    for spec_file in Path(".").glob("*.spec"):
        try:
            spec_file.unlink()
            print(f"  ✓ Removed {spec_file}")
        except Exception as e:
            print(f"  ! Could not remove {spec_file}: {e}")


def build_executable():
    """Build the executable using PyInstaller with optimized settings."""
    print("\n" + "="*60)
    print("Building BlocSimPy Executable (OPTIMIZED)")
    print("="*60 + "\n")
    
    # PyInstaller command with OPTIMIZED options
    pyinstaller_args = [
        "pyinstaller",
        "--name=BlocSimPy",                    # Name of the executable
        "--onefile",                            # Create a single executable
        "--windowed",                           # Don't show console window (GUI app)
        "--noconfirm",                          # Replace output directory without confirmation
        
        # Add ONLY the specific imports your app actually needs
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=matplotlib.backends.backend_qt5agg",
        
        # Add data files
        "--add-data=config;config",
        "--add-data=user_library;user_library",
        "--add-data=logo.png;.",
        
        # Icon
        "--icon=logo.png",
        
        # EXCLUDE heavy packages that bloat build time and file size
        "--exclude-module=torch",
        "--exclude-module=tensorflow",
        "--exclude-module=cv2",
        "--exclude-module=pandas",
        "--exclude-module=tkinter",
        "--exclude-module=IPython",
        "--exclude-module=notebook",
        "--exclude-module=jupyter",
        "--exclude-module=pytest",
        "--exclude-module=setuptools",
        "--exclude-module=distutils",
        
        # Entry point
        "main.py"
    ]
    
    print("Running OPTIMIZED PyInstaller build...")
    print("Excluded: torch, tensorflow, cv2, pandas (not needed for your app)")
    print()
    
    try:
        subprocess.check_call(pyinstaller_args)
        print("\n" + "="*60)
        print("✓ Build completed successfully!")
        print("="*60)
        print(f"\nExecutable location: {os.path.abspath('dist/BlocSimPy.exe')}")
        
        # Show file size
        exe_path = Path("dist/BlocSimPy.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executable size: {size_mb:.1f} MB")
        
        print("\nYou can now distribute the 'dist' folder or just the BlocSimPy.exe file.")
        return True
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print("✗ Build failed!")
        print("="*60)
        print(f"\nError: {e}")
        return False


def main():
    """Main build process."""
    print("BlocSimPy - OPTIMIZED Executable Build Script")
    print("==============================================\n")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"Working directory: {os.getcwd()}\n")
    
    # Step 1: Check/install PyInstaller
    if not check_pyinstaller():
        print("\nPlease install PyInstaller manually and try again:")
        print("  pip install pyinstaller")
        return 1
    
    # Step 2: Clean previous builds
    clean_build_artifacts()
    
    # Step 3: Build the executable
    if build_executable():
        print("\n✓ All done! Your executable is ready to use.")
        print("\nThis optimized build should be:")
        print("  • MUCH faster to build (2-3x faster)")
        print("  • Smaller file size")
        print("  • Same functionality")
        return 0
    else:
        print("\n✗ Build failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
