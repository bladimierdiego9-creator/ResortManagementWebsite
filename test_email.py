"""
Test email sending functionality
"""
from app import create_app
from app.email import send_password_reset_email

app = create_app()

with app.app_context():
    print("\n=== TESTING EMAIL CONFIGURATION ===\n")
    
    # Get config
    print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")
    
    # Check if password is set (don't print it)
    password = app.config.get('MAIL_PASSWORD', '').strip()
    password_clean = ''.join(password.split())  # Remove all spaces for Gmail
    print(f"MAIL_PASSWORD: {'[SET]' if password else '[NOT SET]'}")
    print(f"Password length: {len(password_clean)} characters")
    
    print("\n=== SENDING TEST EMAIL ===\n")
    
    # Send test email
    test_email = "thysiaresort@gmail.com"
    test_otp = "123456"
    
    print(f"Sending OTP to: {test_email}")
    print(f"Test OTP: {test_otp}")
    
    try:
        result = send_password_reset_email(test_email, test_otp)
        if result:
            print("\n[SUCCESS] EMAIL SENT SUCCESSFULLY!")
        else:
            print("\n[FAILED] EMAIL SENDING FAILED!")
            print("Check the logs above for error details.")
    except Exception as e:
        print(f"\n[ERROR]: {e}")
