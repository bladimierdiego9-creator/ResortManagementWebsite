"""Email utilities for sending password reset and other system emails."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
from typing import Optional


def send_email(to: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """
    Send an email using SMTP configuration from app config.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        html_body: HTML version of email body
        text_body: Plain text version of email body (optional)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get SMTP settings from config
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_port = current_app.config.get('MAIL_PORT')
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
        mail_default_sender = current_app.config.get('MAIL_DEFAULT_SENDER') or mail_username
        
        # Validate config
        if not all([mail_server, mail_port, mail_username, mail_password]):
            current_app.logger.error('SMTP configuration incomplete')
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mail_default_sender
        msg['To'] = to
        
        # Attach text and HTML parts
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(html_body, 'html')
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(mail_server, mail_port) as server:
            server.set_debuglevel(0)  # Set to 1 for debugging
            if mail_use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_default_sender, to, msg.as_string())
        
        current_app.logger.info(f'Email sent successfully to {to}')
        return True
        
    except Exception as e:
        current_app.logger.error(f'Failed to send email to {to}: {str(e)}')
        return False


def send_password_reset_email(user_email: str, reset_token: str) -> bool:
    """
    Send a password reset email with a reset link.
    
    Args:
        user_email: Email address of the user requesting password reset
        reset_token: Token to include in the reset URL
    
    Returns:
        True if email sent successfully, False otherwise
    """
    from flask import url_for
    
    # Generate reset URL
    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
    
    # HTML email body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 8px;
                padding: 30px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #4edea3;
                margin: 0;
            }}
            .content {{
                background-color: white;
                padding: 30px;
                border-radius: 6px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #4edea3;
                color: white !important;
                text-decoration: none;
                border-radius: 6px;
                margin: 20px 0;
                font-weight: 500;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 12px;
                color: #666;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffb95f;
                padding: 12px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>A&D Thysia Resort</h1>
            </div>
            <div class="content">
                <h2>Password Reset Request</h2>
                <p>You have requested to reset your password for your A&D Thysia admin account.</p>
                <p>Click the button below to reset your password:</p>
                <div style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666; font-size: 14px;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>This link will expire in 1 hour</li>
                        <li>If you didn't request this reset, please ignore this email</li>
                        <li>Never share this link with anyone</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>© 2026 A&D Thysia Resort. All rights reserved.</p>
                <p>This is an automated email. Please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_body = f"""
    A&D Thysia Resort - Password Reset Request
    
    You have requested to reset your password for your A&D Thysia admin account.
    
    Click the link below to reset your password:
    {reset_url}
    
    Security Notice:
    - This link will expire in 1 hour
    - If you didn't request this reset, please ignore this email
    - Never share this link with anyone
    
    © 2026 A&D Thysia Resort. All rights reserved.
    This is an automated email. Please do not reply.
    """
    
    return send_email(
        to=user_email,
        subject='Reset Your Password - A&D Thysia',
        html_body=html_body,
        text_body=text_body
    )
