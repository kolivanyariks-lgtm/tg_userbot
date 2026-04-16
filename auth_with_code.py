#!/usr/bin/env python3
"""
Use existing Telegram code without requesting a new one
Useful when you already have a code and don't want to trigger FloodWait
"""
import os
import sys
import asyncio
import base64
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def auth_with_existing_code():
    """Authorize using code you already have"""
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║  Telegram Auth - Use Existing Code                            ║
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
        
        if await client.is_user_authorized():
            print("✅ Already authorized! No code needed.")
            me = await client.get_me()
            print(f"   Logged in as: {me.first_name} (@{me.username})")
            await client.disconnect()
            return True
        
        print("📝 You need to authorize with a code")
        print()
        print("⚠️  IMPORTANT: This will NOT request a new code!")
        print("   Use the code you already received in Telegram")
        print()
        
        # Check if code is provided via environment variable
        code = os.getenv('TELEGRAM_CODE', '').strip()
        
        if code:
            print(f"✅ Using code from TELEGRAM_CODE environment variable: {code}")
        else:
            # Get code from user input
            code = input("Enter the code you already have: ").strip()
        
        if not code:
            print("❌ No code provided")
            print("   Set TELEGRAM_CODE environment variable or enter it manually")
            return False
        
        try:
            print("🔐 Signing in with provided code...")
            await client.sign_in(phone, code)
            print("✅ Code accepted!")
            
        except SessionPasswordNeededError:
            print()
            print("🔐 Two-factor authentication is enabled")
            
            # Check if password is provided via environment variable
            password = os.getenv('TELEGRAM_2FA_PASSWORD', '').strip()
            
            if password:
                print("✅ Using 2FA password from TELEGRAM_2FA_PASSWORD environment variable")
            else:
                password = input("Enter your 2FA password: ").strip()
            
            await client.sign_in(password=password)
            print("✅ Password accepted!")
        
        except Exception as e:
            error_msg = str(e)
            if "PHONE_CODE_EXPIRED" in error_msg:
                print("❌ Code expired! You need to wait for FloodWait to end, then request a new code.")
                print("   Use: python auth_interactive.py")
            elif "PHONE_CODE_INVALID" in error_msg:
                print("❌ Invalid code! Make sure you entered it correctly.")
            else:
                print(f"❌ Error: {e}")
            return False
        
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
        result = asyncio.run(auth_with_existing_code())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Authorization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
