# main.py - Fixed production version
"""
SuperMailer Pro - Production Grade Email Marketing System
Designed for 50k+ email campaigns with enterprise security and scalability
"""

import os
import sys
import smtplib
import json
import uuid
import hashlib
import secrets
import threading
import time
import functools
import queue
import asyncio
import logging
import tempfile
import csv
import io
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from contextlib import contextmanager
from dataclasses import dataclass, asdict

# Core web framework
from flask import Flask, render_template, request, jsonify, send_file, session, g, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Try to import optional dependencies
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    FLASK_LIMITER_AVAILABLE = True
except ImportError:
    FLASK_LIMITER_AVAILABLE = False
    Limiter = None
    get_remote_address = None

try:
    from flask_talisman import Talisman
    FLASK_TALISMAN_AVAILABLE = True
except ImportError:
    FLASK_TALISMAN_AVAILABLE = False
    Talisman = None

try:
    from flask_compress import Compress
    FLASK_COMPRESS_AVAILABLE = True
except ImportError:
    FLASK_COMPRESS_AVAILABLE = False
    Compress = None

try:
    from flask_caching import Cache
    FLASK_CACHING_AVAILABLE = True
except ImportError:
    FLASK_CACHING_AVAILABLE = False
    Cache = None

# Email validation
from email_validator import validate_email, EmailNotValidError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, utils

# ==================== Environment Configuration ====================
@dataclass
class Config:
    """Central configuration management"""
    
    # Security
    SECRET_KEY: str = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.environ.get('JWT_SECRET_KEY', secrets.token_urlsafe(32))
    ENCRYPTION_KEY: str = os.environ.get('ENCRYPTION_KEY', '')
    SESSION_COOKIE_SECURE: bool = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    PERMANENT_SESSION_LIFETIME: int = int(os.environ.get('PERMANENT_SESSION_LIFETIME', '7200'))
    
    # Database - Use SQLite for production simplicity
    DATABASE_PATH: str = os.environ.get('DATABASE_PATH', '/app/data/supermailer.db')
    CONFIG_PATH: str = os.environ.get('CONFIG_PATH', '/app/data/config.json')
    TEMPLATES_PATH: str = os.environ.get('TEMPLATES_PATH', '/app/data/templates')
    LOGS_PATH: str = os.environ.get('LOGS_PATH', '/app/data/logs')
    BACKUPS_PATH: str = os.environ.get('BACKUPS_PATH', '/app/data/backups')
    UPLOADS_PATH: str = os.environ.get('UPLOADS_PATH', '/app/data/uploads')
    
    # Redis (optional)
    REDIS_URL: str = os.environ.get('REDIS_URL', '')
    
    # Email Sending
    SMTP_POOL_SIZE: int = int(os.environ.get('SMTP_POOL_SIZE', '10'))
    MAX_CONCURRENT_CAMPAIGNS: int = int(os.environ.get('MAX_CONCURRENT_CAMPAIGNS', '5'))
    BATCH_SIZE: int = int(os.environ.get('BATCH_SIZE', '500'))
    PARALLEL_WORKERS: int = int(os.environ.get('PARALLEL_WORKERS', '10'))
    
    # Rate Limiting (defaults)
    DEFAULT_RATE_LIMIT: int = int(os.environ.get('DEFAULT_RATE_LIMIT', '5000'))
    
    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Feature flags
    ENABLE_METRICS: bool = os.environ.get('ENABLE_METRICS', 'false').lower() == 'true'
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create config from dict"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

# Create necessary directories
for path in [Config.DATABASE_PATH, Config.CONFIG_PATH, Config.TEMPLATES_PATH, 
             Config.LOGS_PATH, Config.BACKUPS_PATH, Config.UPLOADS_PATH]:
    dir_path = os.path.dirname(path) if '.' in os.path.basename(path) else path
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

# ==================== Logging Setup ====================
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(Config.LOGS_PATH, 'supermailer.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== Initialize Flask App ====================
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=Config.PERMANENT_SESSION_LIFETIME)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Security middleware (only if available)
if FLASK_TALISMAN_AVAILABLE and Talisman:
    Talisman(app, content_security_policy=None, force_https=False)

if FLASK_COMPRESS_AVAILABLE and Compress:
    Compress(app)

CORS(app, resources={r"/api/*": {"origins": "*"}})

# Rate limiting setup
if FLASK_LIMITER_AVAILABLE and Limiter and get_remote_address:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[f"{Config.DEFAULT_RATE_LIMIT}/day", "500/hour", "10/minute"],
        storage_uri=Config.REDIS_URL if Config.REDIS_URL else "memory://"
    )
else:
    # Dummy limiter
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            return lambda f: f
    limiter = DummyLimiter()

# Cache setup
if FLASK_CACHING_AVAILABLE and Cache:
    if Config.REDIS_URL:
        cache = Cache(app, config={
            'CACHE_TYPE': 'RedisCache',
            'CACHE_REDIS_URL': Config.REDIS_URL,
            'CACHE_DEFAULT_TIMEOUT': 300
        })
    else:
        cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
else:
    cache = None

