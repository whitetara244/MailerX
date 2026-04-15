# desktop_app.py - Enhanced PyWebView Entry Point for MailerX Pro
"""
MailerX Pro Desktop Application
Enterprise Email Marketing System with Native Desktop Window
"""

import webview
import threading
import time
import sys
import os
import signal
import webbrowser
import subprocess
from datetime import datetime

# Import Flask app from main.py
from main import app as flask_app


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
    """Manage Flask server lifecycle"""
    
    def __init__(self):
        self.server_thread = None
        self.is_running = False
        self.port = 5000
        self.host = '127.0.0.1'
        
    def start(self):
        """Start Flask server in background thread"""
        if self.is_running:
            return
        
        def run_server():
            try:
                print(f"🌐 Starting Flask server on http://{self.host}:{self.port}")
                flask_app.run(
                    host=self.host,
                    port=self.port,
                    threaded=True,
                    debug=False,
                    use_reloader=False
                )
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"⚠️ Port {self.port} is already in use. Trying alternative port...")
                    self.port = 5001
                    try:
                        flask_app.run(
                            host=self.host,
                            port=self.port,
                            threaded=True,
                            debug=False,
                            use_reloader=False
                        )
                    except Exception as e2:
                        print(f"❌ Failed to start server on port {self.port}: {e2}")
                else:
                    print(f"❌ Failed to start Flask server: {e}")
            except Exception as e:
                print(f"❌ Unexpected error starting Flask server: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
        
        # Wait for server to be ready
        wait_time = 0
        while wait_time < 10:
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((self.host, self.port))
                if result == 0:
                    print(f"✅ Flask server is ready on port {self.port}")
                    break
                sock.close()
            except:
                pass
            time.sleep(0.5)
            wait_time += 0.5
    
    def stop(self):
        """Stop Flask server"""
        self.is_running = False
        print("🛑 Flask server stopping...")


class MailerXWebView:
    """Manage WebView window and JavaScript bridge"""
    
    def __init__(self, server):
        self.server = server
        self.window = None
        
    def create_window(self):
        """Create and configure the WebView window"""
        
        # JavaScript API for desktop integration
        js_api = {
            'getAppVersion': self.get_app_version,
            'openExternalBrowser': self.open_external_browser,
            'showNotification': self.show_notification,
            'getSystemInfo': self.get_system_info,
            'minimizeWindow': self.minimize_window,
            'maximizeWindow': self.maximize_window,
            'closeWindow': self.close_window,
            'exportData': self.export_data,
            'printReport': self.print_report,
            'openDevTools': self.open_dev_tools
        }
        
        # Create window with JavaScript bridge
        self.window = webview.create_window(
            title='MailerX Pro | Enterprise Email Campaigns',
            url=f'http://{self.server.host}:{self.server.port}',
            width=1450,
            height=920,
            min_size=(1100, 700),
            text_select=False,
            confirm_close=True,
            background_color='#0f172a',
            js_api=js_api
        )
        
        return self.window
    
    # JavaScript callable methods
    def get_app_version(self):
        """Return application version"""
        return {
            'version': '2.0.0',
            'build_date': '2025-04-14',
            'name': 'MailerX Pro',
            'platform': sys.platform
        }
    
    def open_external_browser(self, url):
        """Open URL in system default browser"""
        try:
            webbrowser.open(url)
            return {'success': True, 'url': url}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def show_notification(self, title, message):
        """Show system notification"""
        print(f"🔔 Notification - {title}: {message}")
        return {'success': True}
    
    def get_system_info(self):
        """Get system information for diagnostics"""
        import platform
        return {
            'platform': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'python_version': sys.version,
            'host': self.server.host,
            'port': self.server.port,
            'executable': sys.executable if hasattr(sys, 'executable') else 'unknown'
        }
    
    def minimize_window(self):
        """Minimize the application window"""
        if self.window:
            self.window.minimize()
        return {'success': True}
    
    def maximize_window(self):
        """Toggle maximize/restore the application window"""
        if self.window:
            if getattr(self.window, 'maximized', False):
                self.window.restore()
            else:
                self.window.maximize()
        return {'success': True}
    
    def close_window(self):
        """Close the application window"""
        if self.window:
            self.window.destroy()
        return {'success': True}
    
    def open_dev_tools(self):
        """Open developer tools for debugging"""
        if self.window:
            self.window.evaluate_js("console.log('Dev Tools requested');")
            # In pywebview, dev tools can be opened with a flag
            print("💻 Dev Tools: Run with debug=True to enable")
        return {'success': True}
    
    def export_data(self, data_type, format='json'):
        """Export data from the application"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"mailerx_export_{data_type}_{timestamp}.{format}"
        
        # This would need to be implemented with actual data export logic
        return {
            'success': True,
            'filename': filename,
            'message': f'Export initiated for {data_type}'
        }
    
    def print_report(self, report_data):
        """Print a report"""
        if self.window:
            self.window.evaluate_js("window.print();")
        return {'success': True}


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received shutdown signal. Exiting...")
    sys.exit(0)


def ensure_data_directories():
    """Ensure all required data directories exist"""
    directories = [
        'data',
        'data/templates',
        'data/attachments',
        'data/uploads',
        'data/logs',
        'data/backups'
    ]
    
    for directory in directories:
        os.makedirs(resource_path(directory), exist_ok=True)
    
    print("✓ Data directories verified")


def main():
    """Main entry point for desktop application"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     🚀 MailerX Pro Desktop Application v2.0.0           ║
    ║     Enterprise Email Marketing System                   ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ensure data directories exist
    ensure_data_directories()
    
    # Initialize server
    server = MailerXServer()
    server.start()
    
    # Create WebView window
    webview_manager = MailerXWebView(server)
    window = webview_manager.create_window()
    
    # Optional: Load custom CSS for desktop mode
    def inject_desktop_styles():
        """Inject additional CSS for desktop optimization"""
        # Wait for page to load before injecting
        time.sleep(2)
        if window:
            window.evaluate_js("""
                // Add desktop-specific styles
                const style = document.createElement('style');
                style.textContent = `
                    /* Desktop optimizations */
                    .sidebar {
                        transition: all 0.2s ease;
                    }
                    .btn:hover {
                        transform: translateY(-1px);
                    }
                    /* Custom scrollbar for desktop */
                    ::-webkit-scrollbar {
                        width: 8px;
                        height: 8px;
                    }
                    ::-webkit-scrollbar-track {
                        background: #f1f5f9;
                        border-radius: 4px;
                    }
                    ::-webkit-scrollbar-thumb {
                        background: #cbd5e1;
                        border-radius: 4px;
                    }
                    ::-webkit-scrollbar-thumb:hover {
                        background: #94a3b8;
                    }
                    
                    /* Desktop app optimizations */
                    body {
                        user-select: none; /* Prevent text selection for better desktop feel */
                    }
                    
                    input, textarea {
                        user-select: text; /* Allow text selection in inputs */
                    }
                `;
                document.head.appendChild(style);
                
                // Add desktop API detection
                if (window.pywebview) {
                    console.log('✅ Desktop mode detected - PyWebView bridge active');
                    window.dispatchEvent(new CustomEvent('desktop-ready', { 
                        detail: { platform: 'desktop', version: '2.0.0' }
                    }));
                }
                
                // Add window control buttons if needed
                console.log('🎨 Desktop enhancements applied');
            """)
    
    # Start a thread to inject desktop styles after page loads
    style_thread = threading.Thread(target=inject_desktop_styles, daemon=True)
    style_thread.start()
    
    print(f"""
    ✨ MailerX Pro is now running!
    
    📱 Application URL: http://{server.host}:{server.port}
    🖥️  Native desktop window active
    🔗 JavaScript bridge available
    🛡️  CORS and security enabled
    
    📁 Data Directory: {resource_path('data')}
    
    ℹ️  To quit, close the window or press Ctrl+C in terminal
    """)
    
    # Start the WebView application
    try:
        webview.start(
            debug=False,  # Set to True only when debugging
            http_server=True,
            gui=None  # Auto-detect best GUI framework
        )
    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        print("👋 MailerX Pro has been closed.")


if __name__ == '__main__':
    main()