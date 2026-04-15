#!/usr/bin/env python
"""
MailerX Pro - Complete Single File Builder
Combined setup and build script - No pywebview issues
Run: python build_mailerx.py
"""

import os
import sys
import shutil
import subprocess
import webbrowser
import threading
import time
from pathlib import Path

def print_banner():
    """Print application banner"""
    print("""
    ========================================
      MailerX Pro - Complete Builder
      Enterprise Email Marketing System
    ========================================
    """)

def clean_build_dirs():
    """Clean previous build directories"""
    print("\n[1/6] Cleaning previous builds...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  ✓ Removed {dir_name}/")
    
    # Clean spec files
    for spec_file in Path('.').glob('*.spec'):
        spec_file.unlink()
        print(f"  ✓ Removed {spec_file}")
    
    print("  ✓ Cleanup complete")

def check_python():
    """Check Python installation"""
    print("\n[2/6] Checking Python installation...")
    
    if sys.version_info.major < 3 or sys.version_info.minor < 8:
        print("  ✗ ERROR: Python 3.8+ required")
        print(f"  Your version: {sys.version}")
        return False
    
    print(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def install_dependencies():
    """Install required packages"""
    print("\n[3/6] Installing dependencies...")
    
    packages = [
        'flask==2.3.3',
        'flask-cors==4.0.0', 
        'werkzeug==2.3.7',
        'jinja2==3.1.2',
        'pyinstaller==6.3.0'
    ]
    
    for package in packages:
        print(f"  Installing {package}...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package, '--quiet'],
            capture_output=True
        )
        if result.returncode == 0:
            print(f"    ✓ {package.split('==')[0]} installed")
        else:
            print(f"    ⚠ Warning: {package} had issues, continuing...")
    
    print("  ✓ Dependencies installed")
    return True

def create_directories():
    """Create required data directories"""
    print("\n[4/6] Creating data directories...")
    
    directories = [
        'data',
        'data/templates',
        'data/attachments',
        'data/uploads',
        'data/logs',
        'data/backups'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"  ✓ Created {directory}/")
    
    return True

def check_files():
    """Check if required files exist"""
    print("\n[5/6] Checking required files...")
    
    required_files = ['main.py', 'index.html']
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ Missing: {file}")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n  ERROR: Missing {len(missing_files)} required file(s)")
        return False
    
    return True

def create_standalone_launcher():
    """Create standalone launcher without webview dependency"""
    print("\n  Creating standalone launcher...")
    
    launcher_content = '''# desktop_run.py - Standalone launcher for MailerX Pro
import sys
import os
import webbrowser
import threading
import time
import signal
import socket
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app
try:
    from main import app as flask_app
except ImportError as e:
    print(f"ERROR: Cannot import main.py - {e}")
    print("Make sure main.py is in the same directory")
    sys.exit(1)

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and bundled .exe"""
    try:
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    except Exception:
        return os.path.join(os.path.abspath("."), relative_path)

class MailerXServer:
    def __init__(self):
        self.server_thread = None
        self.is_running = False
        self.port = 5000
        self.host = '127.0.0.1'
    
    def start(self):
        if self.is_running:
            return
        
        def run_server():
            try:
                print(f"  Starting Flask server on http://{self.host}:{self.port}")
                flask_app.run(
                    host=self.host,
                    port=self.port,
                    threaded=True,
                    debug=False,
                    use_reloader=False
                )
            except OSError:
                self.port = 5001
                try:
                    print(f"  Port 5000 in use, trying port {self.port}")
                    flask_app.run(
                        host=self.host,
                        port=self.port,
                        threaded=True,
                        debug=False,
                        use_reloader=False
                    )
                except Exception as e:
                    print(f"  ERROR: Failed to start server: {e}")
            except Exception as e:
                print(f"  ERROR: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
        
        # Wait for server to be ready
        wait_time = 0
        while wait_time < 10:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex((self.host, self.port)) == 0:
                    print(f"  ✓ Server ready on port {self.port}")
                    break
                sock.close()
            except:
                pass
            time.sleep(0.5)
            wait_time += 0.5

def signal_handler(signum, frame):
    print("\\n  Shutting down...")
    sys.exit(0)

def ensure_data_directories():
    directories = ['data', 'data/templates', 'data/attachments', 
                   'data/uploads', 'data/logs', 'data/backups']
    for directory in directories:
        os.makedirs(resource_path(directory), exist_ok=True)

def main():
    print("""
    ========================================
      MailerX Pro - Enterprise Edition
      Email Marketing System
    ========================================
    """)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("  Starting MailerX Pro...")
    ensure_data_directories()
    
    server = MailerXServer()
    server.start()
    
    url = f"http://{server.host}:{server.port}"
    
    print(f"""
    ========================================
      Application is running!
    ========================================
    
      URL: {url}
      Data: data/
      
      Opening in your browser...
    
    ========================================
    """)
    
    # Open browser after short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("  Press Ctrl+C to stop the application")
    print("  Close this window to exit\\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\n  Shutting down...")

if __name__ == '__main__':
    main()
'''
    
    with open('desktop_run.py', 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    print("  ✓ Created desktop_run.py")
    return True

def build_executable():
    """Build executable with PyInstaller"""
    print("\n[6/6] Building executable with PyInstaller...")
    print("  This may take 2-4 minutes...\n")
    
    # PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--name=MailerXPro',
        '--add-data', f'index.html{os.pathsep}.',
        '--add-data', f'main.py{os.pathsep}.',
        '--add-data', f'data{os.pathsep}data',
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
        '--collect-all=flask',
        '--collect-all=flask_cors',
        '--collect-all=werkzeug',
        '--collect-all=jinja2',
        '--noupx',
        'desktop_run.py'
    ]
    
    # Run PyInstaller
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("\n  ✗ Build failed!")
        
        # Try alternative build without --onefile
        print("\n  Trying alternative build method...")
        cmd_alt = [
            sys.executable, '-m', 'PyInstaller',
            '--name=MailerXPro',
            '--add-data', f'index.html{os.pathsep}.',
            '--add-data', f'main.py{os.pathsep}.',
            '--add-data', f'data{os.pathsep}data',
            'desktop_run.py'
        ]
        result = subprocess.run(cmd_alt, capture_output=False)
        
        if result.returncode == 0 and os.path.exists('dist/MailerXPro/desktop_run.exe'):
            print("\n  ✓ Alternative build created")
            return 'dist/MailerXPro/desktop_run.exe'
        return None
    
    return 'dist/MailerXPro.exe' if os.path.exists('dist/MailerXPro.exe') else None

