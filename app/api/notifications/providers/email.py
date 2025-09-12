"""Email notification provider"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import asyncio

from .base import BaseProvider, NotificationMessage, SendResult, NotificationChannel

logger = logging.getLogger(__name__)


class EmailProvider(BaseProvider):
    """SMTP email notification provider"""
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate email configuration"""
        required = ['smtp_host', 'smtp_port', 'from_email']
        for field in required:
            if not self.config.get(field):
                return False, f"Email {field} is required"
        
        # Validate port
        port = self.config.get('smtp_port')
        if not isinstance(port, int) or port < 1 or port > 65535:
            return False, "Invalid SMTP port"
        
        # Validate email format (basic check)
        from_email = self.config.get('from_email')
        if '@' not in from_email:
            return False, "Invalid from_email format"
        
        return True, None
    
    async def send(self, message: NotificationMessage) -> SendResult:
        """Send email notification"""
        if not self.enabled:
            return SendResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error="Email notifications are disabled"
            )
        
        try:
            # Run SMTP operations in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._send_smtp,
                message
            )
            return result
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error=str(e)
            )
    
    def _send_smtp(self, message: NotificationMessage) -> SendResult:
        """Send email via SMTP (blocking)"""
        try:
            # Log configuration (without password)
            logger.info(f"Email config: host={self.config.get('smtp_host')}, port={self.config.get('smtp_port')}, "
                       f"user={self.config.get('smtp_user')}, from={self.config.get('from_email')}, "
                       f"to={self.config.get('to_emails')}, use_tls={self.config.get('use_tls')}, "
                       f"use_ssl={self.config.get('use_ssl')}")
            
            # Create message
            msg = self.format_message(message)
            
            # Determine TLS mode
            use_tls = self.config.get('use_tls', True)
            use_ssl = self.config.get('use_ssl', False)
            
            logger.info(f"Connecting to SMTP server {self.config['smtp_host']}:{self.config['smtp_port']} "
                       f"(SSL={use_ssl}, TLS={use_tls})")
            
            # Connect to SMTP server
            if use_ssl:
                server = smtplib.SMTP_SSL(
                    self.config['smtp_host'],
                    self.config['smtp_port'],
                    timeout=30
                )
            else:
                server = smtplib.SMTP(
                    self.config['smtp_host'],
                    self.config['smtp_port'],
                    timeout=30
                )
                if use_tls:
                    logger.info("Starting TLS...")
                    server.starttls()
            
            # Authenticate if credentials provided
            if self.config.get('smtp_user') and self.config.get('smtp_pass'):
                logger.info(f"Authenticating as {self.config['smtp_user']}...")
                server.login(self.config['smtp_user'], self.config['smtp_pass'])
                logger.info("Authentication successful")
            else:
                logger.warning("No SMTP credentials provided, skipping authentication")
            
            # Send email
            to_emails = self.config.get('to_emails', [])
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            if not to_emails:
                return SendResult(
                    success=False,
                    channel=NotificationChannel.EMAIL,
                    error="No recipient email addresses configured"
                )
            
            logger.info(f"Sending email to {to_emails}...")
            server.send_message(msg)
            server.quit()
            logger.info("Email sent successfully")
            
            return SendResult(
                success=True,
                channel=NotificationChannel.EMAIL
            )
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error="SMTP authentication failed"
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error=f"SMTP error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return SendResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error=str(e)
            )
    
    def format_message(self, message: NotificationMessage) -> MIMEMultipart:
        """Format message as email"""
        msg = MIMEMultipart('alternative')
        
        # Set headers
        msg['Subject'] = message.title or f"StreamOps: {message.event_type.replace('.', ' ').title()}"
        msg['From'] = self.config['from_email']
        
        to_emails = self.config.get('to_emails', [])
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        msg['To'] = ', '.join(to_emails)
        
        # Create email body
        text_content = message.content
        
        # Add metadata to body if present
        if message.metadata:
            text_content += "\n\n--- Details ---\n"
            for key, value in message.metadata.items():
                if value is not None:
                    text_content += f"{key.replace('_', ' ').title()}: {value}\n"
        
        # Create HTML version
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>{msg['Subject']}</h2>
                <p>{message.content.replace(chr(10), '<br>')}</p>
        """
        
        if message.metadata:
            html_content += """
                <hr>
                <h3>Details</h3>
                <table style="border-collapse: collapse;">
            """
            for key, value in message.metadata.items():
                if value is not None:
                    html_content += f"""
                    <tr>
                        <td style="padding: 5px; font-weight: bold;">{key.replace('_', ' ').title()}:</td>
                        <td style="padding: 5px;">{value}</td>
                    </tr>
                    """
            html_content += "</table>"
        
        html_content += """
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Sent by StreamOps Notification System
                </p>
            </body>
        </html>
        """
        
        # Attach parts
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        return msg