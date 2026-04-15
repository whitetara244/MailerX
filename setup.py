# setup.py - PyInstaller configuration for MailerX Pro
"""
PyInstaller setup script for MailerX Pro Desktop Application
Run: python setup.py
"""

import os
import sys
import shutil
from PyInstaller.__main__ import run

def clean_build_dirs():
    """Clean previous build directories"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✓ Cleaned {dir_name}/")
    
    # Clean spec file
    spec_file = 'MailerXPro.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"✓ Removed {spec_file}")

def get_pyinstaller_args():
    """Get PyInstaller arguments for MailerX Pro"""
    
    # Ensure data directories exist
    os.makedirs('data/templates', exist_ok=True)
    os.makedirs('data/attachments', exist_ok=True)
    os.makedirs('data/uploads', exist_ok=True)
    
    args = [
        'desktop_app.py',  # Entry point
        '--name=MailerXPro',
        '--onefile',  # Single executable file
        '--windowed',  # No console window (GUI app)
        '--icon=NONE',  # Add icon if available: '--icon=icon.ico'
        '--clean',
        '--noconfirm',
        
        # Add data files
        f'--add-data=index.html{os.pathsep}.',
        f'--add-data=main.py{os.pathsep}.',
        f'--add-data=data{os.pathsep}data',
        
        # Hidden imports (for dependencies)
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=werkzeug',
        '--hidden-import=jinja2',
        '--hidden-import=email',
        '--hidden-import=smtplib',
        '--hidden-import=csv',
        '--hidden-import=json',
        '--hidden-import=uuid',
        '--hidden-import=threading',
        '--hidden-import=datetime',
        '--hidden-import=logging',
        '--hidden-import=webbrowser',
        '--hidden-import=socket',
        '--hidden-import=platform',
        '--hidden-import=mimetypes',
        
        # Collect all necessary packages
        '--collect-all=flask',
        '--collect-all=flask_cors',
        '--collect-all=werkzeug',
        '--collect-all=jinja2',
        
        # Runtime options
        '--noupx',  # Disable UPX compression for better compatibility
        
        # Version info (optional)
        '--version-file=version.txt' if os.path.exists('version.txt') else '',
    ]
    
    # Filter out empty strings
    return [arg for arg in args if arg]

def create_version_file():
    """Create version info file for Windows executable"""
    version_content = '''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set to 2.0.0.0 for MailerX Pro
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    # Contains a bitmask that specifies the valid bits 'flags'
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - Windows NT, 0x40004 - Windows NT GUI
    OS=0x40004,
    # The general type of file.
    # 0x1 - application
    fileType=0x1,
    # The function of the file.
    # 0x0 - function unspecified
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'MailerX Technologies'),
        StringStruct(u'FileDescription', u'MailerX Pro - Enterprise Email Marketing System'),
        StringStruct(u'FileVersion', u'2.0.0'),
        StringStruct(u'InternalName', u'MailerXPro'),
        StringStruct(u'LegalCopyright', u'Copyright © 2025 MailerX Technologies'),
        StringStruct(u'OriginalFilename', u'MailerXPro.exe'),
        StringStruct(u'ProductName', u'MailerX Pro'),
        StringStruct(u'ProductVersion', u'2.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    with open('version.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)
    print("✓ Created version.txt")

def create_build_script():
    """Create a build script for easy execution"""
    build_script = '''@echo off
echo ========================================
echo   MailerX Pro - Desktop Builder
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Install required packages
echo [1/3] Installing required packages...
pip install pyinstaller flask flask-cors

REM Run PyInstaller
echo [2/3] Building executable...
python setup.py

REM Check build result
if exist "dist\\MailerXPro.exe" (
    echo.
    echo ========================================
    echo   BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Executable location: dist\\MailerXPro.exe
    echo Size: 
    dir "dist\\MailerXPro.exe" | find "MailerXPro.exe"
    echo.
    echo To run the application, double-click MailerXPro.exe
) else (
    echo.
    echo [ERROR] Build failed - executable not found
)

echo.
pause
'''
    
    with open('build.bat', 'w') as f:
        f.write(build_script)
    print("✓ Created build.bat")

def create_launcher_script():
    """Create a launcher script for development"""
    launcher = '''#!/usr/bin/env python
"""
MailerX Pro Launcher - Development Mode
Run this script to test the application before building
"""

import subprocess
import sys
import os

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     🚀 MailerX Pro - Development Launcher               ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Check if required packages are installed
    required_packages = ['flask', 'flask_cors']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        install = input("Install them now? (y/n): ")
        if install.lower() == 'y':
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
        else:
            print("Please install required packages and try again.")
            return
    
    # Run the desktop application
    try:
        subprocess.run([sys.executable, 'desktop_app.py'])
    except KeyboardInterrupt:
        print("\\nApplication stopped.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
'''
    
    with open('launcher.py', 'w') as f:
        f.write(launcher)
    print("✓ Created launcher.py")

def main():
    """Main build function"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     📦 MailerX Pro - Desktop Executable Builder         ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Clean previous builds
    print("Cleaning previous builds...")
    clean_build_dirs()
    
    # Create version file
    print("Creating version info...")
    create_version_file()
    
    # Create helper scripts
    create_build_script()
    create_launcher_script()
    
    # Run PyInstaller
    print("Building executable with PyInstaller...")
    args = get_pyinstaller_args()
    
    if args:
        try:
            run(args)
            print("""
            ✅ BUILD COMPLETE!
            
            📁 Executable location: dist/MailerXPro.exe
            💾 Size: Approximately 40-60 MB
            
            🚀 To run:
               Double-click MailerXPro.exe
            
            📝 Note: First launch may take a few seconds to start.
            """)
        except Exception as e:
            print(f"❌ Build failed: {e}")
            sys.exit(1)
    else:
        print("❌ No build arguments generated")
        sys.exit(1)

if __name__ == '__main__':
    main()