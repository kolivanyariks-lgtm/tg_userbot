"""
UserBot Client - Telethon client working on behalf of a user
Uses your account's API ID and API Hash
"""
import os
import asyncio
import logging
from typing import Optional, Set
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from bot.config import Config
from bot.ai_client import AIClient
from bot.dialogue_memory import DialogueMemory

logger = logging.getLogger(__name__)


class UserBotClient:
    """
    UserBot client based on Telethon
    Works on behalf of your Telegram account
    """
    
    def __init__(self):
        """Initialize UserBot client"""
        # Create Telethon client
        self.client = TelegramClient(
            Config.SESSION_FILE,
            Config.API_ID,
            Config.API_HASH
        )
        
        # Initialize memory and AI
        self.memory = DialogueMemory()
        self.ai = AIClient(self.memory)
        
        # Set of processed messages (duplicate protection)
        self.processed_messages: Set[int] = set()
        
        # Bot running flag
        self.is_running = False
        
        logger.info("UserBotClient initialized")
    
    async def start(self):
        """Start client and authorize"""
        logger.info("Starting UserBot...")
        
        # Connect to Telegram
        await self.client.start(phone=Config.PHONE_NUMBER)
        
        # Get info about self
        me = await self.client.get_me()
        logger.info(f"Authorized as: {me.first_name} (@{me.username}) ID: {me.id}")
        
        # Register event handlers
        self._register_handlers()
        
        self.is_running = True
        logger.info("✅ UserBot started and ready!")
        
        # Keep client running
        await self.client.run_until_disconnected()
    
    def _register_handlers(self):
        """Register event handlers"""
        
        # New message handler
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            await self._on_message(event)
        
        # Edited message handler
        @self.client.on(events.MessageEdited)
        async def handle_edited_message(event):
            # Can add logic for handling edits here
            pass
        
        logger.info("Event handlers registered")
    
    async def _on_message(self, event):
        """
        Handle incoming message
        
        Args:
            event: New message event
        """
        # Skip our own messages
        if event.out:
            return
        
        # Get message info
        message = event.message
        chat = await event.get_chat()
        sender = await event.get_sender()
        
        # Duplicate protection
        if message.id in self.processed_messages:
            return
        self.processed_messages.add(message.id)
        
        # Clean up old IDs (keep last 1000)
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])
        
        # Check if we should respond
        if not await self._should_respond(message, chat, sender):
            return
        
        # Get message text
        text = message.message
        if not text:
            return
        
        user_id = sender.id
        username = sender.first_name or "User"
        chat_type = self._get_chat_type(chat)
        
        logger.info(f"[Message] {username} ({user_id}): {text[:50]}...")
        
        # Save message to context
        self.memory.add_to_context(user_id, "user", text, username)
        
        # Simulate typing if enabled
        if Config.TYPING_SIMULATION:
            async with self.client.action(chat, 'typing'):
                import random
                delay = random.uniform(Config.MIN_TYPING_DELAY, Config.MAX_TYPING_DELAY)
                await asyncio.sleep(delay)
        
        # Get response from AI
        response = await self.ai.get_response(user_id, text, chat_type)
        
        # Final check for leftover SCORE
        if "[score" in response.lower():
            response = response.split("[score")[0].strip()
        
        # Save response to context
        self.memory.add_to_context(user_id, "assistant", response)
        
        # Send response
        await event.reply(response.lower())
        
        logger.info(f"[Response] {response[:50]}...")
    
    async def _should_respond(self, message, chat, sender) -> bool:
        """
        Check if we should respond to the message
        
        Args:
            message: Message
            chat: Chat
            sender: Sender
            
        Returns:
            bool: True if we should respond
        """
        # Don't respond to empty messages
        if not message.message:
            return False
        
        # Don't respond to messages without text (photos, videos etc. without caption)
        if not message.message.strip():
            return False
        
        user_id = sender.id
        chat_id = chat.id
        
        # Check blocklist
        if chat_id in Config.BLOCKED_CHATS or user_id in Config.BLOCKED_CHATS:
            return False
        
        # Check allowlist (if set)
        if Config.ALLOWED_CHATS:
            if chat_id not in Config.ALLOWED_CHATS and user_id not in Config.ALLOWED_CHATS:
                return False
        
        # Get chat type
        chat_type = self._get_chat_type(chat)
        
        # Always respond in DMs
        if chat_type == "private":
            return True
        
        # In groups respond only if:
        # 1. Bot name is mentioned
        # 2. It's a reply to our message
        # 3. Message contains @username mention
        
        text = message.message.lower()
        bot_name = Config.BOT_NAME.lower()
        
        # Check name mention
        if bot_name in text:
            return True
        
        # Check if it's a reply to our message
        if message.reply_to:
            try:
                replied_msg = await message.get_reply_message()
                if replied_msg and replied_msg.out:
                    return True
            except:
                pass
        
        # Check @username mention
        me = await self.client.get_me()
        if me.username and f"@{me.username.lower()}" in text:
            return True
        
        return False
    
    def _get_chat_type(self, chat) -> str:
        """
        Determine chat type
        
        Args:
            chat: Chat object
            
        Returns:
            str: Chat type (private, group, channel, supergroup)
        """
        if isinstance(chat, User):
            return "private"
        elif isinstance(chat, Channel):
            if chat.megagroup:
                return "supergroup"
            else:
                return "channel"
        elif isinstance(chat, Chat):
            return "group"
        else:
            return "unknown"
    
    async def send_message(self, chat_id: int, text: str):
        """
        Send message to specified chat
        
        Args:
            chat_id: Chat ID
            text: Message text
        """
        try:
            await self.client.send_message(chat_id, text)
            logger.info(f"Message sent to chat {chat_id}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def stop(self):
        """Stop client"""
        logger.info("Stopping UserBot...")
        self.is_running = False
        await self.client.disconnect()
        logger.info("✅ UserBot stopped")
    
    # ==================== CONTROL COMMANDS ====================
    
    async def cmd_start(self, event):
        """Command /start - reset memory"""
        user_id = (await event.get_sender()).id
        self.memory.reset_user_memory(user_id)
        
        responses = [
            "oh hey. do we know each other?",
            "who even are u... whatever, hey. what do u want?",
            "hey. who r u lol",
            "hi. what's up?"
        ]
        import random
        await event.reply(random.choice(responses))
    
    async def cmd_clear(self, event):
        """Command /clear - clear context"""
        user_id = (await event.get_sender()).id
        if self.memory.clear_context(user_id):
            await event.reply("ok, forgot everything.")
        else:
            await event.reply("didn't remember anything anyway lol.")
    
    async def cmd_trust(self, event):
        """Command /trust - show trust level"""
        user_id = (await event.get_sender()).id
        stats = self.memory.get_user_stats(user_id)
        trust = stats.get('trust', 0)
        
        # Create text scale
        bar_len = 10
        filled = int((trust + 100) / 200 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        mood = "❤️" if trust > 50 else "😐" if trust > -20 else "😠"
        
        await event.reply(f"my trust level for u:\n[{bar}] {trust}% {mood}")
    
    async def cmd_help(self, event):
        """Command /help - help"""
        help_text = """commands:
/start - start over (reset memory)
/clear - clear conversation context
/trust - show trust level
/help - this message

just text me like a normal girl 👋"""
        await event.reply(help_text)


# ==================== SIMPLIFIED CLIENT FOR POLLING ====================

class SimpleUserBot:
    """Simplified version for polling mode"""
    
    def __init__(self):
        self.client = TelegramClient(
            Config.SESSION_FILE,
            Config.API_ID,
            Config.API_HASH
        )
        self.memory = DialogueMemory()
        self.ai = AIClient(self.memory)
        self.processed_messages: Set[int] = set()
    
    async def start(self):
        """Start in polling mode"""
        await self.client.start(phone=Config.PHONE_NUMBER)
        
        me = await self.client.get_me()
        logger.info(f"Authorized as: {me.first_name} (@{me.username})")
        
        # Register handlers
        self._setup_handlers()
        
        logger.info("✅ UserBot started in polling mode!")
        await self.client.run_until_disconnected()
    
    def _setup_handlers(self):
        """Setup handlers"""
        
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = (await event.get_sender()).id
            self.memory.reset_user_memory(user_id)
            
            import random
            responses = [
                "oh hey. do we know each other?",
                "who even are u... whatever, hey. what do u want?",
                "hey. who r u lol"
            ]
            await event.reply(random.choice(responses))
        
        @self.client.on(events.NewMessage(pattern='/clear'))
        async def clear_handler(event):
            user_id = (await event.get_sender()).id
            if self.memory.clear_context(user_id):
                await event.reply("ok, forgot everything.")
            else:
                await event.reply("didn't remember anything anyway lol.")
        
        @self.client.on(events.NewMessage(pattern='/trust'))
        async def trust_handler(event):
            user_id = (await event.get_sender()).id
            stats = self.memory.get_user_stats(user_id)
            trust = stats.get('trust', 0)
            
            bar_len = 10
            filled = int((trust + 100) / 200 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            mood = "❤️" if trust > 50 else "😐" if trust > -20 else "😠"
            
            await event.reply(f"my trust level:\n[{bar}] {trust}% {mood}")
        
        @self.client.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            help_text = """commands:
/start - start over
/clear - clear memory
/trust - trust level
/help - help"""
            await event.reply(help_text)
        
        @self.client.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            await self._handle_message(event)
    
    async def _handle_message(self, event):
        """Handle message"""
        if event.out:
            return
        
        message = event.message
        if not message.message:
            return
        
        # Duplicate protection
        if message.id in self.processed_messages:
            return
        self.processed_messages.add(message.id)
        
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])
        
        sender = await event.get_sender()
        chat = await event.get_chat()
        
        # Check if we should respond
        if not await self._should_answer(message, chat, sender):
            return
        
        text = message.message
        user_id = sender.id
        username = sender.first_name or "User"
        chat_type = "private" if isinstance(chat, User) else "group"
        
        logger.info(f"[{username}]: {text[:50]}...")
        
        # Save to context
        self.memory.add_to_context(user_id, "user", text, username)
        
        # Simulate typing
        if Config.TYPING_SIMULATION:
            async with self.client.action(chat, 'typing'):
                import random
                await asyncio.sleep(random.uniform(1, 2))
        
        # Get response
        response = await self.ai.get_response(user_id, text, chat_type)
        
        # Remove SCORE if leftover
        if "[score" in response.lower():
            response = response.split("[score")[0].strip()
        
        # Save response
        self.memory.add_to_context(user_id, "assistant", response)
        
        # Send
        await event.reply(response.lower())
    
    async def _should_answer(self, message, chat, sender) -> bool:
        """Check if we should respond"""
        if not message.message or not message.message.strip():
            return False
        
        user_id = sender.id
        chat_id = chat.id
        
        if chat_id in Config.BLOCKED_CHATS or user_id in Config.BLOCKED_CHATS:
            return False
        
        if Config.ALLOWED_CHATS:
            if chat_id not in Config.ALLOWED_CHATS and user_id not in Config.ALLOWED_CHATS:
                return False
        
        # Always respond in DMs
        if isinstance(chat, User):
            return True
        
        # In groups - only when addressed
        text = message.message.lower()
        bot_name = Config.BOT_NAME.lower()
        
        if bot_name in text:
            return True
        
        if message.reply_to:
            try:
                replied = await message.get_reply_message()
                if replied and replied.out:
                    return True
            except:
                pass
        
        me = await self.client.get_me()
        if me.username and f"@{me.username.lower()}" in text:
            return True
        
        return False
