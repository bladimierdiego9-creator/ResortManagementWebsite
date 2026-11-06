#!/usr/bin/env python3
"""
Test script to verify session protection is working
"""

import requests
import sys

def test_session_protection():
    """Test URL manipulation protection"""
    base_url = "http://localhost:5000"  # Adjust as needed
    
    print("🔒 Testing Session-Based URL Protection")
    print("=" * 50)
    
    # Test 1: Direct URL access (should work with proper session)
    print("1. Testing direct URL access...")
    try:
        response = requests.get(f"{base_url}/payments/verification", 
                              allow_redirects=False,
                              timeout=5)
        print(f"   Status: {response.status_code}")
        if 'payment_session' in response.cookies:
            print("   ✅ Session cookie set")
        else:
            print("   ⚠️  No session cookie found")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
    
    # Test 2: Check security headers
    print("\n2. Testing security headers...")
    try:
        response = requests.get(f"{base_url}/payments/verification", 
                              timeout=5)
        headers = response.headers
        
        security_headers = [
            'Cache-Control',
            'Pragma', 
            'Expires',
            'X-Frame-Options',
            'X-Content-Type-Options'
        ]
        
        for header in security_headers:
            if header in headers:
                print(f"   ✅ {header}: {headers[header]}")
            else:
                print(f"   ❌ Missing {header}")
                
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
    
    print("\n3. Testing cookie attributes...")
    try:
        response = requests.get(f"{base_url}/payments/verification", 
                              timeout=5)
        
        for cookie in response.cookies:
            if cookie.name == 'payment_session':
                print(f"   ✅ Cookie: {cookie.name}")
                print(f"   ✅ HttpOnly: {cookie.has_nonstandard_attr('httponly')}")
                print(f"   ✅ SameSite: {cookie.get_nonstandard_attr('samesite', 'Not Set')}")
                print(f"   ✅ Secure: {cookie.secure}")
                break
        else:
            print("   ⚠️  Payment session cookie not found")
            
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")

if __name__ == "__main__":
    print("GCash Payment Verification - Session Protection Test")
    print("Note: This requires the Flask app to be running")
    test_session_protection()