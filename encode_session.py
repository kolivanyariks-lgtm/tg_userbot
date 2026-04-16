#!/usr/bin/env python3
"""
Helper script to encode session file to base64 for Railway/Render deployment
"""
import os
import base64
import sys


def encode_session():
    """Encode session file to base64"""
    session_file = "data/userbot_session.session"
    
    if not os.path.exists(session_file):
        print(f"❌ Session file not found: {session_file}")
        print("\n💡 First run the bot locally to create a session:")
        print("   python run_polling.py")
        return False
    
    try:
        with open(session_file, 'rb') as f:
            session_data = f.read()
        
        session_b64 = base64.b64encode(session_data).decode('utf-8')
        
        print("✅ Session encoded successfully!")
        print("\n" + "="*60)
        print("SESSION_B64 value (copy this to Railway/Render):")
        print("="*60)
        print(session_b64)
        print("="*60)
        
        # Save to file
        output_file = "session_b64.txt"
        with open(output_file, 'w') as f:
            f.write(session_b64)
        
        print(f"\n💾 Also saved to: {output_file}")
        print("\n📋 Next steps:")
        print("1. Copy the SESSION_B64 value above")
        print("2. Go to Railway/Render dashboard")
        print("3. Add environment variable: SESSION_B64 = <paste value>")
        print("4. Deploy!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error encoding session: {e}")
        return False


if __name__ == '__main__':
    encode_session()