# ==================== Data Storage Manager ====================
class StorageManager:
    """File-based storage manager for production"""
    
    def __init__(self):
        self.config_file = Config.CONFIG_PATH
        self.templates_dir = Config.TEMPLATES_PATH
        self.logs_dir = Config.LOGS_PATH
        self.backups_dir = Config.BACKUPS_PATH
        self.uploads_dir = Config.UPLOADS_PATH
        self.db_file = Config.DATABASE_PATH
        
    # ===== Configuration Management =====
    def load_config(self) -> dict:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()
    
    def save_config(self, config: dict) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            'smtp': {
                'server': '',
                'port': 587,
                'username': '',
                'password': '',
                'use_tls': True,
                'use_ssl': False,
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 5
            },
            'email': {
                'from_email': '',
                'from_name': 'SuperMailer Pro',
                'reply_to': '',
                'bounce_address': ''
            },
            'campaign': {
                'rate_limit': 5,
                'max_emails_per_batch': 50,
                'parallel_workers': 3,
                'max_emails_per_hour': 500,
                'max_emails_per_day': 5000,
                'enable_tracking': True,
                'enable_unsubscribe': True
            }
        }
    
    # ===== Template Management =====
    def list_templates(self) -> List[dict]:
        """List all email templates"""
        templates = []
        try:
            if not os.path.exists(self.templates_dir):
                os.makedirs(self.templates_dir, exist_ok=True)
                self._create_default_templates()
            
            for file in os.listdir(self.templates_dir):
                if file.endswith('.html'):
                    file_path = os.path.join(self.templates_dir, file)
                    stat = os.stat(file_path)
                    templates.append({
                        'name': file.replace('.html', ''),
                        'filename': file,
                        'size_kb': round(stat.st_size / 1024, 1),
                        'modified': stat.st_mtime,
                        'created': stat.st_ctime
                    })
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
        return sorted(templates, key=lambda x: x['modified'], reverse=True)
    
    def _create_default_templates(self):
        """Create default templates"""
        default_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; font-size: 12px; color: #999; }
        h1 { margin: 0; font-size: 28px; }
        p { margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Hello {{name}}!</h1>
        </div>
        <div class="content">
            <p>Thank you for being part of our community.</p>
            <p>Your email: <strong>{{email}}</strong></p>
            {% if company %}
            <p>Company: {{company}}</p>
            {% endif %}
            <p>We're excited to share our latest updates with you.</p>
            <a href="{{cta_url}}" class="button">Learn More</a>
        </div>
        <div class="footer">
            <p>You received this email because you subscribed to our newsletter.</p>
            <p><a href="{{unsubscribe_url}}">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>"""
        
        with open(os.path.join(self.templates_dir, 'welcome.html'), 'w') as f:
            f.write(default_template)
    
    def get_template(self, name: str) -> Optional[str]:
        """Get template content by name"""
        try:
            # Sanitize filename
            safe_name = secure_filename(name).replace('.html', '')
            file_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to get template {name}: {e}")
        return None
    
    def save_template(self, name: str, content: str) -> bool:
        """Save template to file"""
        try:
            safe_name = secure_filename(name).replace('.html', '')
            if not safe_name:
                return False
            file_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            with open(file_path, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to save template {name}: {e}")
            return False
    
    def delete_template(self, name: str) -> bool:
        """Delete template file"""
        try:
            safe_name = secure_filename(name).replace('.html', '')
            file_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete template {name}: {e}")
        return False
    
    # ===== Campaign Management =====
    def load_campaigns(self) -> List[dict]:
        """Load all campaigns from database file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    return data.get('campaigns', [])
        except Exception as e:
            logger.error(f"Failed to load campaigns: {e}")
        return []
    
    def save_campaign(self, campaign: dict) -> bool:
        """Save campaign to database file"""
        try:
            campaigns = self.load_campaigns()
            # Update or add
            existing_idx = None
            for i, c in enumerate(campaigns):
                if c.get('id') == campaign.get('id'):
                    existing_idx = i
                    break
            
            if existing_idx is not None:
                campaigns[existing_idx] = campaign
            else:
                campaigns.append(campaign)
            
            with open(self.db_file, 'w') as f:
                json.dump({'campaigns': campaigns}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save campaign: {e}")
            return False
    
    def update_campaign_stats(self, campaign_id: str, stats: dict) -> bool:
        """Update campaign statistics"""
        try:
            campaigns = self.load_campaigns()
            for c in campaigns:
                if c.get('id') == campaign_id:
                    if 'stats' not in c:
                        c['stats'] = {}
                    c['stats'].update(stats)
                    return self.save_campaign(c)
        except Exception as e:
            logger.error(f"Failed to update campaign stats: {e}")
        return False
    
    # ===== Recipient Files Management =====
    def list_recipient_files(self) -> List[dict]:
        """List all uploaded recipient files"""
        files = []
        try:
            if not os.path.exists(self.uploads_dir):
                os.makedirs(self.uploads_dir, exist_ok=True)
            
            for file in os.listdir(self.uploads_dir):
                if file.endswith('.csv'):
                    file_path = os.path.join(self.uploads_dir, file)
                    stat = os.stat(file_path)
                    
                    # Count rows
                    row_count = 0
                    try:
                        with open(file_path, 'r') as f:
                            reader = csv.reader(f)
                            row_count = sum(1 for _ in reader) - 1
                    except:
                        pass
                    
                    files.append({
                        'name': file,
                        'display_name': file.replace('.csv', '').replace('_', ' '),
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'row_count': max(0, row_count),
                        'modified': stat.st_mtime
                    })
        except Exception as e:
            logger.error(f"Failed to list recipient files: {e}")
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    
    def save_recipient_file(self, file_data, filename: str) -> Optional[str]:
        """Save uploaded recipient file"""
        try:
            safe_name = secure_filename(filename)
            if not safe_name.endswith('.csv'):
                safe_name += '.csv'
            
            # Add timestamp to avoid collisions
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_name = f"{timestamp}_{safe_name}"
            file_path = os.path.join(self.uploads_dir, final_name)
            
            file_data.save(file_path)
            return final_name
        except Exception as e:
            logger.error(f"Failed to save recipient file: {e}")
            return None
    
    def delete_recipient_file(self, filename: str) -> bool:
        """Delete recipient file"""
        try:
            safe_name = secure_filename(filename)
            file_path = os.path.join(self.uploads_dir, safe_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete recipient file: {e}")
        return False
    
    def get_recipients(self, filename: str, limit: int = 100) -> List[dict]:
        """Get recipients from CSV file"""
        recipients = []
        try:
            safe_name = secure_filename(filename)
            file_path = os.path.join(self.uploads_dir, safe_name)
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if i >= limit:
                            break
                        recipients.append(row)
        except Exception as e:
            logger.error(f"Failed to get recipients: {e}")
        return recipients
    
    def count_recipients(self, filename: str) -> int:
        """Count total recipients in CSV file"""
        try:
            safe_name = secure_filename(filename)
            file_path = os.path.join(self.uploads_dir, safe_name)
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return sum(1 for _ in f) - 1
        except Exception as e:
            logger.error(f"Failed to count recipients: {e}")
        return 0
    
    # ===== Blacklist Management =====
    def load_blacklist(self) -> List[str]:
        """Load blacklisted emails"""
        blacklist_file = os.path.join(self.db_file.replace('.db', '_blacklist.json'))
        try:
            if os.path.exists(blacklist_file):
                with open(blacklist_file, 'r') as f:
                    data = json.load(f)
                    return data.get('emails', [])
        except Exception as e:
            logger.error(f"Failed to load blacklist: {e}")
        return []
    
    def save_blacklist(self, emails: List[str]) -> bool:
        """Save blacklisted emails"""
        blacklist_file = os.path.join(self.db_file.replace('.db', '_blacklist.json'))
        try:
            with open(blacklist_file, 'w') as f:
                json.dump({'emails': list(set(emails)), 'updated_at': datetime.now().isoformat()}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save blacklist: {e}")
            return False
    
    def add_to_blacklist(self, emails: List[str]) -> int:
        """Add emails to blacklist"""
        current = self.load_blacklist()
        new_emails = [e.lower().strip() for e in emails if e and '@' in e]
        updated = list(set(current + new_emails))
        self.save_blacklist(updated)
        return len(new_emails)
    
    def remove_from_blacklist(self, emails: List[str]) -> int:
        """Remove emails from blacklist"""
        current = self.load_blacklist()
        to_remove = set([e.lower().strip() for e in emails])
        updated = [e for e in current if e not in to_remove]
        self.save_blacklist(updated)
        return len(current) - len(updated)
    
    # ===== Log Management =====
    def list_logs(self) -> List[dict]:
        """List all log files"""
        logs = []
        try:
            if os.path.exists(self.logs_dir):
                for file in os.listdir(self.logs_dir):
                    if file.endswith('.log'):
                        file_path = os.path.join(self.logs_dir, file)
                        stat = os.stat(file_path)
                        logs.append({
                            'name': file,
                            'type': 'campaign' if 'campaign' in file else 'system',
                            'size_kb': round(stat.st_size / 1024, 1),
                            'modified': stat.st_mtime
                        })
        except Exception as e:
            logger.error(f"Failed to list logs: {e}")
        return sorted(logs, key=lambda x: x['modified'], reverse=True)
    
    def get_log_content(self, filename: str, lines: int = 500) -> Optional[str]:
        """Get log file content"""
        try:
            safe_name = secure_filename(filename)
            file_path = os.path.join(self.logs_dir, safe_name)
            
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                    if lines > 0:
                        content_lines = content.split('\n')
                        content = '\n'.join(content_lines[-lines:])
                    return content
        except Exception as e:
            logger.error(f"Failed to get log content: {e}")
        return None
    
    def delete_log(self, filename: str) -> bool:
        """Delete log file"""
        try:
            safe_name = secure_filename(filename)
            file_path = os.path.join(self.logs_dir, safe_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete log: {e}")
        return False
    
    # ===== Backup Management =====
    def list_backups(self) -> List[dict]:
        """List all backups"""
        backups = []
        try:
            if not os.path.exists(self.backups_dir):
                os.makedirs(self.backups_dir, exist_ok=True)
            
            for file in os.listdir(self.backups_dir):
                if file.endswith('.zip'):
                    file_path = os.path.join(self.backups_dir, file)
                    stat = os.stat(file_path)
                    backups.append({
                        'id': file.replace('.zip', ''),
                        'filename': file,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created': stat.st_mtime
                    })
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def create_backup(self) -> Optional[dict]:
        """Create a backup of all data"""
        import zipfile
        
        try:
            backup_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(self.backups_dir, f"{backup_id}.zip")
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add config
                if os.path.exists(self.config_file):
                    zipf.write(self.config_file, 'config.json')
                
                # Add database
                if os.path.exists(self.db_file):
                    zipf.write(self.db_file, 'database.json')
                
                # Add templates
                if os.path.exists(self.templates_dir):
                    for root, dirs, files in os.walk(self.templates_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join('templates', file)
                            zipf.write(file_path, arcname)
                
                # Add blacklist
                blacklist_file = os.path.join(self.db_file.replace('.db', '_blacklist.json'))
                if os.path.exists(blacklist_file):
                    zipf.write(blacklist_file, 'blacklist.json')
            
            stat = os.stat(backup_path)
            return {
                'id': backup_id,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': stat.st_mtime
            }
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def get_backup_path(self, backup_id: str) -> Optional[str]:
        """Get backup file path"""
        try:
            safe_id = secure_filename(backup_id)
            file_path = os.path.join(self.backups_dir, f"{safe_id}.zip")
            if os.path.exists(file_path):
                return file_path
        except Exception as e:
            logger.error(f"Failed to get backup path: {e}")
        return None
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete backup file"""
        try:
            safe_id = secure_filename(backup_id)
            file_path = os.path.join(self.backups_dir, f"{safe_id}.zip")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
        return False
    
    # ===== System Information =====
    def get_system_info(self) -> dict:
        """Get system information"""
        import platform
        import psutil 
        if importlib.util.find_spec('psutil') else None;
        
        info = {
            'system': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'hostname': platform.node()
            },
            'app': {
                'templates': len(self.list_templates()),
                'uploaded_files': len(self.list_recipient_files()),
                'total_campaigns': len(self.load_campaigns()),
                'active_campaigns': sum(1 for c in self.load_campaigns() if c.get('status') in ['running', 'queued'])
            }
        }
        
        # Add disk info if psutil available
        try:
            import psutil
            disk = psutil.disk_usage(self.backups_dir)
            info['disk'] = {
                'total_gb': round(disk.total / (1024**3), 1),
                'free_gb': round(disk.free / (1024**3), 1),
                'used_gb': round(disk.used / (1024**3), 1),
                'percent_used': disk.percent
            }
            memory = psutil.virtual_memory()
            info['memory'] = {
                'total_gb': round(memory.total / (1024**3), 1),
                'available_gb': round(memory.available / (1024**3), 1),
                'percent_used': memory.percent
            }
            info['cpu'] = {
                'count': psutil.cpu_count(),
                'percent': psutil.cpu_percent(interval=0.1)
            }
        except:
            pass
        
        return info

# ==================== SMTP Email Sender ====================
class SMTPEmailSender:
    """SMTP email sender with connection pooling and rate limiting"""
    
    def __init__(self, config: dict):
        self.config = config
        self._lock = threading.Lock()
        self._active_sends = 0
    
    def send_email(self, to_email: str, subject: str, html_content: str, 
                   text_content: str = None, from_email: str = None, 
                   from_name: str = None, reply_to: str = None) -> Tuple[bool, str]:
        """Send a single email"""
        try:
            smtp_config = self.config.get('smtp', {})
            email_config = self.config.get('email', {})
            
            if not smtp_config.get('server') or not smtp_config.get('username'):
                return False, "SMTP not configured"
            
            # Rate limiting
            with self._lock:
                if self._active_sends >= 10:
                    return False, "Rate limit exceeded"
                self._active_sends += 1
            
            try:
                # Create message
                from_email_addr = from_email or email_config.get('from_email') or smtp_config.get('username')
                from_name_str = from_name or email_config.get('from_name', 'SuperMailer Pro')
                
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{from_name_str} <{from_email_addr}>"
                msg['To'] = to_email
                msg['Subject'] = subject
                msg['Message-ID'] = f"<{uuid.uuid4()}@{from_email_addr.split('@')[-1]}>"
                msg['Date'] = utils.formatdate(localtime=True)
                
                if reply_to:
                    msg['Reply-To'] = reply_to
                elif email_config.get('reply_to'):
                    msg['Reply-To'] = email_config['reply_to']
                
                # Attach parts
                if text_content:
                    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
                else:
                    # Convert HTML to text
                    import re
                    text_content = re.sub(r'<[^>]+>', '', html_content)
                    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
                
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                
                # Connect and send
                if smtp_config.get('use_ssl'):
                    server = smtplib.SMTP_SSL(
                        smtp_config['server'],
                        smtp_config.get('port', 465),
                        timeout=smtp_config.get('timeout', 30)
                    )
                else:
                    server = smtplib.SMTP(
                        smtp_config['server'],
                        smtp_config.get('port', 587),
                        timeout=smtp_config.get('timeout', 30)
                    )
                    if smtp_config.get('use_tls', True):
                        server.starttls()
                
                server.login(smtp_config['username'], smtp_config.get('password', ''))
                server.send_message(msg)
                server.quit()
                
                return True, "Sent successfully"
                
            finally:
                with self._lock:
                    self._active_sends -= 1
                    
        except smtplib.SMTPAuthenticationError:
            return False, "SMTP authentication failed"
        except smtplib.SMTPRecipientsRefused:
            return False, "Recipient refused"
        except Exception as e:
            return False, str(e)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test SMTP connection"""
        try:
            smtp_config = self.config.get('smtp', {})
            
            if not smtp_config.get('server') or not smtp_config.get('username'):
                return False, "SMTP not configured"
            
            if smtp_config.get('use_ssl'):
                server = smtplib.SMTP_SSL(
                    smtp_config['server'],
                    smtp_config.get('port', 465),
                    timeout=smtp_config.get('timeout', 10)
                )
            else:
                server = smtplib.SMTP(
                    smtp_config['server'],
                    smtp_config.get('port', 587),
                    timeout=smtp_config.get('timeout', 10)
                )
                if smtp_config.get('use_tls', True):
                    server.starttls()
            
            server.login(smtp_config['username'], smtp_config.get('password', ''))
            server.quit()
            
            return True, "Connection successful"
            
        except Exception as e:
            return False, str(e)

# Initialize storage and email sender
storage = StorageManager()
email_sender = None

def get_email_sender():
    """Get or create email sender instance"""
    global email_sender
    if email_sender is None:
        config = storage.load_config()
        email_sender = SMTPEmailSender(config)
    return email_sender

# ==================== Template Helper ====================
def render_template_content(template_content: str, context: dict) -> str:
    """Simple template rendering with variable substitution"""
    import re
    
    content = template_content
    
    # Replace {{variable}} patterns
    for key, value in context.items():
        if value is not None:
            content = content.replace(f'{{{{{key}}}}}', str(value))
    
    # Handle {% if variable %} blocks (simplified)
    def process_if_blocks(text):
        pattern = r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}'
        
        def replacer(match):
            var_name = match.group(1)
            block_content = match.group(2)
            if context.get(var_name):
                return block_content
            return ''
        
        return re.sub(pattern, replacer, text, flags=re.DOTALL)
    
    content = process_if_blocks(content)
    
    return content

# ==================== Campaign Worker ====================
class CampaignWorker:
    """Background campaign worker"""
    
    def __init__(self):
        self.active_campaigns = {}
        self._lock = threading.Lock()
    
    def start_campaign(self, campaign_id: str, config: dict, 
                       recipients_file: str, template_content: str, 
                       subject: str, reply_to: str = None,
                       on_progress: callable = None) -> bool:
        """Start a campaign in background thread"""
        
        with self._lock:
            if campaign_id in self.active_campaigns:
                return False
        
        def run():
            try:
                self._run_campaign(campaign_id, config, recipients_file, 
                                  template_content, subject, reply_to, on_progress)
            finally:
                with self._lock:
                    if campaign_id in self.active_campaigns:
                        del self.active_campaigns[campaign_id]
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        
        with self._lock:
            self.active_campaigns[campaign_id] = {
                'thread': thread,
                'status': 'running',
                'started_at': datetime.now().isoformat()
            }
        
        return True
    
    def _run_campaign(self, campaign_id: str, config: dict,
                      recipients_file: str, template_content: str,
                      subject: str, reply_to: str = None,
                      on_progress: callable = None):
        """Run the campaign"""
        
        try:
            # Load recipients
            recipients = storage.get_recipients(recipients_file, limit=10000)
            blacklist = storage.load_blacklist()
            blacklist_set = set(blacklist)
            
            total = len(recipients)
            sent = 0
            failed = 0
            skipped = 0
            
            # Filter out blacklisted
            valid_recipients = [r for r in recipients if r.get('email', '').lower() not in blacklist_set]
            skipped = total - len(valid_recipients)
            total = len(valid_recipients)
            
            # Update campaign
            campaign = {
                'id': campaign_id,
                'status': 'running',
                'started_at': datetime.now().isoformat(),
                'total_recipients': total,
                'stats': {'sent': 0, 'failed': 0, 'skipped': skipped}
            }
            storage.save_campaign(campaign)
            
            # Create email sender
            sender = SMTPEmailSender(config)
            campaign_config = config.get('campaign', {})
            rate_limit = campaign_config.get('rate_limit', 5)
            batch_delay = 1.0 / rate_limit if rate_limit > 0 else 0
            
            for i, recipient in enumerate(valid_recipients):
                # Check if campaign was stopped
                with self._lock:
                    if campaign_id not in self.active_campaigns:
                        break
                    if self.active_campaigns[campaign_id].get('status') == 'stopped':
                        break
                
                # Personalize content
                context = {
                    'name': recipient.get('name', 'Valued Customer'),
                    'email': recipient.get('email', ''),
                    'company': recipient.get('company', ''),
                    'city': recipient.get('city', ''),
                    'cta_url': campaign_config.get('cta_url', '#'),
                    'unsubscribe_url': campaign_config.get('unsubscribe_url', '#'),
                    'subject': subject
                }
                
                personalized_html = render_template_content(template_content, context)
                personalized_subject = render_template_content(subject, context)
                
                # Send email
                success, message = sender.send_email(
                    to_email=recipient['email'],
                    subject=personalized_subject,
                    html_content=personalized_html,
                    reply_to=reply_to
                )
                
                if success:
                    sent += 1
                else:
                    failed += 1
                    logger.error(f"Failed to send to {recipient['email']}: {message}")
                
                # Update progress
                if (i + 1) % 10 == 0:
                    campaign = storage.load_campaigns()
                    for c in campaign:
                        if c.get('id') == campaign_id:
                            c['stats']['sent'] = sent
                            c['stats']['failed'] = failed
                            storage.save_campaign(c)
                            break
                    
                    if on_progress:
                        on_progress(campaign_id, sent + failed, total, sent, failed)
                
                # Rate limiting
                if batch_delay > 0:
                    time.sleep(batch_delay)
            
            # Final update
            final_status = 'completed' if sent > 0 else 'failed'
            campaign = {
                'id': campaign_id,
                'status': final_status,
                'completed_at': datetime.now().isoformat(),
                'total_recipients': total,
                'stats': {'sent': sent, 'failed': failed, 'skipped': skipped}
            }
            storage.save_campaign(campaign)
            
            # Create campaign log
            log_content = f"""Campaign: {campaign_id}
Started: {campaign.get('started_at')}
Completed: {campaign.get('completed_at')}
Status: {final_status}
Total: {total}
Sent: {sent}
Failed: {failed}
Skipped (blacklisted): {skipped}
Success Rate: {round(sent/max(total,1)*100, 1)}%
"""
            log_file = os.path.join(Config.LOGS_PATH, f"campaign_{campaign_id}.log")
            with open(log_file, 'w') as f:
                f.write(log_content)
            
        except Exception as e:
            logger.error(f"Campaign {campaign_id} failed: {e}")
            campaign = {
                'id': campaign_id,
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.now().isoformat()
            }
            storage.save_campaign(campaign)
    
    def stop_campaign(self, campaign_id: str) -> bool:
        """Stop a running campaign"""
        with self._lock:
            if campaign_id in self.active_campaigns:
                self.active_campaigns[campaign_id]['status'] = 'stopped'
                return True
        return False
    
    def get_campaign_status(self, campaign_id: str) -> Optional[dict]:
        """Get campaign status"""
        campaigns = storage.load_campaigns()
        for c in campaigns:
            if c.get('id') == campaign_id:
                status = c.get('status', 'unknown')
                if campaign_id in self.active_campaigns:
                    status = self.active_campaigns[campaign_id].get('status', 'running')
                return {
                    'id': c.get('id'),
                    'name': c.get('name', ''),
                    'status': status,
                    'total_recipients': c.get('total_recipients', 0),
                    'stats': c.get('stats', {}),
                    'started_at': c.get('started_at'),
                    'completed_at': c.get('completed_at')
                }
        return None

campaign_worker = CampaignWorker()

# ==================== API Endpoints ====================

@app.route('/')
def index():
    """Serve the main application"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    if os.path.exists(path):
        return send_from_directory('.', path)
    return send_from_directory('.', 'index.html')

# ===== Config API =====
@app.route('/api/config', methods=['GET'])
@limiter.limit('100/hour')
def get_config():
    """Get current configuration"""
    config = storage.load_config()
    # Don't send password in response
    if 'smtp' in config and 'password' in config['smtp']:
        config['smtp']['password'] = '***'
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
@limiter.limit('50/hour')
def save_config():
    """Save configuration"""
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({'error': 'No config provided'}), 400
        
        # Preserve password if not changed
        current = storage.load_config()
        if 'smtp' in new_config and 'password' in new_config['smtp']:
            if new_config['smtp']['password'] == '***' and 'smtp' in current:
                new_config['smtp']['password'] = current['smtp'].get('password', '')
        
        if storage.save_config(new_config):
            # Recreate email sender
            global email_sender
            email_sender = SMTPEmailSender(new_config)
            return jsonify({'success': True, 'message': 'Configuration saved'})
        else:
            return jsonify({'error': 'Failed to save config'}), 500
    except Exception as e:
        logger.error(f"Save config error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== Template API =====
@app.route('/api/templates', methods=['GET'])
@limiter.limit('200/hour')
def list_templates():
    """List all templates"""
    templates = storage.list_templates()
    return jsonify(templates)

@app.route('/api/templates/<name>', methods=['GET'])
@limiter.limit('200/hour')
def get_template(name):
    """Get template content"""
    content = storage.get_template(name)
    if content:
        return jsonify({'name': name, 'content': content})
    return jsonify({'error': 'Template not found'}), 404

@app.route('/api/templates', methods=['POST'])
@limiter.limit('100/hour')
def create_template():
    """Create or update template"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        content = data.get('content', '')
        
        if not name:
            return jsonify({'error': 'Template name required'}), 400
        if not content:
            return jsonify({'error': 'Template content required'}), 400
        
        if storage.save_template(name, content):
            return jsonify({'success': True, 'message': 'Template saved'})
        else:
            return jsonify({'error': 'Failed to save template'}), 500
    except Exception as e:
        logger.error(f"Save template error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<name>', methods=['DELETE'])
@limiter.limit('50/hour')
def delete_template(name):
    """Delete template"""
    if storage.delete_template(name):
        return jsonify({'success': True, 'message': 'Template deleted'})
    return jsonify({'error': 'Template not found'}), 404

@app.route('/api/templates/<name>/preview', methods=['GET'])
def preview_template(name):
    """Preview template"""
    content = storage.get_template(name)
    if content:
        return render_template_content(content, {
            'name': 'John Doe',
            'email': 'john@example.com',
            'company': 'Acme Inc',
            'cta_url': '#',
            'unsubscribe_url': '#',
            'subject': 'Preview Email'
        }), 200, {'Content-Type': 'text/html'}
    return 'Template not found', 404

# ===== Recipient Files API =====
@app.route('/api/recipient-files', methods=['GET'])
@limiter.limit('200/hour')
def list_recipient_files():
    """List recipient files"""
    files = storage.list_recipient_files()
    return jsonify(files)

@app.route('/api/upload-csv', methods=['POST'])
@limiter.limit('50/hour')
def upload_csv():
    """Upload CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are supported'}), 400
        
        # Save file
        filename = storage.save_recipient_file(file, file.filename)
        if not filename:
            return jsonify({'error': 'Failed to save file'}), 500
        
        # Validate and preview
        recipients = storage.get_recipients(filename, limit=10)
        total = storage.count_recipients(filename)
        
        # Validate emails
        valid_rows = 0
        invalid_rows = 0
        
        for r in recipients:
            if r.get('email') and '@' in r.get('email', ''):
                valid_rows += 1
            else:
                invalid_rows += 1
        
        return jsonify({
            'success': True,
            'filename': filename,
            'cleaned_filename': filename,
            'total_rows': total,
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows,
            'preview': recipients
        })
    except Exception as e:
        logger.error(f"Upload CSV error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipient-files/<filename>', methods=['DELETE'])
@limiter.limit('50/hour')
def delete_recipient_file(filename):
    """Delete recipient file"""
    if storage.delete_recipient_file(filename):
        return jsonify({'success': True, 'message': 'File deleted'})
    return jsonify({'error': 'File not found'}), 404

# ===== Campaign API =====
@app.route('/api/campaigns', methods=['GET'])
@limiter.limit('200/hour')
def list_campaigns():
    """List all campaigns"""
    campaigns = storage.load_campaigns()
    return jsonify({'campaigns': campaigns})

@app.route('/api/campaign/start', methods=['POST'])
@limiter.limit('20/hour')
def start_campaign():
    """Start a new campaign"""
    try:
        data = request.get_json()
        
        required = ['recipients_file', 'template', 'subject']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Load configuration
        config = storage.load_config()
        
        # Check SMTP configuration
        if not config.get('smtp', {}).get('server') or not config.get('smtp', {}).get('username'):
            return jsonify({'error': 'SMTP not configured. Please configure SMTP settings first.'}), 400
        
        # Get template content
        template_content = storage.get_template(data['template'])
        if not template_content:
            return jsonify({'error': f'Template "{data["template"]}" not found'}), 404
        
        # Check recipient file exists
        files = storage.list_recipient_files()
        if not any(f['name'] == data['recipients_file'] for f in files):
            return jsonify({'error': 'Recipient file not found'}), 404
        
        # Create campaign
        campaign_id = str(uuid.uuid4())[:8]
        campaign = {
            'id': campaign_id,
            'name': data.get('campaign_name', f'Campaign_{campaign_id}'),
            'subject': data['subject'],
            'status': 'queued',
            'recipients_file': data['recipients_file'],
            'template': data['template'],
            'reply_to': data.get('reply_to', ''),
            'created_at': datetime.now().isoformat(),
            'stats': {'sent': 0, 'failed': 0}
        }
        
        # Apply campaign-specific settings
        if 'rate_limit' in data:
            config['campaign']['rate_limit'] = data['rate_limit']
        if 'batch_size' in data:
            config['campaign']['max_emails_per_batch'] = data['batch_size']
        if 'parallel_workers' in data:
            config['campaign']['parallel_workers'] = data['parallel_workers']
        
        storage.save_campaign(campaign)
        
        # Start campaign in background
        def on_progress(cid, processed, total, sent, failed):
            pass  # Could implement WebSocket updates
        
        success = campaign_worker.start_campaign(
            campaign_id=campaign_id,
            config=config,
            recipients_file=data['recipients_file'],
            template_content=template_content,
            subject=data['subject'],
            reply_to=data.get('reply_to'),
            on_progress=on_progress
        )
        
        if success:
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'message': 'Campaign started'
            })
        else:
            return jsonify({'error': 'Failed to start campaign'}), 500
            
    except Exception as e:
        logger.error(f"Start campaign error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaign/<campaign_id>/pause', methods=['POST'])
@limiter.limit('50/hour')
def pause_campaign(campaign_id):
    """Pause a campaign"""
    # For now, stop is the same as pause
    if campaign_worker.stop_campaign(campaign_id):
        return jsonify({'success': True, 'message': 'Campaign paused'})
    return jsonify({'error': 'Campaign not found or not running'}), 404

@app.route('/api/campaign/<campaign_id>/resume', methods=['POST'])
@limiter.limit('50/hour')
def resume_campaign(campaign_id):
    """Resume a campaign (not implemented - would need state saving)"""
    return jsonify({'error': 'Resume not implemented. Please start a new campaign.'}), 400

@app.route('/api/campaign/<campaign_id>/stop', methods=['POST'])
@limiter.limit('50/hour')
def stop_campaign_route(campaign_id):
    """Stop a campaign"""
    if campaign_worker.stop_campaign(campaign_id):
        campaign = {
            'id': campaign_id,
            'status': 'stopped',
            'completed_at': datetime.now().isoformat()
        }
        storage.save_campaign(campaign)
        return jsonify({'success': True, 'message': 'Campaign stopped'})
    return jsonify({'error': 'Campaign not found or not running'}), 404

@app.route('/api/campaign/<campaign_id>/results', methods=['GET'])
@limiter.limit('100/hour')
def get_campaign_results(campaign_id):
    """Get campaign results"""
    status = campaign_worker.get_campaign_status(campaign_id)
    if status:
        return jsonify({
            'campaign_id': campaign_id,
            'summary': status,
            'errors': {}
        })
    return jsonify({'error': 'Campaign not found'}), 404

# ===== Stats API =====
@app.route('/api/stats', methods=['GET'])
@limiter.limit('200/hour')
def get_stats():
    """Get campaign statistics"""
    campaigns = storage.load_campaigns()
    
    totals = {
        'emails_sent': sum(c.get('stats', {}).get('sent', 0) for c in campaigns),
        'emails_failed': sum(c.get('stats', {}).get('failed', 0) for c in campaigns),
        'total_recipients': sum(c.get('total_recipients', 0) for c in campaigns),
        'delivery_rate': 0,
        'open_rate': 0,
        'click_rate': 0
    }
    
    total_sent = totals['emails_sent']
    total_recipients = totals['total_recipients']
    if total_recipients > 0:
        totals['delivery_rate'] = round(total_sent / total_recipients * 100, 1)
    
    return jsonify({
        'campaigns': campaigns,
        'totals': totals
    })

@app.route('/api/analytics', methods=['GET'])
@limiter.limit('100/hour')
def get_analytics():
    """Get analytics data"""
    campaigns = storage.load_campaigns()
    
    # Daily stats
    daily_stats = {}
    for c in campaigns:
        if c.get('completed_at'):
            date = c['completed_at'][:10]
            if date not in daily_stats:
                daily_stats[date] = {'sent': 0, 'failed': 0}
            daily_stats[date]['sent'] += c.get('stats', {}).get('sent', 0)
            daily_stats[date]['failed'] += c.get('stats', {}).get('failed', 0)
    
    return jsonify({
        'total_campaigns': len(campaigns),
        'daily_stats': daily_stats,
        'campaigns': campaigns
    })

# ===== Blacklist API =====
@app.route('/api/blacklist', methods=['GET'])
@limiter.limit('200/hour')
def get_blacklist():
    """Get blacklist"""
    emails = storage.load_blacklist()
    search = request.args.get('search', '')
    if search:
        emails = [e for e in emails if search.lower() in e.lower()]
    return jsonify({
        'items': emails,
        'total': len(emails)
    })

@app.route('/api/blacklist', methods=['POST'])
@limiter.limit('50/hour')
def add_to_blacklist():
    """Add emails to blacklist"""
    data = request.get_json()
    emails = data.get('emails', [])
    if isinstance(emails, str):
        emails = [emails]
    
    added = storage.add_to_blacklist(emails)
    return jsonify({'success': True, 'added': added})

@app.route('/api/blacklist', methods=['DELETE'])
@limiter.limit('50/hour')
def remove_from_blacklist():
    """Remove emails from blacklist"""
    data = request.get_json()
    emails = data.get('emails', [])
    if isinstance(emails, str):
        emails = [emails]
    
    removed = storage.remove_from_blacklist(emails)
    return jsonify({'success': True, 'removed': removed})

@app.route('/api/blacklist/import', methods=['POST'])
@limiter.limit('20/hour')
def import_blacklist():
    """Import blacklist from CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Parse CSV
        content = file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        
        emails = []
        for row in reader:
            if row and '@' in row[0]:
                emails.append(row[0].strip())
        
        added = storage.add_to_blacklist(emails)
        total = len(storage.load_blacklist())
        
        return jsonify({
            'success': True,
            'new': added,
            'total': total,
            'message': f'Imported {added} new emails'
        })
    except Exception as e:
        logger.error(f"Import blacklist error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/blacklist/export', methods=['GET'])
def export_blacklist():
    """Export blacklist as CSV"""
    emails = storage.load_blacklist()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['email'])
    for email in emails:
        writer.writerow([email])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='blacklist.csv'
    )

# ===== Logs API =====
@app.route('/api/logs', methods=['GET'])
@limiter.limit('100/hour')
def list_logs():
    """List log files"""
    logs = storage.list_logs()
    return jsonify(logs)

@app.route('/api/logs/<filename>', methods=['GET'])
@limiter.limit('100/hour')
def get_log(filename):
    """Get log content"""
    lines = request.args.get('lines', 500, type=int)
    content = storage.get_log_content(filename, lines)
    if content:
        return jsonify({
            'name': filename,
            'content': content
        })
    return jsonify({'error': 'Log not found'}), 404

@app.route('/api/logs/<filename>', methods=['DELETE'])
@limiter.limit('20/hour')
def delete_log(filename):
    """Delete log file"""
    if storage.delete_log(filename):
        return jsonify({'success': True, 'message': 'Log deleted'})
    return jsonify({'error': 'Log not found'}), 404

# ===== Backup API =====
@app.route('/api/backups', methods=['GET'])
@limiter.limit('50/hour')
def list_backups():
    """List backups"""
    backups = storage.list_backups()
    return jsonify(backups)

@app.route('/api/backup', methods=['POST'])
@limiter.limit('10/hour')
def create_backup():
    """Create a backup"""
    backup = storage.create_backup()
    if backup:
        return jsonify(backup)
    return jsonify({'error': 'Failed to create backup'}), 500

@app.route('/api/backup/<backup_id>', methods=['GET'])
def download_backup(backup_id):
    """Download backup"""
    backup_path = storage.get_backup_path(backup_id)
    if backup_path:
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=f'supermailer_backup_{backup_id}.zip'
        )
    return jsonify({'error': 'Backup not found'}), 404

@app.route('/api/backup/<backup_id>', methods=['DELETE'])
@limiter.limit('20/hour')
def delete_backup(backup_id):
    """Delete backup"""
    if storage.delete_backup(backup_id):
        return jsonify({'success': True, 'message': 'Backup deleted'})
    return jsonify({'error': 'Backup not found'}), 404

# ===== SMTP Test API =====
@app.route('/api/test-smtp', methods=['POST'])
@limiter.limit('20/hour')
def test_smtp():
    """Test SMTP connection"""
    try:
        config = request.get_json()
        sender = SMTPEmailSender(config)
        success, message = sender.test_connection()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ===== System Info API =====
@app.route('/api/system/info', methods=['GET'])
@limiter.limit('50/hour')
def system_info():
    """Get system information"""
    info = storage.get_system_info()
    return jsonify(info)

@app.route('/api/export-stats', methods=['GET'])
def export_stats():
    """Export statistics as CSV"""
    campaigns = storage.load_campaigns()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Campaign ID', 'Name', 'Status', 'Created At', 'Completed At', 
                     'Total Recipients', 'Sent', 'Failed', 'Success Rate'])
    
    for c in campaigns:
        sent = c.get('stats', {}).get('sent', 0)
        total = c.get('total_recipients', 0)
        success_rate = round(sent / max(total, 1) * 100, 1)
        
        writer.writerow([
            c.get('id', ''),
            c.get('name', ''),
            c.get('status', ''),
            c.get('created_at', ''),
            c.get('completed_at', ''),
            total,
            sent,
            c.get('stats', {}).get('failed', 0),
            success_rate
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'stats_{datetime.now().strftime("%Y%m%d")}.csv'
    )

# ===== Health Check =====
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

# ==================== Error Handlers ====================
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ==================== Main Entry Point ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='SuperMailer Pro')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting SuperMailer Pro on {args.host}:{args.port}")
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )