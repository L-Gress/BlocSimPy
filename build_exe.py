"""
Build script for creating a standalone executable of BlocSimPy.

This script uses PyInstaller to package the application into a single executable.
It handles all dependencies including PySide6, matplotlib, and other libraries.

Usage:
    python build_exe.py
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
    """Build the executable using PyInstaller."""
    print("\n" + "="*60)
    print("Building BlocSimPy Executable")
    print("="*60 + "\n")
    
    # PyInstaller command with all necessary options
    pyinstaller_args = [
        "pyinstaller",
        "--name=BlocSimPy",                    # Name of the executable
        "--onefile",                            # Create a single executable
        "--windowed",                           # Don't show console window (GUI app)
        "--noconfirm",                          # Replace output directory without confirmation
        
        # Add hidden imports for packages that might not be detected automatically
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=matplotlib",
        "--hidden-import=matplotlib.backends.backend_qt5agg",
        "--hidden-import=numpy",
        "--hidden-import=scipy",
        "--hidden-import=scipy.signal",
        
        # Collect all submodules from your packages
        "--collect-all=PySide6",
        "--collect-all=matplotlib",
        
        # Add data files (if you have any configuration files, icons, etc.)
        "--add-data=config;config",
        "--add-data=user_library;user_library",
        
        # Exclude unnecessary packages to reduce size
        "--exclude-module=tkinter",
        "--exclude-module=IPython",
        "--exclude-module=notebook",
        
        # Entry point
        "main.py"
    ]
    
    print("Running PyInstaller with the following command:")
    print(" ".join(pyinstaller_args))
    print()
    
    try:
        subprocess.check_call(pyinstaller_args)
        print("\n" + "="*60)
        print("✓ Build completed successfully!")
        print("="*60)
        print(f"\nExecutable location: {os.path.abspath('dist/BlocSimPy.exe')}")
        print("\nYou can now distribute the 'dist' folder or just the BlocSimPy.exe file.")
        return True
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print("✗ Build failed!")
        print("="*60)
        print(f"\nError: {e}")
        return False


def create_spec_file():
    """Create a custom .spec file for more control (alternative approach)."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('user_library', 'user_library'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'matplotlib',
        'matplotlib.backends.backend_qt5agg',
        'numpy',
        'scipy',
        'scipy.signal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BlocSimPy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    
    with open("BlocSimPy.spec", "w") as f:
        f.write(spec_content)
    
    print("✓ Created BlocSimPy.spec file")
    print("  You can customize this file and build using: pyinstaller BlocSimPy.spec")


def main():
    """Main build process."""
    print("BlocSimPy - Executable Build Script")
    print("====================================\n")
    
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
    
    # Step 3: Create .spec file (optional, for reference)
    create_spec_file()
    
    # Step 4: Build the executable
    if build_executable():
        print("\n✓ All done! Your executable is ready to use.")
        return 0
    else:
        print("\n✗ Build failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
