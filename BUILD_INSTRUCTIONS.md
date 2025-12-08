# Building BlocSimPy Standalone Executable

This guide explains how to create a standalone executable (.exe) of BlocSimPy that can run on Windows without requiring Python installation.

## Quick Start

### Method 1: Using the Batch File (Easiest)
1. Double-click `build_exe.bat`
2. Wait for the build process to complete
3. Find your executable in the `dist` folder

### Method 2: Using the Python Script
1. Open a terminal in the project directory
2. Run: `python build_exe.py`
3. Find your executable in the `dist` folder

## Requirements

- Python 3.7 or higher
- All project dependencies installed (`pip install -r requirements.txt` if you have one)
- PyInstaller (will be automatically installed by the build script if missing)

## What the Build Script Does

1. **Checks for PyInstaller**: Automatically installs it if not present
2. **Cleans old builds**: Removes previous `build` and `dist` folders
3. **Creates .spec file**: Generates a PyInstaller specification file for customization
4. **Builds executable**: Packages your app with all dependencies into a single .exe file

## Output

After successful build, you'll find:
- `dist/BlocSimPy.exe` - Your standalone executable
- `BlocSimPy.spec` - PyInstaller specification file (for customization)
- `build/` - Temporary build files (can be deleted)

## Distribution

You can distribute just the `BlocSimPy.exe` file from the `dist` folder. Users can run it without installing Python or any dependencies.

**Note**: The first run might take a few seconds as PyInstaller extracts files to a temporary directory.

## Customization

### Making a Directory-Based Build (Faster Startup)

If you want a faster-starting executable (but with multiple files), edit `build_exe.py` and change:
```python
"--onefile",  # Remove this line
```
to:
```python
"--onedir",   # Use this instead
```

### Adding an Icon

1. Create or find an `.ico` file for your app
2. Add this line to the `pyinstaller_args` in `build_exe.py`:
```python
"--icon=path/to/your/icon.ico",
```

### Reducing File Size

The executable might be large (50-200 MB) because it includes Python and all libraries. To reduce size:
- The script already excludes tkinter, IPython, and notebook
- Consider using `--onedir` instead of `--onefile` for better optimization
- Use UPX compression (already enabled in the .spec file)

### Enabling Console (for Debugging)

If you need to see console output for debugging:

In `build_exe.py`, change:
```python
"--windowed",  # Remove or comment this line
```
or set `console=True` in the .spec file.

## Troubleshooting

### "Module not found" errors
Add the missing module to the `hiddenimports` list in `build_exe.py`:
```python
"--hidden-import=your_module_name",
```

### Missing data files
Add data files using:
```python
"--add-data=source_path;destination_path",
```

### Build fails
1. Make sure all dependencies are installed in your Python environment
2. Try running the app with `python main.py` first to ensure it works
3. Check for any import errors in the PyInstaller output

### Antivirus flags the executable
This is common with PyInstaller executables. You may need to:
- Add an exception in your antivirus
- Sign the executable with a code signing certificate (for distribution)

## Advanced: Using the .spec File

For more control over the build process:

1. The script creates `BlocSimPy.spec` automatically
2. Customize this file as needed
3. Build using: `pyinstaller BlocSimPy.spec`

This allows you to:
- Add version information
- Include additional resources
- Configure runtime hooks
- And more...

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [PyInstaller Common Issues](https://pyinstaller.org/en/stable/common-issues.html)

---

**Happy Building!** 🚀
