#!/usr/bin/env python3
"""
Interactive Telegram authorization for Railway/Cloud deployment
Run this in Railway Shell to authorize and create session
"""
import os
import sys
import asyncio
import base64
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def interactive_auth():
    """Interactive Telegram authorization"""
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║  Telegram UserBot - Interactive Authorization                 ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    # Get credentials from environment
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE_NUMBER')
    
    if not api_id or not api_hash or not phone:
        print("❌ Error: Missing environment variables!")
        print("   Required: API_ID, API_HASH, PHONE_NUMBER")
        return False
    
    print(f"📱 Phone: {phone}")
    print(f"🔑 API ID: {api_id}")
    print()
    
    # Determine session path
    is_cloud = any([
        os.getenv('RENDER', '') != '',
        os.getenv('RAILWAY_ENVIRONMENT', '') != '',
    ])
    
    if is_cloud:
        data_dir = os.getenv('DATA_DIR', '/tmp/data')
    else:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    os.makedirs(data_dir, exist_ok=True)
    session_path = os.path.join(data_dir, 'userbot_session')
    
    print(f"💾 Session will be saved to: {session_path}.session")
    print()
    
    # Create client
    client = TelegramClient(session_path, int(api_id), api_hash)
    
    try:
        print("🔄 Connecting to Telegram...")
        await client.connect()
        
        if not await client.is_user_authorized():
            print("📲 Sending code request...")
            await client.send_code_request(phone)
            
            print()
            print("=" * 60)
            print("📬 Check your Telegram app for the confirmation code")
            print("=" * 60)
            print()
            
            # Get code from user
            code = input("Enter the code you received: ").strip()
            
            try:
                await client.sign_in(phone, code)
                print("✅ Code accepted!")
                
            except SessionPasswordNeededError:
                print()
                print("🔐 Two-factor authentication is enabled")
                password = input("Enter your 2FA password: ").strip()
                await client.sign_in(password=password)
                print("✅ Password accepted!")
        
        # Test connection
        me = await client.get_me()
        print()
        print("=" * 60)
        print(f"✅ Successfully authorized as: {me.first_name}")
        print(f"   Username: @{me.username}" if me.username else "   (no username)")
        print(f"   Phone: {me.phone}")
        print("=" * 60)
        print()
        
        # Save session info
        session_file = f"{session_path}.session"
        if os.path.exists(session_file):
            file_size = os.path.getsize(session_file)
            print(f"💾 Session file created: {session_file}")
            print(f"   Size: {file_size} bytes")
            print()
            
            # Encode to base64 for environment variable
            with open(session_file, 'rb') as f:
                session_data = f.read()
            session_b64 = base64.b64encode(session_data).decode('utf-8')
            
            print("📋 SESSION_B64 value (if needed for env var):")
            print("=" * 60)
            print(session_b64[:100] + "..." if len(session_b64) > 100 else session_b64)
            print("=" * 60)
            print(f"   Length: {len(session_b64)} characters")
            
            if len(session_b64) > 32768:
                print("   ⚠️  WARNING: Too large for Railway env var (32KB limit)")
                print("   Use volume mount instead: DATA_DIR=/data")
            else:
                print("   ✅ Size OK for environment variable")
            print()
        
        print("🎉 Authorization complete!")
        print()
        print("Next steps:")
        if is_cloud:
            print("1. Session is saved in the volume")
            print("2. Restart your deployment")
            print("3. Bot will use the saved session")
        else:
            print("1. Run: python encode_session.py")
            print("2. Copy SESSION_B64 to Railway/Render")
            print("3. Deploy!")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Error during authorization: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    try:
        result = asyncio.run(interactive_auth())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Authorization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
