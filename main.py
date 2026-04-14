# main.py - Production MailerX Pro with Template Attachments
"""
MailerX Pro - Enterprise Email Marketing System with Template Attachments
"""

import os
import sys
import smtplib
import json
import uuid
import secrets
import threading
import time
import csv
import io
import re
import platform
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
import logging

# Core web framework
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

# Email handling
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, utils

# ==================== Configuration ====================
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))
    
    # Resource path helper for PyInstaller / PyWebView
    @staticmethod
    def resource_path(relative_path):
        """Get absolute path to resource, works both in development and when bundled as .exe"""
        if hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle
            return os.path.join(sys._MEIPASS, relative_path)
        # Running normally (python main.py or desktop_app.py)
        return os.path.join(os.path.abspath("."), relative_path)

    # All paths now use resource_path
    DATABASE_PATH = resource_path('data/MailerX.db')
    CONFIG_PATH = resource_path('data/config.json')
    TEMPLATES_PATH = resource_path('data/templates')
    ATTACHMENTS_PATH = resource_path('data/attachments')
    LOGS_PATH = resource_path('data/logs')
    BACKUPS_PATH = resource_path('data/backups')
    UPLOADS_PATH = resource_path('data/uploads')
    
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload
    ALLOWED_ATTACHMENT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.zip', '.txt'}
    
