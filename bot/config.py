"""
UserBot configuration for Render
"""
import os
from dotenv import load_dotenv

# Load variables from .env (locally) or from env (on Render)
load_dotenv()


class Config:
    """Main configuration class"""

    # ============================================
    # TELEGRAM USERBOT (YOUR ACCOUNT)
    # ============================================
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")

    # ============================================
    # SERVER SETTINGS
    # ============================================
    SERVER_MODE = os.getenv("SERVER_MODE", "polling")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8443")))
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SSL_CERT = os.getenv("SSL_CERT", "")
    SSL_KEY = os.getenv("SSL_KEY", "")

    # ============================================
    # OPENROUTER (AI MODEL)
    # ============================================
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    # ============================================
    # BOT BEHAVIOR SETTINGS
    # ============================================
    BOT_NAME = os.getenv("BOT_NAME", "Diana")
    BOT_AGE = int(os.getenv("BOT_AGE", "18"))
    BOT_CITY = os.getenv("BOT_CITY", "NYC")

    # ============================================
    # FILE PATHS (ADAPTED FOR RENDER)
    # ============================================
    # Detect cloud hosting (Render/Railway etc.)
    IS_CLOUD = any([
        os.getenv("RENDER", "") != "",
        os.getenv("RENDER_EXTERNAL_HOSTNAME", "") != "",
        os.getenv("RAILWAY_ENVIRONMENT", "") != "",
        os.getenv("RAILWAY_PROJECT_ID", "") != "",
    ])

    # Base project path (local) or temp path (cloud)
    BASE_DIR = "/tmp" if IS_CLOUD else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # DATA_DIR can be overridden via env variable
    # By default on cloud we write to /tmp/data (ephemeral FS)
    DATA_DIR = os.getenv("DATA_DIR", "/tmp/data" if IS_CLOUD else os.path.join(BASE_DIR, "data"))

    DIALOGUES_DIR = os.path.join(DATA_DIR, "dialogues")
    CONTEXTS_DIR = os.path.join(DATA_DIR, "contexts")

    # Telethon session — important! On Render stored in /tmp
    SESSION_FILE = os.path.join(DATA_DIR, "userbot_session")

    # ============================================
    # MEMORY & CONTEXT SETTINGS
    # ============================================
    MAX_HISTORY = int(os.getenv("MAX_HISTORY", "50"))
    STYLE_EXAMPLES_COUNT = int(os.getenv("STYLE_EXAMPLES_COUNT", "15"))

    # ============================================
    # RESPONSE SETTINGS
    # ============================================
    TYPING_SIMULATION = os.getenv("TYPING_SIMULATION", "true").lower() == "true"
    MIN_TYPING_DELAY = float(os.getenv("MIN_TYPING_DELAY", "1.0"))
    MAX_TYPING_DELAY = float(os.getenv("MAX_TYPING_DELAY", "4.0"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "200"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

    # ============================================
    # TRUST SETTINGS
    # ============================================
    INITIAL_TRUST = int(os.getenv("INITIAL_TRUST", "50"))
    MIN_TRUST = -100
    MAX_TRUST = 100

    # ============================================
    # ALLOWED CHATS LIST
    # ============================================
    ALLOWED_CHATS = [
        int(chat_id.strip())
        for chat_id in os.getenv("ALLOWED_CHATS", "").split(",")
        if chat_id.strip()
    ]

    BLOCKED_CHATS = [
        int(chat_id.strip())
        for chat_id in os.getenv("BLOCKED_CHATS", "").split(",")
        if chat_id.strip()
    ]

    # ============================================
    # LOGGING SETTINGS
    # ============================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.path.join(DATA_DIR, "bot.log")

    # ============================================
    # CHAT ROULETTE SETTINGS
    # ============================================
    ROULETTE_BOT = os.getenv("ROULETTE_BOT", "anonymous_chat_bot")
    TARGET_USERNAME = os.getenv("TARGET_USERNAME", "")
    MAX_DIALOG_DURATION = int(os.getenv("MAX_DIALOG_DURATION", "300"))
    MIN_MESSAGES_BEFORE_OFFER = int(os.getenv("MIN_MESSAGES_BEFORE_OFFER", "3"))
    CAPTURED_USERNAMES_FILE = os.path.join(DATA_DIR, "captured_usernames.txt")

    DIALOG_EXAMPLES = [
        "hey d",
        "heyy)",
        "hey",
        "18",
        "gimme a present)",
        "urself lmao",
        "dm me",
        "m",
        "how old r u?",
        "from nyc",
        "u?",
        "gotcha",
        "nice",
        "))",
        "lmao",
        "let's move to tg",
        "my @username, hmu there",
        "slide in my dms",
        "drop ur tg",
    ]

    @classmethod
    def validate(cls):
        """Validate required settings"""
        errors = []

        if cls.API_ID == 0:
            errors.append("API_ID not set! Get it at https://my.telegram.org/apps")

        if not cls.API_HASH:
            errors.append("API_HASH not set! Get it at https://my.telegram.org/apps")

        if not cls.PHONE_NUMBER:
            errors.append("PHONE_NUMBER not set!")

        if not cls.OPENROUTER_API_KEY:
            errors.append("OPENROUTER_API_KEY not set! Get it at https://openrouter.ai/keys")

        if errors:
            print("❌ CONFIG ERRORS:")
            for error in errors:
                print(f"   - {error}")
            print("\nFill in the environment variables and try again.")
            return False

        return True

    @classmethod
    def create_directories(cls):
        """Create required directories"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.DIALOGUES_DIR, exist_ok=True)
        os.makedirs(cls.CONTEXTS_DIR, exist_ok=True)
