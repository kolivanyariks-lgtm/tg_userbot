"""
Handlers - command and message handlers
"""
import random
import asyncio
import logging
from telethon import events
from bot.config import Config
from bot.ai_client import AIClient
from bot.dialogue_memory import DialogueMemory

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Class for handling messages and commands"""
    
    def __init__(self, client, memory: DialogueMemory, ai: AIClient):
        """
        Initialize handlers
        
        Args:
            client: Telethon client
            memory: Dialogue memory object
            ai: AI client
        """
        self.client = client
        self.memory = memory
        self.ai = ai
        
        # Set of processed messages
        self.processed_ids = set()
        
        logger.info("MessageHandlers initialized")
    
    def register(self):
        """Register all handlers"""
        
        # /start command
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_cmd(event):
            await self._handle_start(event)
        
        # /clear command
        @self.client.on(events.NewMessage(pattern='/clear'))
        async def clear_cmd(event):
            await self._handle_clear(event)
        
        # /trust command
        @self.client.on(events.NewMessage(pattern='/trust'))
        async def trust_cmd(event):
            await self._handle_trust(event)
        
        # /stats command
        @self.client.on(events.NewMessage(pattern='/stats'))
        async def stats_cmd(event):
            await self._handle_stats(event)
        
        # /help command
        @self.client.on(events.NewMessage(pattern='/help'))
        async def help_cmd(event):
            await self._handle_help(event)
        
        # /export command
        @self.client.on(events.NewMessage(pattern='/export'))
        async def export_cmd(event):
            await self._handle_export(event)
        
        # Regular message handler
        @self.client.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            await self._handle_message(event)
        
        logger.info("Handlers registered")
    
    async def _handle_start(self, event):
        """Handle /start command"""
        sender = await event.get_sender()
        user_id = sender.id
        
        # Reset user memory
        self.memory.reset_user_memory(user_id)
        
        # Random response
        responses = [
            "oh hey. do we know each other?",
            "who even are u... whatever, hey. what do u want?",
            "hey. who r u lol",
            "hi. what's up?",
            "oh, a new face? hey)",
            "heyy. where u from?"
        ]
        
        await event.reply(random.choice(responses))
        logger.info(f"[CMD /start] from user {user_id}")
    
    async def _handle_clear(self, event):
        """Handle /clear command"""
        sender = await event.get_sender()
        user_id = sender.id
        
        if self.memory.clear_context(user_id):
            responses = [
                "ok, forgot everything.",
                "what were we even talking about? idk anymore.",
                "context cleared. where do we start?",
                "blanked out. what was that again?"
            ]
            await event.reply(random.choice(responses))
        else:
            await event.reply("didn't remember anything anyway lol.")
        
        logger.info(f"[CMD /clear] from user {user_id}")
    
    async def _handle_trust(self, event):
        """Handle /trust command - show trust level"""
        sender = await event.get_sender()
        user_id = sender.id
        
        stats = self.memory.get_user_stats(user_id)
        trust = stats.get('trust', Config.INITIAL_TRUST)
        
        # Create text scale
        bar_len = 12
        filled = int((trust + 100) / 200 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Determine mood emoji
        if trust > 70:
            mood = "❤️ really into u"
        elif trust > 40:
            mood = "😍 u're cute ngl"
        elif trust > 10:
            mood = "🙂 we're chill"
        elif trust > -20:
            mood = "😐 neutral"
        elif trust > -50:
            mood = "😒 u kinda annoy me"
        else:
            mood = "🤬 i hate u lol"
        
        message = f"my trust level for u:\n\n[{bar}] {trust}%\n{mood}"
        await event.reply(message)
        
        logger.info(f"[CMD /trust] User: {user_id}, Trust: {trust}")
    
    async def _handle_stats(self, event):
        """Handle /stats command - statistics"""
        sender = await event.get_sender()
        user_id = sender.id
        
        stats = self.memory.get_user_stats(user_id)
        context = self.memory.get_context(user_id)
        
        trust = stats.get('trust', Config.INITIAL_TRUST)
        message_count = len(context)
        
        message = (
            f"📊 ur stats:\n\n"
            f"trust: {trust}%\n"
            f"messages in memory: {message_count}\n"
            f"total users: {len(self.memory.get_all_users())}"
        )
        
        await event.reply(message)
        logger.info(f"[CMD /stats] from user {user_id}")
    
    async def _handle_help(self, event):
        """Handle /help command"""
        help_text = f"""hey, i'm {Config.BOT_NAME} 😊