# Create directories
for path in [Config.TEMPLATES_PATH, Config.ATTACHMENTS_PATH, Config.LOGS_PATH, 
             Config.BACKUPS_PATH, Config.UPLOADS_PATH]:
    os.makedirs(path, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
CORS(app)

# ==================== Storage Manager ====================
class StorageManager:
    def __init__(self):
        self.templates_dir = Config.TEMPLATES_PATH
        self.attachments_dir = Config.ATTACHMENTS_PATH
        self.uploads_dir = Config.UPLOADS_PATH
        self.db_file = Config.DATABASE_PATH
        self.config_file = Config.CONFIG_PATH
        
    # ===== Template Management with Attachments =====
    def list_templates(self) -> List[dict]:
        """List all templates with their attachments"""
        templates = []
        try:
            for file in os.listdir(self.templates_dir):
                if file.endswith('.html'):
                    file_path = os.path.join(self.templates_dir, file)
                    stat = os.stat(file_path)
                    template_name = file.replace('.html', '')
                    
                    # Get attachments for this template
                    attachments = self.get_template_attachments(template_name)
                    
                    templates.append({
                        'name': template_name,
                        'filename': file,
                        'size_kb': round(stat.st_size / 1024, 1),
                        'modified': stat.st_mtime,
                        'attachments': attachments,
                        'attachment_count': len(attachments)
                    })
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
        return sorted(templates, key=lambda x: x['modified'], reverse=True)
    
    def get_template_attachments(self, template_name: str) -> List[dict]:
        """Get attachments for a specific template"""
        attachments = []
        template_attach_dir = os.path.join(self.attachments_dir, secure_filename(template_name))
        
        if os.path.exists(template_attach_dir):
            for file in os.listdir(template_attach_dir):
                file_path = os.path.join(template_attach_dir, file)
                stat = os.stat(file_path)
                
                # Detect file type
                mime_type, _ = mimetypes.guess_type(file)
                file_type = 'image' if mime_type and mime_type.startswith('image/') else 'document'
                
                attachments.append({
                    'filename': file,
                    'size_kb': round(stat.st_size / 1024, 1),
                    'size_bytes': stat.st_size,
                    'type': file_type,
                    'mime_type': mime_type or 'application/octet-stream',
                    'modified': stat.st_mtime
                })
        return attachments
    
    def save_template_attachment(self, template_name: str, file: FileStorage) -> Optional[str]:
        """Save an attachment for a template"""
        try:
            safe_name = secure_filename(template_name)
            filename = secure_filename(file.filename)
            
            if not filename:
                return None
            
            # Check extension
            ext = os.path.splitext(filename)[1].lower()
            if ext not in Config.ALLOWED_ATTACHMENT_EXTENSIONS:
                logger.warning(f"Blocked attachment type: {ext}")
                return None
            
            # Create template attachment directory
            template_attach_dir = os.path.join(self.attachments_dir, safe_name)
            os.makedirs(template_attach_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(template_attach_dir, filename)
            file.save(file_path)
            
            logger.info(f"Saved attachment {filename} for template {template_name}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to save attachment: {e}")
            return None
    
    def delete_template_attachment(self, template_name: str, filename: str) -> bool:
        """Delete an attachment from a template"""
        try:
            safe_name = secure_filename(template_name)
            safe_filename = secure_filename(filename)
            file_path = os.path.join(self.attachments_dir, safe_name, safe_filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted attachment {filename} from template {template_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete attachment: {e}")
        return False
    
    def get_template(self, name: str) -> Optional[str]:
        """Get template content"""
        try:
            safe_name = secure_filename(name)
            file_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to get template {name}: {e}")
        return None
    
    def save_template(self, name: str, content: str) -> bool:
        """Save template with metadata"""
        try:
            safe_name = secure_filename(name)
            if not safe_name:
                return False
            
            # Save template content
            file_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Save template metadata
            metadata = {
                'name': name,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'has_attachments': os.path.exists(os.path.join(self.attachments_dir, safe_name))
            }
            
            meta_path = os.path.join(self.templates_dir, f"{safe_name}.meta.json")
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save template {name}: {e}")
            return False
    
    def delete_template(self, name: str) -> bool:
        """Delete template and its attachments"""
        try:
            safe_name = secure_filename(name)
            
            # Delete template file
            template_path = os.path.join(self.templates_dir, f"{safe_name}.html")
            if os.path.exists(template_path):
                os.remove(template_path)
            
            # Delete metadata
            meta_path = os.path.join(self.templates_dir, f"{safe_name}.meta.json")
            if os.path.exists(meta_path):
                os.remove(meta_path)
            
            # Delete attachments directory
            attach_dir = os.path.join(self.attachments_dir, safe_name)
            if os.path.exists(attach_dir):
                import shutil
                shutil.rmtree(attach_dir)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete template {name}: {e}")
            return False
    
    # ===== Other Storage Methods =====
    def load_config(self) -> dict:
        """Load configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        return {
            'smtp': {'server': '', 'port': 587, 'username': '', 'password': '', 'use_tls': True},
            'email': {'from_email': '', 'from_name': 'MailerX Pro', 'reply_to': ''},
            'campaign': {'rate_limit': 5, 'max_emails_per_batch': 50, 'parallel_workers': 3}
        }
    
    def save_config(self, config: dict) -> bool:
        """Save configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def list_recipient_files(self) -> List[dict]:
        """List uploaded recipient files"""
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
                        with open(file_path, 'r', encoding='utf-8') as f:
                            row_count = sum(1 for _ in f) - 1
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
            file_path = os.path.join(self.uploads_dir, secure_filename(filename))
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete recipient file: {e}")
        return False
    
    def get_recipients(self, filename: str, limit: int = 10000) -> List[dict]:
        """Get recipients from CSV"""
        recipients = []
        try:
            file_path = os.path.join(self.uploads_dir, secure_filename(filename))
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if i >= limit:
                            break
                        if row.get('email'):
                            recipients.append(row)
        except Exception as e:
            logger.error(f"Failed to get recipients: {e}")
        return recipients
    
    def count_recipients(self, filename: str) -> int:
        """Count total recipients"""
        try:
            file_path = os.path.join(self.uploads_dir, secure_filename(filename))
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return sum(1 for _ in f) - 1
        except Exception as e:
            logger.error(f"Failed to count recipients: {e}")
        return 0
    
    def load_campaigns(self) -> List[dict]:
        """Load all campaigns"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    return data.get('campaigns', [])
        except Exception as e:
            logger.error(f"Failed to load campaigns: {e}")
        return []
    
    def save_campaign(self, campaign: dict) -> bool:
        """Save campaign"""
        try:
            campaigns = self.load_campaigns()
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
    
    def load_blacklist(self) -> List[str]:
        """Load blacklist"""
        blacklist_file = os.path.join(os.path.dirname(self.db_file), 'blacklist.json')
        try:
            if os.path.exists(blacklist_file):
                with open(blacklist_file, 'r') as f:
                    data = json.load(f)
                    return data.get('emails', [])
        except Exception as e:
            logger.error(f"Failed to load blacklist: {e}")
        return []
    
    def save_blacklist(self, emails: List[str]) -> bool:
        """Save blacklist"""
        blacklist_file = os.path.join(os.path.dirname(self.db_file), 'blacklist.json')
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
    
    def list_logs(self) -> List[dict]:
        """List log files"""
        logs = []
        try:
            if os.path.exists(Config.LOGS_PATH):
                for file in os.listdir(Config.LOGS_PATH):
                    if file.endswith('.log'):
                        file_path = os.path.join(Config.LOGS_PATH, file)
                        stat = os.stat(file_path)
                        logs.append({
                            'name': file,
                            'size_kb': round(stat.st_size / 1024, 1),
                            'modified': stat.st_mtime
                        })
        except Exception as e:
            logger.error(f"Failed to list logs: {e}")
        return sorted(logs, key=lambda x: x['modified'], reverse=True)
    
    def list_backups(self) -> List[dict]:
        """List backups"""
        backups = []
        try:
            if os.path.exists(Config.BACKUPS_PATH):
                for file in os.listdir(Config.BACKUPS_PATH):
                    if file.endswith('.zip'):
                        file_path = os.path.join(Config.BACKUPS_PATH, file)
                        stat = os.stat(file_path)
                        backups.append({
                            'id': file.replace('.zip', ''),
                            'size_mb': round(stat.st_size / (1024 * 1024), 2),
                            'created': stat.st_mtime
                        })
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def create_backup(self) -> Optional[dict]:
        """Create backup"""
        import zipfile
        try:
            backup_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(Config.BACKUPS_PATH, f"{backup_id}.zip")
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for dir_path, dirs, files in os.walk(Config.TEMPLATES_PATH):
                    for file in files:
                        file_path = os.path.join(dir_path, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(Config.TEMPLATES_PATH))
                        zipf.write(file_path, arcname)
                
                if os.path.exists(self.config_file):
                    zipf.write(self.config_file, 'config.json')
                if os.path.exists(self.db_file):
                    zipf.write(self.db_file, 'database.json')
            
            stat = os.stat(backup_path)
            return {'id': backup_id, 'size_mb': round(stat.st_size / (1024 * 1024), 2)}
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete backup"""
        try:
            file_path = os.path.join(Config.BACKUPS_PATH, f"{secure_filename(backup_id)}.zip")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
        return False
    
    def get_backup_path(self, backup_id: str) -> Optional[str]:
        """Get backup path"""
        try:
            file_path = os.path.join(Config.BACKUPS_PATH, f"{secure_filename(backup_id)}.zip")
            return file_path if os.path.exists(file_path) else None
        except Exception as e:
            logger.error(f"Failed to get backup path: {e}")
            return None

# ==================== SMTP Email Sender with Attachments ====================
class SMTPEmailSender:
    def __init__(self, config: dict):
        self.config = config
    
    def send_email_with_attachments(self, to_email: str, subject: str, html_content: str,
                                     attachments: List[dict] = None, reply_to: str = None) -> Tuple[bool, str]:
        """Send email with attachments"""
        try:
            smtp_config = self.config.get('smtp', {})
            email_config = self.config.get('email', {})
            
            if not smtp_config.get('server') or not smtp_config.get('username'):
                return False, "SMTP not configured"
            
            # Create message
            from_email_addr = email_config.get('from_email') or smtp_config.get('username')
            from_name_str = email_config.get('from_name', 'MailerX Pro')
            
            msg = MIMEMultipart('mixed') if attachments else MIMEMultipart('alternative')
            msg['From'] = f"{from_name_str} <{from_email_addr}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Message-ID'] = f"<{uuid.uuid4()}@{from_email_addr.split('@')[-1]}>"
            msg['Date'] = utils.formatdate(localtime=True)
            
            if reply_to:
                msg['Reply-To'] = reply_to
            elif email_config.get('reply_to'):
                msg['Reply-To'] = email_config['reply_to']
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Attach files
            if attachments:
                for attach in attachments:
                    if attach.get('file_path') and os.path.exists(attach['file_path']):
                        with open(attach['file_path'], 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename="{attach.get("filename", "attachment")}"'
                            )
                            msg.attach(part)
            
            # Connect and send
            if smtp_config.get('use_ssl'):
                server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config.get('port', 465), timeout=30)
            else:
                server = smtplib.SMTP(smtp_config['server'], smtp_config.get('port', 587), timeout=30)
                if smtp_config.get('use_tls', True):
                    server.starttls()
            
            server.login(smtp_config['username'], smtp_config.get('password', ''))
            server.send_message(msg)
            server.quit()
            
            return True, "Sent successfully"
            
        except smtplib.SMTPAuthenticationError:
            return False, "SMTP authentication failed"
        except Exception as e:
            return False, str(e)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test SMTP connection"""
        try:
            smtp_config = self.config.get('smtp', {})
            if not smtp_config.get('server') or not smtp_config.get('username'):
                return False, "SMTP not configured"
            
            if smtp_config.get('use_ssl'):
                server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config.get('port', 465), timeout=10)
            else:
                server = smtplib.SMTP(smtp_config['server'], smtp_config.get('port', 587), timeout=10)
                if smtp_config.get('use_tls', True):
                    server.starttls()
            
            server.login(smtp_config['username'], smtp_config.get('password', ''))
            server.quit()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

# ==================== Template Renderer ====================
def render_template_content(template_content: str, context: dict) -> str:
    """Render template with context"""
    content = template_content
    
    # Replace variables
    for key, value in context.items():
        if value is not None:
            content = content.replace(f'{{{{{key}}}}}', str(value))
    
    # Handle conditional blocks
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
    def __init__(self):
        self.active_campaigns = {}
        self._lock = threading.Lock()
    
    def start_campaign(self, campaign_id: str, config: dict, recipients_file: str,
                       template_content: str, subject: str, reply_to: str = None,
                       attachments: List[dict] = None) -> bool:
        """Start campaign with attachments"""
        with self._lock:
            if campaign_id in self.active_campaigns:
                return False
        
        def run():
            try:
                self._run_campaign(campaign_id, config, recipients_file, template_content,
                                  subject, reply_to, attachments)
            finally:
                with self._lock:
                    if campaign_id in self.active_campaigns:
                        del self.active_campaigns[campaign_id]
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        
        with self._lock:
            self.active_campaigns[campaign_id] = {'thread': thread, 'status': 'running'}
        
        return True
    
    def _run_campaign(self, campaign_id: str, config: dict, recipients_file: str,
                      template_content: str, subject: str, reply_to: str = None,
                      attachments: List[dict] = None):
        """Run campaign"""
        try:
            storage = StorageManager()
            recipients = storage.get_recipients(recipients_file)
            blacklist = set(storage.load_blacklist())
            
            # Filter recipients
            valid_recipients = [r for r in recipients if r.get('email', '').lower() not in blacklist]
            total = len(valid_recipients)
            sent = 0
            failed = 0
            
            # Update campaign
            campaign = {
                'id': campaign_id,
                'status': 'running',
                'started_at': datetime.now().isoformat(),
                'total_recipients': total,
                'stats': {'sent': 0, 'failed': 0}
            }
            storage.save_campaign(campaign)
            
            # Create sender
            sender = SMTPEmailSender(config)
            campaign_config = config.get('campaign', {})
            rate_limit = campaign_config.get('rate_limit', 5)
            batch_delay = 1.0 / rate_limit if rate_limit > 0 else 0
            
            for i, recipient in enumerate(valid_recipients):
                # Check if stopped
                with self._lock:
                    if campaign_id not in self.active_campaigns or self.active_campaigns[campaign_id].get('status') == 'stopped':
                        break
                
                # Personalize
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
                
                # Send
                success, message = sender.send_email_with_attachments(
                    to_email=recipient['email'],
                    subject=personalized_subject,
                    html_content=personalized_html,
                    attachments=attachments,
                    reply_to=reply_to
                )
                
                if success:
                    sent += 1
                else:
                    failed += 1
                    logger.error(f"Failed to send to {recipient['email']}: {message}")
                
                # Update progress
                if (i + 1) % 10 == 0:
                    campaigns = storage.load_campaigns()
                    for c in campaigns:
                        if c.get('id') == campaign_id:
                            c['stats']['sent'] = sent
                            c['stats']['failed'] = failed
                            storage.save_campaign(c)
                            break
                
                if batch_delay > 0:
                    time.sleep(batch_delay)
            
            # Final update
            campaign['status'] = 'completed' if sent > 0 else 'failed'
            campaign['completed_at'] = datetime.now().isoformat()
            campaign['stats'] = {'sent': sent, 'failed': failed}
            storage.save_campaign(campaign)
            
            # Create log
            log_content = f"""Campaign: {campaign_id}
Started: {campaign.get('started_at')}
Completed: {campaign.get('completed_at')}
Status: {campaign['status']}
Total: {total}
Sent: {sent}
Failed: {failed}
Success Rate: {round(sent/max(total,1)*100, 1)}%
"""
            log_file = os.path.join(Config.LOGS_PATH, f"campaign_{campaign_id}.log")
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(log_content)
                
        except Exception as e:
            logger.error(f"Campaign {campaign_id} failed: {e}")
    
    def stop_campaign(self, campaign_id: str) -> bool:
        """Stop campaign"""
        with self._lock:
            if campaign_id in self.active_campaigns:
                self.active_campaigns[campaign_id]['status'] = 'stopped'
                return True
        return False
    
    def get_campaign_status(self, campaign_id: str) -> Optional[dict]:
        """Get campaign status"""
        storage = StorageManager()
        campaigns = storage.load_campaigns()
        for c in campaigns:
            if c.get('id') == campaign_id:
                return c
        return None

# ==================== API Endpoints ====================

@app.route('/')
def index():
    """Serve main application"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    if os.path.exists(path):
        return send_from_directory('.', path)
    return send_from_directory('.', 'index.html')

# ===== Template API with Attachments =====
@app.route('/api/templates', methods=['GET'])
def list_templates():
    """List all templates"""
    storage = StorageManager()
    templates = storage.list_templates()
    return jsonify(templates)

@app.route('/api/templates/<name>', methods=['GET'])
def get_template(name):
    """Get template content"""
    storage = StorageManager()
    content = storage.get_template(name)
    if content:
        return jsonify({'name': name, 'content': content})
    return jsonify({'error': 'Template not found'}), 404

@app.route('/api/templates', methods=['POST'])
def save_template():
    """Save template"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        content = data.get('content', '')
        
        if not name:
            return jsonify({'error': 'Template name required'}), 400
        
        storage = StorageManager()
        if storage.save_template(name, content):
            return jsonify({'success': True, 'message': 'Template saved'})
        return jsonify({'error': 'Failed to save template'}), 500
    except Exception as e:
        logger.error(f"Save template error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<name>', methods=['DELETE'])
def delete_template(name):
    """Delete template"""
    storage = StorageManager()
    if storage.delete_template(name):
        return jsonify({'success': True, 'message': 'Template deleted'})
    return jsonify({'error': 'Template not found'}), 404

# ===== Template Attachments API =====
@app.route('/api/templates/<name>/attachments', methods=['GET'])
def get_template_attachments(name):
    """Get template attachments"""
    storage = StorageManager()
    attachments = storage.get_template_attachments(name)
    return jsonify(attachments)

@app.route('/api/templates/<name>/attachments', methods=['POST'])
def upload_template_attachment(name):
    """Upload attachment to template"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        storage = StorageManager()
        filename = storage.save_template_attachment(name, file)
        
        if filename:
            return jsonify({
                'success': True,
                'filename': filename,
                'message': 'Attachment uploaded'
            })
        return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        logger.error(f"Upload attachment error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<name>/attachments/<filename>', methods=['DELETE'])
def delete_template_attachment(name, filename):
    """Delete template attachment"""
    storage = StorageManager()
    if storage.delete_template_attachment(name, filename):
        return jsonify({'success': True, 'message': 'Attachment deleted'})
    return jsonify({'error': 'Attachment not found'}), 404

@app.route('/api/templates/<name>/attachments/<filename>', methods=['GET'])
def download_template_attachment(name, filename):
    """Download template attachment"""
    storage = StorageManager()
    attach_dir = os.path.join(Config.ATTACHMENTS_PATH, secure_filename(name))
    file_path = os.path.join(attach_dir, secure_filename(filename))
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/templates/<name>/preview', methods=['GET'])
def preview_template(name):
    """Preview template with attachments"""
    storage = StorageManager()
    content = storage.get_template(name)
    if content:
        # Create preview context
        context = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'company': 'Acme Inc',
            'cta_url': '#',
            'unsubscribe_url': '#',
            'subject': 'Preview Email'
        }
        
        # Add attachment URLs to context
        attachments = storage.get_template_attachments(name)
        if attachments:
            context['attachments'] = attachments
            context['has_attachments'] = True
        
        rendered = render_template_content(content, context)
        return rendered, 200, {'Content-Type': 'text/html'}
    return 'Template not found', 404

# ===== Recipient Files API =====
@app.route('/api/recipient-files', methods=['GET'])
def list_recipient_files():
    """List recipient files"""
    storage = StorageManager()
    files = storage.list_recipient_files()
    return jsonify(files)

@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    """Upload CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        storage = StorageManager()
        filename = storage.save_recipient_file(file, file.filename)
        
        if not filename:
            return jsonify({'error': 'Failed to save file'}), 500
        
        total = storage.count_recipients(filename)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'cleaned_filename': filename,
            'total_rows': total,
            'valid_rows': total,
            'invalid_rows': 0
        })
    except Exception as e:
        logger.error(f"Upload CSV error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipient-files/<filename>', methods=['DELETE'])
def delete_recipient_file(filename):
    """Delete recipient file"""
    storage = StorageManager()
    if storage.delete_recipient_file(filename):
        return jsonify({'success': True, 'message': 'File deleted'})
    return jsonify({'error': 'File not found'}), 404

# ===== Campaign API =====
@app.route('/api/campaigns', methods=['GET'])
def list_campaigns():
    """List campaigns"""
    storage = StorageManager()
    campaigns = storage.load_campaigns()
    return jsonify({'campaigns': campaigns})

@app.route('/api/campaign/start', methods=['POST'])
def start_campaign():
    """Start campaign with attachments"""
    try:
        data = request.get_json()
        
        required = ['recipients_file', 'template', 'subject']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        storage = StorageManager()
        config = storage.load_config()
        
        # Check SMTP
        if not config.get('smtp', {}).get('server'):
            return jsonify({'error': 'SMTP not configured'}), 400
        
        # Get template and attachments
        template_content = storage.get_template(data['template'])
        if not template_content:
            return jsonify({'error': 'Template not found'}), 404
        
        attachments = storage.get_template_attachments(data['template'])
        
        # Prepare attachment paths
        attachment_paths = []
        for attach in attachments:
            attach_dir = os.path.join(Config.ATTACHMENTS_PATH, secure_filename(data['template']))
            file_path = os.path.join(attach_dir, attach['filename'])
            if os.path.exists(file_path):
                attachment_paths.append({
                    'filename': attach['filename'],
                    'file_path': file_path,
                    'mime_type': attach.get('mime_type', 'application/octet-stream')
                })
        
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
            'has_attachments': len(attachment_paths) > 0,
            'attachment_count': len(attachment_paths),
            'created_at': datetime.now().isoformat(),
            'stats': {'sent': 0, 'failed': 0}
        }
        
        storage.save_campaign(campaign)
        
        # Start campaign
        worker = CampaignWorker()
        success = worker.start_campaign(
            campaign_id=campaign_id,
            config=config,
            recipients_file=data['recipients_file'],
            template_content=template_content,
            subject=data['subject'],
            reply_to=data.get('reply_to'),
            attachments=attachment_paths if attachment_paths else None
        )
        
        if success:
            return jsonify({'success': True, 'campaign_id': campaign_id})
        return jsonify({'error': 'Failed to start campaign'}), 500
        
    except Exception as e:
        logger.error(f"Start campaign error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaign/<campaign_id>/stop', methods=['POST'])
def stop_campaign(campaign_id):
    """Stop campaign"""
    worker = CampaignWorker()
    if worker.stop_campaign(campaign_id):
        return jsonify({'success': True, 'message': 'Campaign stopped'})
    return jsonify({'error': 'Campaign not found'}), 404

@app.route('/api/campaign/<campaign_id>/results', methods=['GET'])
def get_campaign_results(campaign_id):
    """Get campaign results"""
    worker = CampaignWorker()
    result = worker.get_campaign_status(campaign_id)
    if result:
        return jsonify({'campaign_id': campaign_id, 'summary': result})
    return jsonify({'error': 'Campaign not found'}), 404

# ===== Stats API =====
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    storage = StorageManager()
    campaigns = storage.load_campaigns()
    
    totals = {
        'emails_sent': sum(c.get('stats', {}).get('sent', 0) for c in campaigns),
        'emails_failed': sum(c.get('stats', {}).get('failed', 0) for c in campaigns),
        'total_recipients': sum(c.get('total_recipients', 0) for c in campaigns),
        'delivery_rate': 0
    }
    
    if totals['total_recipients'] > 0:
        totals['delivery_rate'] = round(totals['emails_sent'] / totals['total_recipients'] * 100, 1)
    
    return jsonify({'campaigns': campaigns, 'totals': totals})

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get analytics"""
    storage = StorageManager()
    campaigns = storage.load_campaigns()
    
    daily_stats = {}
    for c in campaigns:
        if c.get('completed_at'):
            date = c['completed_at'][:10]
            if date not in daily_stats:
                daily_stats[date] = {'sent': 0, 'failed': 0}
            daily_stats[date]['sent'] += c.get('stats', {}).get('sent', 0)
            daily_stats[date]['failed'] += c.get('stats', {}).get('failed', 0)
    
    return jsonify({'total_campaigns': len(campaigns), 'daily_stats': daily_stats, 'campaigns': campaigns})

# ===== Blacklist API =====
@app.route('/api/blacklist', methods=['GET'])
def get_blacklist():
    """Get blacklist"""
    storage = StorageManager()
    emails = storage.load_blacklist()
    return jsonify({'items': emails, 'total': len(emails)})

@app.route('/api/blacklist', methods=['POST'])
def add_to_blacklist():
    """Add to blacklist"""
    data = request.get_json()
    emails = data.get('emails', [])
    storage = StorageManager()
    added = storage.add_to_blacklist(emails)
    return jsonify({'success': True, 'added': added})

@app.route('/api/blacklist', methods=['DELETE'])
def remove_from_blacklist():
    """Remove from blacklist"""
    data = request.get_json()
    emails = data.get('emails', [])
    storage = StorageManager()
    removed = storage.remove_from_blacklist(emails)
    return jsonify({'success': True, 'removed': removed})

@app.route('/api/blacklist/import', methods=['POST'])
def import_blacklist():
    """Import blacklist CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        
        file = request.files['file']
        content = file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        
        emails = []
        for row in reader:
            if row and '@' in row[0]:
                emails.append(row[0].strip())
        
        storage = StorageManager()
        added = storage.add_to_blacklist(emails)
        
        return jsonify({'success': True, 'new': added, 'total': len(storage.load_blacklist())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blacklist/export', methods=['GET'])
def export_blacklist():
    """Export blacklist"""
    storage = StorageManager()
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
def list_logs():
    """List logs"""
    storage = StorageManager()
    logs = storage.list_logs()
    return jsonify(logs)

@app.route('/api/logs/<filename>', methods=['GET'])
def get_log(filename):
    """Get log content"""
    log_path = os.path.join(Config.LOGS_PATH, secure_filename(filename))
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'name': filename, 'content': content})
    return jsonify({'error': 'Log not found'}), 404

# ===== Backup API =====
@app.route('/api/backups', methods=['GET'])
def list_backups():
    """List backups"""
    storage = StorageManager()
    backups = storage.list_backups()
    return jsonify(backups)

@app.route('/api/backup', methods=['POST'])
def create_backup():
    """Create backup"""
    storage = StorageManager()
    backup = storage.create_backup()
    if backup:
        return jsonify(backup)
    return jsonify({'error': 'Backup failed'}), 500

@app.route('/api/backup/<backup_id>', methods=['GET'])
def download_backup(backup_id):
    """Download backup"""
    storage = StorageManager()
    backup_path = storage.get_backup_path(backup_id)
    if backup_path:
        return send_file(backup_path, as_attachment=True, download_name=f'backup_{backup_id}.zip')
    return jsonify({'error': 'Backup not found'}), 404

@app.route('/api/backup/<backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    """Delete backup"""
    storage = StorageManager()
    if storage.delete_backup(backup_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Backup not found'}), 404

# ===== Config API =====
@app.route('/api/config', methods=['GET'])
def get_config():
    """Get config"""
    storage = StorageManager()
    config = storage.load_config()
    # Hide password
    if 'smtp' in config and 'password' in config['smtp'] and config['smtp']['password']:
        config['smtp']['password'] = '***'
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def save_config():
    """Save config"""
    try:
        new_config = request.get_json()
        storage = StorageManager()
        
        # Preserve password if unchanged
        current = storage.load_config()
        if 'smtp' in new_config and 'password' in new_config['smtp']:
            if new_config['smtp']['password'] == '***' and 'smtp' in current:
                new_config['smtp']['password'] = current['smtp'].get('password', '')
        
        if storage.save_config(new_config):
            return jsonify({'success': True, 'message': 'Configuration saved'})
        return jsonify({'error': 'Save failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-smtp', methods=['POST'])
def test_smtp():
    """Test SMTP"""
    try:
        config = request.get_json()
        sender = SMTPEmailSender(config)
        success, message = sender.test_connection()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ===== Health Check =====
@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    
    logger.info(f"Starting MailerX Pro on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)

# Optional: Increase limits for form data
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)