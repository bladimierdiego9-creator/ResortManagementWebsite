"""Email utilities for sending password reset and other system emails."""
import smtplib
import ssl
import os
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
        import os
        from dotenv import load_dotenv
        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        load_dotenv(os.path.join(basedir, '.env'), override=True)

        # Get SMTP settings from env (fallback to config)
        mail_server = os.environ.get('MAIL_SERVER') or current_app.config.get('MAIL_SERVER') or 'smtp.gmail.com'
        mail_port = int(os.environ.get('MAIL_PORT') or current_app.config.get('MAIL_PORT') or 465)
        mail_username = (os.environ.get('MAIL_USERNAME') or current_app.config.get('MAIL_USERNAME') or '').strip()
        mail_password = (os.environ.get('MAIL_PASSWORD') or current_app.config.get('MAIL_PASSWORD') or '').strip()
        mail_use_ssl = os.environ.get('MAIL_USE_SSL', '').lower() in ['true', 'on', '1'] if os.environ.get('MAIL_USE_SSL') is not None else current_app.config.get('MAIL_USE_SSL', False)
        mail_use_tls = os.environ.get('MAIL_USE_TLS', '').lower() in ['true', 'on', '1'] if os.environ.get('MAIL_USE_TLS') is not None else current_app.config.get('MAIL_USE_TLS', True)
        mail_default_sender = os.environ.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_DEFAULT_SENDER') or mail_username

        # If port is 465, SSL must be True
        if mail_port == 465:
            mail_use_ssl = True
            mail_use_tls = False

        # Gmail displays app passwords in four groups separated by spaces.
        if mail_server and mail_server.lower() == 'smtp.gmail.com':
            mail_password = ''.join(mail_password.split())
        
        # Validate config
        if not all([mail_server, mail_port, mail_username, mail_password]):
            print(f"[EMAIL] ERROR: Incomplete config - server={mail_server}, port={mail_port}, user={mail_username}")
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
        timeout = int(os.environ.get('MAIL_TIMEOUT') or current_app.config.get('MAIL_TIMEOUT') or 20)

        print(f"[EMAIL] Connecting to {mail_server}:{mail_port} for {to} (user={mail_username}, SSL={mail_use_ssl}, TLS={mail_use_tls})...")

        # Build transport list - for Gmail, always put port 465 SSL first because
        # port 587 STARTTLS gets connection-aborted by Windows security software.
        transports = []
        if mail_server.lower() == 'smtp.gmail.com':
            transports.append((465, True, False))
            if mail_port != 465:
                transports.append((mail_port, mail_use_ssl, mail_use_tls))
        else:
            transports.append((mail_port, mail_use_ssl, mail_use_tls))

        server = None
        last_error = None
        for port, use_ssl, use_tls in transports:
            candidate = None
            try:
                print(f"[EMAIL] Trying transport port={port}, SSL={use_ssl}, TLS={use_tls}...")
                
                # Create SSL context - disable verification for development/corporate networks
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                if use_ssl:
                    candidate = smtplib.SMTP_SSL(
                        mail_server,
                        port,
                        timeout=timeout,
                        context=ssl_context,
                    )
                    candidate.ehlo()
                else:
                    candidate = smtplib.SMTP(mail_server, port, timeout=timeout)
                    candidate.ehlo()
                    if use_tls:
                        candidate.starttls(context=ssl_context)
                        candidate.ehlo()

                candidate.login(mail_username, mail_password)
                print(f"[EMAIL] SMTP login successful on port {port}!")
                server = candidate
                break
            except smtplib.SMTPAuthenticationError as e:
                print(f"[EMAIL] SMTP auth rejected on port {port}: {e}")
                if candidate is not None:
                    try:
                        candidate.close()
                    except Exception:
                        pass
                raise
            except Exception as e:
                last_error = e
                print(f"[EMAIL] Port {port} transport failed: {type(e).__name__}: {e}")
                if candidate is not None:
                    try:
                        candidate.close()
                    except Exception:
                        pass

        if server is None:
            raise last_error or ConnectionError('No SMTP transport succeeded')

        try:
            server.sendmail(mail_default_sender, to, msg.as_string())
            print(f"[EMAIL] Message sent to {to} successfully!")
        finally:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass
        
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"[EMAIL] Authentication failed: {e.smtp_code} - {e.smtp_error}")
        current_app.logger.error(
            'SMTP authentication was rejected (code %s). Use the valid Gmail '
            'address and a current Google App Password.', e.smtp_code
        )
        return False
    except Exception as e:
        import traceback
        print(f"[EMAIL] Exception occurred: {type(e).__name__}: {e}")
        traceback.print_exc()
        current_app.logger.exception('Failed to send email through SMTP (%s)', type(e).__name__)
        return False


def send_password_reset_email(user_email: str, reset_otp: str) -> bool:
    """
    Send a password reset email with a 6-digit OTP.
    
    Args:
        user_email: Email address of the user requesting password reset
        reset_otp: 6-digit OTP code
    
    Returns:
        True if email sent successfully, False otherwise
    """
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
            .otp-box {{
                background: linear-gradient(135deg, #4edea3 0%, #10b981 100%);
                color: white;
                font-size: 42px;
                font-weight: bold;
                letter-spacing: 8px;
                padding: 25px;
                border-radius: 12px;
                text-align: center;
                margin: 30px 0;
                box-shadow: 0 4px 12px rgba(78, 222, 163, 0.3);
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
                <h2>Password Reset OTP</h2>
                <p>You have requested to reset your password for your A&D Thysia admin account.</p>
                <p>Use this One-Time Password (OTP) to reset your password:</p>
                
                <div class="otp-box">
                    {reset_otp}
                </div>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>This OTP will expire in 15 minutes</li>
                        <li>If you didn't request this reset, please ignore this email</li>
                        <li>Never share this OTP with anyone</li>
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
    A&D Thysia Resort - Password Reset OTP
    
    You have requested to reset your password for your A&D Thysia admin account.
    
    Your One-Time Password (OTP):
    
    {reset_otp}
    
    Security Notice:
    - This OTP will expire in 15 minutes
    - If you didn't request this reset, please ignore this email
    - Never share this OTP with anyone
    
    © 2026 A&D Thysia Resort. All rights reserved.
    This is an automated email. Please do not reply.
    """
    
    return send_email(
        to=user_email,
        subject='Your Password Reset OTP - A&D Thysia',
        html_body=html_body,
        text_body=text_body
    )
