#!/usr/bin/env python3
"""
Start UserBot in chat roulette mode (full automation)
"""
import os
import base64
import sys


# ============================================
# SESSION RESTORE FOR RENDER (before all imports)
# ============================================
def configure_console_encoding():
    """Configure UTF-8 output to avoid Windows console encoding crashes."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def restore_session():
    """Restores .session file from SESSION_B64 environment variable"""
    session_b64 = os.getenv('SESSION_B64')
    if not session_b64:
        return False

    # Determine session storage path (must match Config.SESSION_FILE)
    project_root = os.path.dirname(os.path.abspath(__file__))
    is_cloud = any([
        os.getenv('RENDER', '') != '',
        os.getenv('RENDER_EXTERNAL_HOSTNAME', '') != '',
        os.getenv('RAILWAY_ENVIRONMENT', '') != '',
        os.getenv('RAILWAY_PROJECT_ID', '') != '',
    ])
    default_data_dir = '/tmp/data' if is_cloud else os.path.join(project_root, 'data')
    session_dir = os.getenv('DATA_DIR', default_data_dir)
    os.makedirs(session_dir, exist_ok=True)

    session_path = os.path.join(session_dir, 'userbot_session.session')

    # If file already exists — don't overwrite
    if os.path.exists(session_path):
        print(f"✅ Session already exists: {session_path}")
        return True

    try:
        session_data = base64.b64decode(session_b64)
        with open(session_path, 'wb') as f:
            f.write(session_data)
        print(f"🔐 Session restored from env: {session_path}")
        return True
    except Exception as e:
        print(f"❌ Session restore error: {e}")
        return False


# Try to restore session
configure_console_encoding()
restore_session()

# ============================================
# MAIN IMPORTS
# ============================================
import asyncio
import logging
import time

from bot.config import Config
from bot.userbot_client import SimpleUserBot
from bot.chat_roulette.manager import ChatRouletteManager


def setup_logging():
    """Setup logging"""
    # Create log directory if needed
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


async def main():
    """Main function"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║  🎰 Telegram Chat Roulette Bot v2.0                           ║
║                                                               ║
║  Mode: FULL AUTOMATION                                        ║
║  Goal: Getting usernames from chat roulette                   ║
║  Strategy: High trust, flirting, quick contact grab          ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Validate config
    if not Config.validate():
        print("❌ Config validation error")
        return 1

    # Create directories
    Config.create_directories()

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Starting bot...")
    logger.info(f"📁 Working directory: {Config.DATA_DIR}")
    logger.info(f"📱 Phone: {Config.PHONE_NUMBER}")

    # Check session
    session_exists = os.path.exists(f"{Config.SESSION_FILE}.session")
    if not session_exists:
        logger.warning(f"⚠️ Session file not found: {Config.SESSION_FILE}.session")
        print("""
⚠️  SESSION NOT FOUND!

   First local run is fine:
   - Telegram will ask for confirmation code
   - Session file will be created automatically

   For Render/Cloud later:
   - Encode session: base64 data/userbot_session.session
   - Add to SESSION_B64 environment variable
        """)

    try:
        # Create bot
        bot = SimpleUserBot()

        # Create chat roulette manager
        roulette = ChatRouletteManager(
            client=bot.client,
            ai_client=bot.ai,
            memory=bot.memory,
            config={
                "TARGET_USERNAME": Config.TARGET_USERNAME,
                "ROULETTE_BOT": Config.ROULETTE_BOT,
                "BOT_NAME": Config.BOT_NAME,
                "DIALOG_EXAMPLES": getattr(Config, 'DIALOG_EXAMPLES', [])
            }
        )

        # Event callbacks
        async def on_dialog_start(dialog):
            logger.info(f"🎯 New dialog started!")

        async def on_dialog_end(dialog, reason):
            duration = time.time() - dialog.start_time if hasattr(dialog, 'start_time') else 0
            logger.info(f"🔚 Dialog ended. Duration: {duration:.0f}s")

        async def on_username_received(username, dialog):
            logger.info(f"🎉🎉🎉 GOT USERNAME: @{username} 🎉🎉🎉")
            # Save to file
            try:
                with open(Config.CAPTURED_USERNAMES_FILE, "a") as f:
                    msg_count = getattr(dialog, 'message_count', 0)
                    f.write(f"{username},{int(time.time())},{msg_count}\n")
                logger.info(f"💾 Saved to {Config.CAPTURED_USERNAMES_FILE}")
            except Exception as e:
                logger.error(f"❌ Error saving username: {e}")

        # Bind callbacks
        roulette.on_dialog_start = on_dialog_start
        roulette.on_dialog_end = on_dialog_end
        roulette.on_username_received = on_username_received

        # Start client
        logger.info("📲 Connecting to Telegram...")
        await bot.client.start(phone=Config.PHONE_NUMBER)
        logger.info("✅ Connected!")

        # Initialize manager
        await roulette.initialize()
        roulette.register_handlers()
        logger.info("🎰 Chat roulette manager ready")

        # Start auto mode
        logger.info("▶️ Starting auto mode...")
        await roulette.start_auto_mode()

        # Keep bot running
        logger.info("⏳ Bot is running. Press Ctrl+C to stop.")
        await bot.client.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("🛑 Stopping on user request...")
        try:
            await roulette.stop_auto_mode()
        except:
            pass
    except Exception as e:
        logger.error(f"💥 Critical error: {e}", exc_info=True)
        raise

    return 0


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code if exit_code else 0)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
    