def show_result(executable_path):
    """Show build result and offer to run"""
    print("\n" + "="*40)
    if executable_path and os.path.exists(executable_path):
        print("  ✓ BUILD SUCCESSFUL!")
        print("="*40)
        print(f"\n  Executable: {os.path.abspath(executable_path)}")
        
        # Get file size
        size = os.path.getsize(executable_path) / (1024 * 1024)
        print(f"  Size: {size:.1f} MB")
        
        print("\n" + "="*40)
        print("\n  Features:")
        print("  • Standalone executable - No Python required")
        print("  • Opens in your default browser")
        print("  • All data saved locally")
        print("  • SMTP email sending support")
        print("  • Template management with attachments")
        print("  • CSV recipient management")
        print("  • Blacklist protection")
        
        print("\n" + "="*40)
        choice = input("\n  Run MailerXPro now? (y/n): ").lower()
        if choice == 'y':
            print("\n  Launching MailerXPro...")
            subprocess.Popen([executable_path], shell=True)
            print("  Application started! It will open in your browser.")
    else:
        print("  ✗ BUILD FAILED!")
        print("="*40)
        print("\n  Troubleshooting:")
        print("  1. Make sure main.py and index.html exist")
        print("  2. Try running as Administrator")
        print("  3. Check your internet connection")
        print("  4. Temporarily disable antivirus")
    
    print()

def cleanup_temp_files():
    """Remove temporary files"""
    temp_files = ['desktop_run.py', 'desktop_run.spec']
    for file in temp_files:
        if os.path.exists(file):
            try:
                os.remove(file)
            except:
                pass

def main():
    """Main build function"""
    print_banner()
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Step 1: Clean
    clean_build_dirs()
    
    # Step 2: Check Python
    if not check_python():
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Step 3: Install dependencies
    if not install_dependencies():
        print("\n  Warning: Some packages failed to install")
        response = input("  Continue anyway? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    
    # Step 4: Create directories
    create_directories()
    
    # Step 5: Check files
    if not check_files():
        print("\n  Missing required files!")
        print("  Make sure main.py and index.html are in this folder")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Step 6: Create standalone launcher
    create_standalone_launcher()
    
    # Step 7: Build executable
    executable = build_executable()
    
    # Step 8: Show result
    show_result(executable)
    
    # Step 9: Cleanup
    cleanup_temp_files()
    
    input("\nPress Enter to exit...")

if __name__ == '__main__':
    main()