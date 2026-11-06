"""
Test the complete forgot password flow
"""
from app import create_app
from app.models import Account
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("FORGOT PASSWORD FLOW TEST")
    print("="*60 + "\n")
    
    # Step 1: Check if email configuration is set
    print("📧 Step 1: Checking Email Configuration\n")
    
    mail_server = app.config.get('MAIL_SERVER')
    mail_port = app.config.get('MAIL_PORT')
    mail_username = app.config.get('MAIL_USERNAME')
    mail_password = app.config.get('MAIL_PASSWORD', '').strip()
    
    print(f"   MAIL_SERVER: {mail_server}")
    print(f"   MAIL_PORT: {mail_port}")
    print(f"   MAIL_USERNAME: {mail_username}")
    print(f"   MAIL_PASSWORD: {'✅ Set (' + str(len(mail_password)) + ' chars)' if mail_password else '❌ Not set'}")
    
    if not all([mail_server, mail_port, mail_username, mail_password]):
        print("\n   ❌ EMAIL CONFIGURATION INCOMPLETE!")
        print("   Check your .env file for MAIL_* variables\n")
    else:
        print("\n   ✅ Email configuration looks good!\n")
    
    # Step 2: Check if admin account exists
    print("="*60)
    print("👤 Step 2: Checking Admin Account\n")
    
    test_email = "thysiaresort@gmail.com"
    user = Account.query.filter_by(email=test_email).first()
    
    if user:
        print(f"   ✅ Found account:")
        print(f"      Username: {user.username}")
        print(f"      Email: {user.email}")
        print(f"      Status: {user.status}")
        print(f"      Role: {user.role}\n")
    else:
        print(f"   ❌ No account found with email: {test_email}\n")
        print("   Available emails in database:")
        all_accounts = Account.query.all()
        for acc in all_accounts:
            print(f"      - {acc.email} ({acc.username})")
        print()
    
    # Step 3: Test OTP generation
    if user:
        print("="*60)
        print("🔑 Step 3: Testing OTP Generation\n")
        
        try:
            otp = user.generate_reset_token()
            db.session.commit()
            
            print(f"   ✅ OTP Generated: {otp}")
            print(f"   Expires at: {user.reset_token_expiry}\n")
            
            # Test verification
            if user.verify_reset_token(otp):
                print("   ✅ OTP verification works!\n")
            else:
                print("   ❌ OTP verification failed!\n")
                
        except Exception as e:
            print(f"   ❌ Error generating OTP: {e}\n")
    
    # Step 4: Test email sending
    if user and mail_password:
        print("="*60)
        print("📨 Step 4: Testing Email Sending\n")
        
        from app.email import send_password_reset_email
        
        try:
            otp = user.generate_reset_token()
            db.session.commit()
            
            print(f"   Sending email to: {user.email}")
            print(f"   OTP: {otp}")
            print(f"   Attempting to send...\n")
            
            result = send_password_reset_email(user.email, otp)
            
            if result:
                print("   ✅ EMAIL SENT SUCCESSFULLY!")
                print("   Check the inbox for the OTP email.\n")
            else:
                print("   ❌ EMAIL SENDING FAILED!")
                print("   Possible reasons:")
                print("   1. Invalid Gmail App Password")
                print("   2. 2-Factor Authentication not enabled")
                print("   3. Network/firewall issues")
                print("   4. Gmail blocking 'less secure apps'\n")
                
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    print("="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")