available commands:
/start - start over (reset memory)
/clear - clear conversation context
/trust - show trust level
/stats - ur stats
/export - save our chat to a file
/help - show this message

just text me like a normal girl, no commands needed 👋
i remember context and learn from our convos!"""
        
        await event.reply(help_text)
        logger.info("[CMD /help] help shown")
    
    async def _handle_export(self, event):
        """Handle /export command - export dialogue"""
        sender = await event.get_sender()
        user_id = sender.id
        
        # Export dialogue
        filepath = self.memory.export_dialogue(user_id)
        
        if filepath:
            # Send file to user
            await self.client.send_file(
                event.chat_id,
                filepath,
                caption="here's our chat 📄"
            )
            logger.info(f"[CMD /export] Dialogue exported: {filepath}")
        else:
            await event.reply("couldn't export the chat 😔")
    
    async def _handle_message(self, event):
        """Handle regular messages"""
        # Skip outgoing messages (our own)
        if event.out:
            return
        
        message = event.message
        
        # Skip empty messages
        if not message.message or not message.message.strip():
            return
        
        # Duplicate protection
        if message.id in self.processed_ids:
            return
        self.processed_ids.add(message.id)
        
        # Clean up old IDs
        if len(self.processed_ids) > 1000:
            self.processed_ids = set(list(self.processed_ids)[-500:])
        
        # Get info
        sender = await event.get_sender()
        chat = await event.get_chat()
        
        user_id = sender.id
        username = sender.first_name or "User"
        text = message.message
        
        # Check if we should respond
        if not await self._should_respond(message, chat, sender):
            return
        
        # Determine chat type
        from telethon.tl.types import User
        chat_type = "private" if isinstance(chat, User) else "group"
        
        logger.info(f"[{username}]: {text[:60]}...")
        
        # Save message to context
        self.memory.add_to_context(user_id, "user", text, username)
        
        # Simulate typing
        if Config.TYPING_SIMULATION:
            async with self.client.action(chat, 'typing'):
                delay = random.uniform(Config.MIN_TYPING_DELAY, Config.MAX_TYPING_DELAY)
                await asyncio.sleep(delay)
        
        # Get response from AI
        try:
            response = await self.ai.get_response(user_id, text, chat_type)
            
            # Remove SCORE if still there
            if "[score" in response.lower():
                response = response.split("[score")[0].strip()
            
            # Save response to context
            self.memory.add_to_context(user_id, "assistant", response)
            
            # Send response
            await event.reply(response.lower())
            
            logger.info(f"[Response]: {response[:60]}...")
            
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            await event.reply("ugh, smth went wrong... write again?")
    
    async def _should_respond(self, message, chat, sender) -> bool:
        """
        Check if we should respond to the message
        
        Returns:
            bool: True if we should respond
        """
        from telethon.tl.types import User, Channel, Chat
        
        user_id = sender.id
        chat_id = chat.id
        
        # Check blocklist
        if chat_id in Config.BLOCKED_CHATS or user_id in Config.BLOCKED_CHATS:
            return False
        
        # Check allowlist
        if Config.ALLOWED_CHATS:
            if chat_id not in Config.ALLOWED_CHATS and user_id not in Config.ALLOWED_CHATS:
                return False
        
        # Always respond in DMs
        if isinstance(chat, User):
            return True
        
        # In groups and channels - only when addressed
        text = message.message.lower()
        bot_name = Config.BOT_NAME.lower()
        
        # Direct name mention
        if bot_name in text:
            return True
        
        # Reply to our message
        if message.reply_to:
            try:
                replied = await message.get_reply_message()
                if replied and replied.out:
                    return True
            except:
                pass
        
        # @username mention
        me = await self.client.get_me()
        if me.username and f"@{me.username.lower()}" in text:
            return True
        
        return False
