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
        """Stop Flask server (note: Flask doesn't have a simple stop, but we can set flag)"""
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
            'printReport': self.print_report
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
            background_color='#f8fafc',
            js_api=js_api
        )
        
        return self.window
    
    # JavaScript callable methods
    def get_app_version(self):
        """Return application version"""
        return {
            'version': '2.0.0',
            'build_date': '2025-04-14',
            'name': 'MailerX Pro'
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
        # webview doesn't have native notifications, but we can log
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
            'port': self.server.port
        }
    
    def minimize_window(self):
        """Minimize the application window"""
        if self.window:
            self.window.minimize()
        return {'success': True}
    
    def maximize_window(self):
        """Toggle maximize/restore the application window"""
        if self.window:
            if self.window.maximized:
                self.window.restore()
            else:
                self.window.maximize()
        return {'success': True}
    
    def close_window(self):
        """Close the application window"""
        if self.window:
            self.window.destroy()
        return {'success': True}
    
    def export_data(self, data_type, format='json'):
        """Export data from the application (placeholder for actual export)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"mailerx_export_{data_type}_{timestamp}.{format}"
        
        # This would need to be implemented with actual data export logic
        # For now, return a simulated response
        return {
            'success': True,
            'filename': filename,
            'message': f'Export initiated for {data_type}'
        }
    
    def print_report(self, report_data):
        """Print a report (placeholder for actual printing)"""
        # In a real implementation, this would use webview's print functionality
        if self.window:
            # webview doesn't have built-in print, but we can load a print dialog via JS
            self.window.evaluate_js("window.print();")
        return {'success': True}


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received shutdown signal. Exiting...")
    sys.exit(0)


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
    
    # Initialize server
    server = MailerXServer()
    server.start()
    
    # Create WebView window
    webview_manager = MailerXWebView(server)
    window = webview_manager.create_window()
    
    # Optional: Load custom CSS for desktop mode
    # This can be injected via JavaScript when the page loads
    def inject_desktop_styles():
        """Inject additional CSS for desktop optimization"""
        # Wait for page to load before injecting
        time.sleep(1)
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
                `;
                document.head.appendChild(style);
                
                // Add desktop API detection
                if (window.pywebview) {
                    console.log('✅ Desktop mode detected - PyWebView bridge active');
                    window.dispatchEvent(new CustomEvent('desktop-ready', { 
                        detail: { platform: 'desktop', version: '2.0.0' }
                    }));
                }
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


# Optional: Run as single instance (Windows only)
def check_single_instance():
    """Ensure only one instance of the application runs"""
    if sys.platform == 'win32':
        try:
            import win32event
            import win32api
            from win32com.client import GetObject
            
            mutex_name = "MailerXPro_Desktop_Application"
            mutex = win32event.CreateMutex(None, False, mutex_name)
            if win32api.GetLastError() == win32event.ERROR_ALREADY_EXISTS:
                print("⚠️ Another instance of MailerX Pro is already running.")
                print("   Please close the other instance first.")
                return False
            return True
        except ImportError:
            # win32api not available, skip single instance check
            return True
    return True


if __name__ == '__main__':
    # Ensure data directories exist before starting
    from main import Config
    for path in [Config.TEMPLATES_PATH, Config.ATTACHMENTS_PATH, Config.LOGS_PATH, 
                 Config.BACKUPS_PATH, Config.UPLOADS_PATH]:
        os.makedirs(path, exist_ok=True)
    
    # Check for single instance (optional)
    if not check_single_instance():
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Run the application
    main()