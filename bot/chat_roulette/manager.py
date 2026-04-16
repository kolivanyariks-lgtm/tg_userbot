"""
Chat Roulette Manager - full automation of chat roulette conversations
From finding a partner to getting their username and ending the dialog
"""
import asyncio
import logging
import random
import re
import time
from enum import Enum, auto
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from telethon import events
from telethon.tl.types import Message, User

logger = logging.getLogger(__name__)


class RouletteState(Enum):
    IDLE = auto()           # Waiting, not in a chat
    SEARCHING = auto()      # Looking for a partner (pressed button)
    CONNECTING = auto()     # Connecting, loading partner info
    DIALOG_ACTIVE = auto()  # Active dialog
    USERNAME_SENT = auto()  # Sent our username, waiting for reaction
    ENDING = auto()         # Ending the dialog (/next or /stop)
    COOLDOWN = auto()       # Break between dialogs


@dataclass
class DialogContext:
    """Context of the current dialog"""
    partner_id: Optional[int] = None
    partner_info: Dict[str, Any] = None
    start_time: float = 0
    message_count: int = 0
    last_message_time: float = 0
    username_received: bool = False
    our_username_sent: bool = False
    partner_username: Optional[str] = None  # If partner shared theirs
    dialog_stage: str = "opening"  # opening, rapport, closing
    topics_discussed: list = None
    opening_sent: bool = False
    dialogue_history: list = None
    recent_assistant_replies: list = None
    recent_assistant_texts: list = None
    heat_score: int = 30
    spicy_turns: int = 0
    asked_from: bool = False
    asked_age: bool = False
    asked_name: bool = False
    partner_location_known: bool = False
    proactive_escalation_count: int = 0  # Track bot-initiated escalations
    partner_language: str = "en"  # Detected partner language (en/ru)

    def __post_init__(self):
        if self.topics_discussed is None:
            self.topics_discussed = []
        if self.dialogue_history is None:
            self.dialogue_history = []
        if self.recent_assistant_replies is None:
            self.recent_assistant_replies = []
        if self.recent_assistant_texts is None:
            self.recent_assistant_texts = []
        # Start with lower heat for gradual escalation
        self.heat_score = 15


class ChatRouletteManager:
    """
    Chat roulette manager - full automation
    """

    # Dialog start triggers (messages from chat roulette bot)
    DIALOG_START_TRIGGERS = [
        "dialog started",
        "partner found",
        "match found",
        "chat started",
        "💭 dialog started",
        "🎉 partner found",
        "диалог начат",
        "собеседник найден",
        "партнёр найден",
        "партнер найден",
        "начали диалог",
        "💭 диалог начат",
        "🎉 собеседник найден"
    ]

    # Dialog end triggers (messages from chat roulette bot)
    DIALOG_END_TRIGGERS = [
        "partner left",
        "dialog ended",
        "partner not found",
        "you left the chat",
        "match left",
        "🚫 partner",
        "⏹ dialog ended",
        "собеседник покинул",
        "диалог завершён",
        "диалог завершен",
        "собеседник не найден",
        "вы покинули чат",
        "партнёр покинул",
        "партнер покинул",
        "🚫 собеседник",
        "⏹ диалог завершён",
        "⏹ диалог завершен"
    ]

    # Buttons/commands
    SEARCH_BUTTON_TEXTS = [
        "🔍 find a partner",
        "find a partner",
        "search",
        "🎲 new partner",
        "➡️ next",
        "🔍 искать собеседника",
        "искать собеседника",
        "искать",
        "поиск",
        "🎲 новый собеседник",
        "➡️ следующий",
        "начать поиск",
        "поехали",
        "/search",
        "/next"
    ]

    SYSTEM_REGEX_PATTERNS = [
        r"диалог\s*#?\s*[\d\.]+\s*заверш",
        r"dialog\s*#?\s*[\d\.]+\s*ended",
        r"диалог\s+начат",
        r"dialog\s+started",
        r"собеседник\s+найден",
        r"partner\s+found",
        r"подбираю\s+собеседника",
        r"поиск\s+в\s+процессе",
        r"команда\s+недоступна",
        r"оцените\s+реакцией\s+своего\s+собеседника",
        r"отправьте\s*/search",
        r"buy\s+stars|купить\s+звезды",
        r"if\s+you\s+wish,\s+leave\s+your\s+feedback",
        r"set\s+your\s+gender\s+to\s+improve\s+searching\s+results",
        r"you\s+are\s+in\s+the\s+chat\s+right\s+now",
        r"you\s+stopped\s+the\s+chat",
        r"looking\s+for\s+a\s+partner",
    ]

    def __init__(self, client, ai_client, memory, config):
        self.client = client
        self.ai = ai_client
        self.memory = memory
        self.config = config

        self.state = RouletteState.IDLE
        self.current_dialog: Optional[DialogContext] = None
        self.roulette_bot_id: Optional[int] = None  # Chat roulette bot ID
        self.target_username: str = config.get("TARGET_USERNAME", "your_username_here")

        # Notification callbacks
        self.on_dialog_start: Optional[Callable] = None
        self.on_dialog_end: Optional[Callable] = None
        self.on_username_received: Optional[Callable] = None

        # Stats
        self.stats = {
            "total_dialogs": 0,
            "successful_contacts": 0,
            "total_messages_sent": 0,
            "time_in_chat": 0
        }

        # Timers
        self._dialog_timeout: Optional[asyncio.Task] = None
        self._response_timeout: Optional[asyncio.Task] = None
        self._reply_lock = asyncio.Lock()
        self._fallback_search_cmd_index = 0
        self._pending_partner_messages = []
        self._partner_debounce_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialization - find the chat roulette bot"""
        try:
            # Find bot by username (specify exact username of chat roulette bot)
            roulette_bot_username = self.config.get("ROULETTE_BOT", "anonymous_chat_bot")
            entity = await self.client.get_entity(roulette_bot_username)
            self.roulette_bot_id = entity.id
            logger.info(
                f"🎯 ChatRouletteManager initialized. Bot: @{roulette_bot_username} (ID: {self.roulette_bot_id})")
        except Exception as e:
            logger.error(f"❌ Could not find chat roulette bot: {e}")
            logger.info("⚠️ Will detect bot from message context")

    def register_handlers(self):
        """Register event handlers"""

        @self.client.on(events.NewMessage(incoming=True))
        async def handle_incoming(event):
            await self._handle_message(event)

    async def start_auto_mode(self):
        """Start fully automatic mode"""
        logger.info("🚀 Auto chat roulette mode started")
        self.state = RouletteState.IDLE
        await self._start_search()

    async def stop_auto_mode(self):
        """Stop automatic mode"""
        logger.info("🛑 Stopping automatic mode")
        self.state = RouletteState.IDLE
        if self._dialog_timeout:
            self._dialog_timeout.cancel()
        if self._response_timeout:
            self._response_timeout.cancel()
        # Send /stop if in dialog
        if self.current_dialog:
            await self._send_command("/stop")

    async def _start_search(self):
        """Start searching for a partner"""
        if self.state not in [RouletteState.IDLE, RouletteState.COOLDOWN]:
            return

        logger.info("🔍 Looking for a partner...")
        self.state = RouletteState.SEARCHING
        self.current_dialog = None

        # Press search button
        await self._click_search_button()

        # Wait for connection (60 sec timeout)
        asyncio.create_task(self._wait_for_connection())

    async def _click_search_button(self):
        """Click the 'Find a partner' button"""
        try:
            # Find last message from chat roulette bot with buttons
            async for message in self.client.iter_messages(
                    self.roulette_bot_id or "me",
                    limit=10
            ):
                if message.buttons:
                    for row in message.buttons:
                        for button in row:
                            btn_text = (button.text or "").lower()
                            if any(trigger in btn_text for trigger in self.SEARCH_BUTTON_TEXTS):
                                await message.click(button.data)
                                logger.info(f"✅ Clicked button: {button.text}")
                                return

            # If button not found, send one fallback command.
            # Rotate commands between attempts to support different roulette bots.
            fallback_commands = ["/search", "/next", "/start"]
            command = fallback_commands[self._fallback_search_cmd_index % len(fallback_commands)]
            self._fallback_search_cmd_index += 1
            await self._send_command(command)

        except Exception as e:
            logger.error(f"❌ Error clicking button: {e}")
            fallback_commands = ["/search", "/next", "/start"]
            command = fallback_commands[self._fallback_search_cmd_index % len(fallback_commands)]
            self._fallback_search_cmd_index += 1
            await self._send_command(command)

    async def _send_command(self, command: str):
        """Send command to chat roulette bot"""
        try:
            target = self.roulette_bot_id or self.config.get("ROULETTE_BOT", "anonymous_chat_bot")
            await self.client.send_message(target, command)
            logger.info(f"📤 Command sent: {command}")
        except Exception as e:
            logger.error(f"❌ Error sending command: {e}")

    async def _wait_for_connection(self, timeout: int = 60):
        """Wait for partner connection"""
        try:
            await asyncio.sleep(timeout)
            if self.state == RouletteState.SEARCHING:
                logger.warning("⏱️ Search timeout, trying again...")
                await self._start_search()
        except asyncio.CancelledError:
            pass

    async def _handle_message(self, event):
        """Handle incoming messages"""
        message = event.message
        sender = await event.get_sender()
        chat = await event.get_chat()
        text = (message.text or "").strip()
        sender_id = sender.id if sender else None
        chat_id = getattr(chat, "id", None)

        # Ignore unrelated chats entirely; roulette manager must only process roulette chat.
        if self.roulette_bot_id and chat_id and chat_id != self.roulette_bot_id:
            return

        # In anonymous roulette, both system and partner texts come from roulette bot.
        # So when sender is roulette bot, we must classify by text content, not sender id.
        if sender and self.roulette_bot_id and sender.id == self.roulette_bot_id:
            is_roulette_bot = self._is_roulette_bot_message(text)
        else:
            is_roulette_bot = self._is_roulette_bot_message(text)

        logger.info(
            "[Roulette msg] state=%s sender_id=%s roulette_bot_id=%s is_bot=%s text=%s",
            self.state.name,
            sender_id,
            self.roulette_bot_id,
            is_roulette_bot,
            text[:120] if text else "<empty>",
        )

        if is_roulette_bot:
            await self._handle_roulette_bot_message(message)
        else:
            # Some roulette bots forward partner text without explicit
            # "dialog started" system message. Promote state on first partner text.
            if self.state == RouletteState.SEARCHING:
                logger.info("[Roulette] partner text arrived while SEARCHING, promoting to active dialog")
                await self._activate_dialog_from_partner_message()
            # Message from partner
            await self._handle_partner_message(event)

    async def _activate_dialog_from_partner_message(self):
        """Promote SEARCHING -> DIALOG_ACTIVE when partner message arrives first."""
        if self.state != RouletteState.SEARCHING:
            return

        self.state = RouletteState.DIALOG_ACTIVE
        self.stats["total_dialogs"] += 1
        self.current_dialog = DialogContext(
            start_time=time.time(),
            last_message_time=time.time(),
        )
        if self._partner_debounce_task and not self._partner_debounce_task.done():
            self._partner_debounce_task.cancel()
        self._pending_partner_messages = []

        if self.on_dialog_start:
            await self.on_dialog_start(self.current_dialog)

        if self._dialog_timeout:
            self._dialog_timeout.cancel()
        self._dialog_timeout = asyncio.create_task(self._dialog_timeout_task(600))

    @staticmethod
    def _normalize_text(text: str) -> str:
        text_lower = (text or "").lower()
        return re.sub(r"[*_`~]", "", text_lower)

    def _is_dialog_start_message(self, normalized: str) -> bool:
        if any(trigger in normalized for trigger in self.DIALOG_START_TRIGGERS):
            return True
        return bool(re.search(r"диалог\s+начат|dialog\s+started|собеседник\s+найден|partner\s+found", normalized))

    def _is_dialog_end_message(self, normalized: str) -> bool:
        if any(trigger in normalized for trigger in self.DIALOG_END_TRIGGERS):
            return True
        return bool(
            re.search(
                r"диалог\s*#?\s*[\d\.]+\s*заверш|"
                r"dialog\s*#?\s*[\d\.]+\s*ended|"
                r"вы\s+покинули\s+чат|you\s+left\s+the\s+chat|"
                r"you\s+stopped\s+the\s+chat|"
                r"отправьте\s*/search|type\s*/search",
                normalized,
            )
        )

    def _is_roulette_bot_message(self, text: str) -> bool:
        """Determine if message is a system message from chat roulette bot"""
        normalized = self._normalize_text(text)

        # Check start/end triggers
        for trigger in self.DIALOG_START_TRIGGERS + self.DIALOG_END_TRIGGERS:
            if trigger in normalized:
                return True

        # Check known system regex patterns
        for pattern in self.SYSTEM_REGEX_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return True

        # Commands and service markers are usually system messages
        if any(cmd in normalized for cmd in ["/stop", "/search", "/premium", "/premgift"]):
            return True

        # Check for buttons presence (usually system messages)
        if (
            "reputation:" in normalized
            or "gender:" in normalized
            or "age:" in normalized
            or "репутация:" in normalized
            or "пол:" in normalized
            or "возраст:" in normalized
        ):
            return True

        return False

    async def _handle_roulette_bot_message(self, message: Message):
        """Handle messages from chat roulette bot"""
        text = message.text or ""
        normalized = self._normalize_text(text)

        # Dialog started
        if self._is_dialog_start_message(normalized):
            await self._on_dialog_start(message)

        # Dialog ended
        elif self._is_dialog_end_message(normalized):
            await self._on_dialog_end("partner_left" if ("left" in normalized or "покинул" in normalized) else "ended")

        # Partner info (parse it)
        elif "gender:" in normalized or "age:" in normalized or "пол:" in normalized or "возраст:" in normalized:
            self._parse_partner_info(message.text)

    def _parse_partner_info(self, text: str):
        """Parse partner info from bot message"""
        info = {}

        # Gender
        gender_match = re.search(r'([Gg]ender|[Пп]ол):\s*(\*\*|male|female|муж|жен|m|f|м|ж)', text)
        if gender_match:
            info['gender'] = gender_match.group(2)

        # Age
        age_match = re.search(r'([Aa]ge|[Вв]озраст):\s*(\*\*|\d+)', text)
        if age_match:
            info['age'] = age_match.group(2)

        # Reputation
        rep_match = re.search(r'([Rr]eputation|[Рр]епутация):[\s\d🗿😘🤭🚩]+', text)
        if rep_match:
            info['reputation'] = rep_match.group(0)

        if self.current_dialog:
            self.current_dialog.partner_info = info
            logger.info(f"👤 Partner info: {info}")

    async def _on_dialog_start(self, message: Message):
        """Handle dialog start"""
        logger.info("🎉 Dialog started!")
        self.state = RouletteState.DIALOG_ACTIVE
        self.stats["total_dialogs"] += 1

        if self._partner_debounce_task and not self._partner_debounce_task.done():
            self._partner_debounce_task.cancel()
        self._pending_partner_messages = []

        self.current_dialog = DialogContext(
            start_time=time.time(),
            last_message_time=time.time()
        )

        # Parse info if present in this message
        self._parse_partner_info(message.text or "")

        # Notification
        if self.on_dialog_start:
            await self.on_dialog_start(self.current_dialog)

        # Cancel search timeout
        if self._dialog_timeout:
            self._dialog_timeout.cancel()

        # Start dialog timeout (max 10 minutes)
        self._dialog_timeout = asyncio.create_task(self._dialog_timeout_task(600))

        # Small delay before first message (naturalness)
        dialog_ref = self.current_dialog
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # If dialog already ended during delay, do not send greeting.
        if self.state != RouletteState.DIALOG_ACTIVE or self.current_dialog is not dialog_ref:
            logger.info("[Roulette skip] dialog ended before greeting")
            return

        # If partner already wrote first, skip greeting to avoid out-of-order reply.
        if self.current_dialog.message_count > 0:
            logger.info("[Roulette skip] partner already sent first message")
            return

        # First message - greeting
        await self._send_message_to_partner(self._get_opening_message())
        self.current_dialog.opening_sent = True

    async def _on_dialog_end(self, reason: str):
        """Handle dialog end"""
        if not self.current_dialog:
            return

        if self._partner_debounce_task and not self._partner_debounce_task.done():
            self._partner_debounce_task.cancel()
        self._pending_partner_messages = []

        duration = time.time() - self.current_dialog.start_time
        self.stats["time_in_chat"] += duration

        logger.info(f"🔚 Dialog ended. Reason: {reason}, Duration: {duration:.1f}s, "
                    f"Messages: {self.current_dialog.message_count}")

        # Notification
        if self.on_dialog_end:
            await self.on_dialog_end(self.current_dialog, reason)

        self.current_dialog = None
        self.state = RouletteState.COOLDOWN

        # Break between dialogs
        cooldown = random.uniform(3, 8)
        logger.info(f"⏱️ Cooldown {cooldown:.1f}s before next search...")
        await asyncio.sleep(cooldown)

        # Auto-search for next
        await self._start_search()

    async def _handle_partner_message(self, event):
        """Handle messages from partner"""
        if self.state != RouletteState.DIALOG_ACTIVE or not self.current_dialog:
            return

        message = event.message
        text = message.text or ""
        if not text.strip():
            return

        # Safety net: if something looks like a service/system message, ignore it.
        if self._is_roulette_bot_message(text):
            logger.info("[Roulette skip] message looks system-like, skipping partner handler")
            return

        # Skip illegal sexual-minor content and end dialog immediately.
        if self._contains_illegal_minor_sexual_content(text):
            logger.warning("[Roulette block] detected sexual content involving minors, ending dialog")
            await self._end_dialog()
            return

        if self._contains_under_16_signal(text):
            logger.warning("[Roulette block] detected under-16 signal, ending dialog")
            await self._end_dialog()
            return

        if self._contains_prohibited_topic(text):
            logger.warning("[Roulette block] detected prohibited topic, ending dialog")
            await self._end_dialog()
            return

        # Update context
        self.current_dialog.message_count += 1
        self.current_dialog.last_message_time = time.time()

        if self.current_dialog.asked_from and not self.current_dialog.partner_location_known and self._looks_like_location_reply(text):
            self.current_dialog.partner_location_known = True
            if not self.current_dialog.partner_info:
                self.current_dialog.partner_info = {}
            self.current_dialog.partner_info["location"] = text.strip()
        
        # AI-based spiciness analysis for better context understanding
        if len(text) > 10 and self.current_dialog.message_count % 2 == 0:
            asyncio.create_task(self._analyze_message_spiciness(text))

        # Save every partner message for live style training in real time.
        try:
            self.memory.record_live_message("user", text, "Partner")
        except Exception:
            pass
        
        # Detect language (Russian vs English)
        if self._detect_russian(text):
            self.current_dialog.partner_language = "ru"
            logger.info("[Roulette] Detected Russian language")
        elif self.current_dialog.partner_language == "en" and self._detect_english(text):
            self.current_dialog.partner_language = "en"

        # Infer shorthand gender messages like "m" and "g".
        inferred_gender = self._infer_gender_from_text(text)
        if inferred_gender:
            if not self.current_dialog.partner_info:
                self.current_dialog.partner_info = {}
            self.current_dialog.partner_info["gender"] = inferred_gender
            logger.info(f"[Roulette] Inferred partner gender from text: {inferred_gender}")

        # Check if partner shared their username
        extracted_username = self._extract_username(text)
        if extracted_username:
            self.current_dialog.partner_username = extracted_username
            self.current_dialog.username_received = True
            self.stats["successful_contacts"] += 1

            logger.info(f"✅ Got partner's username: @{extracted_username}")

            if self.on_username_received:
                await self.on_username_received(extracted_username, self.current_dialog)

            # Can end right away or thank them first
            await asyncio.sleep(random.uniform(1, 2))
            await self._send_message_to_partner("thx, gonna hit u up there 💕")
            await asyncio.sleep(random.uniform(2, 3))
            await self._end_dialog()
            return

        # Batch multiple rapid partner messages into one semantic chunk.
        self._pending_partner_messages.append(text.strip())
        await self._schedule_partner_processing(delay=self._partner_debounce_delay(text))

    async def _schedule_partner_processing(self, delay: float = 1.2):
        """Debounce partner message handling to merge rapid message bursts."""
        if self._partner_debounce_task and not self._partner_debounce_task.done():
            self._partner_debounce_task.cancel()
        self._partner_debounce_task = asyncio.create_task(self._flush_partner_messages_after_delay(delay))

    @staticmethod
    def _partner_debounce_delay(text: str) -> float:
        """Adaptive debounce: wait longer for short fragments like '29', 'ok', '?'"""
        t = (text or "").strip()
        if not t:
            return 0.8
        if len(t) <= 4:
            return 1.8
        if re.fullmatch(r"[0-9]{1,2}", t):
            return 2.0
        if re.fullmatch(r"[?.!]+", t):
            return 1.8
        return 1.0

    async def _flush_partner_messages_after_delay(self, delay: float):
        """Flush queued partner messages and process them as one combined input."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        if self.state != RouletteState.DIALOG_ACTIVE or not self.current_dialog:
            self._pending_partner_messages = []
            return

        chunks = [m for m in self._pending_partner_messages if m]
        self._pending_partner_messages = []
        if not chunks:
            return

        combined_text = "\n".join(chunks)
        if len(chunks) > 1:
            logger.info(f"[Roulette batch] Merged {len(chunks)} partner messages")

        self._update_dialog_heat(combined_text)

        # Prevent overlapping AI generations.
        async with self._reply_lock:
            if self.state != RouletteState.DIALOG_ACTIVE or not self.current_dialog:
                return
            self.current_dialog.dialogue_history.append({"role": "user", "content": combined_text})
            # Increased history limit from 12 to 20 for better context
            if len(self.current_dialog.dialogue_history) > 20:
                self.current_dialog.dialogue_history = self.current_dialog.dialogue_history[-20:]
            await self._process_dialog_stage(combined_text)

    def _update_dialog_heat(self, partner_text: str):
        """Update per-dialog 'heat' level from partner messages."""
        if not self.current_dialog:
            return

        text = (partner_text or "").lower()
        if not text.strip():
            return

        # Positive/engaged signals
        flirt_patterns = [
            r"\bcutie\b|\bbeautiful\b|\bsexy\b|\bcute\b|\bhot\b",
            r"\bkiss\b|\bcuddle\b|\bmiss you\b|\bwant you\b",
            r"\bflirt\b|\bturn\s*on\b|\bhorny\b",
            r"\bпошл\b|\bсек[сc]\b|\bинтим\b|\bгоряч\b",
            r"\bme too\b|\bsame here\b|\binteresting\b",
            r"\bnice\b|\bcool\b|\bawesome\b|\bgreat\b",
        ]

        spicy_explicit_patterns = [
            r"\bdirty\b|\bnaughty\b|\bwet\b|\bspicy\b|\bnsfw\b",
            r"\bпошл[аяо]\b|\bвозбуд|\bэрот|\bразврат",
            r"\bfuck\b|\bsex\b|\bdick\b|\bpussy\b|\btits\b|\bass\b",
            r"\bmasturbat\b|\bcum\b|\bhard\b|\btouch\b",
        ]

        # Contact intent signals
        contact_patterns = [
            r"\btelegram\b|\btg\b|\busername\b|\binsta\b|\binstagram\b|\bwhatsapp\b",
            r"\bтг\b|\bтелеграм\b|\bюзер\b|\bинста\b|\bномер\b",
        ]

        # Cooling/hostile signals
        cold_patterns = [
            r"\bok\b|\bk\b|\bfine\b|\bwhatever\b|\bbye\b",
            r"\bstop\b|\bgo away\b|\bnot interested\b",
            r"\bиди\b|\bотвали\b|\bнеинтересно\b",
        ]

        delta = 0
        for pattern in flirt_patterns:
            if re.search(pattern, text):
                delta += 6
        for pattern in spicy_explicit_patterns:
            if re.search(pattern, text):
                delta += 12
        for pattern in contact_patterns:
            if re.search(pattern, text):
                delta += 10
        for pattern in cold_patterns:
            if re.search(pattern, text):
                delta -= 10

        # Longer engaged messages are usually better than one-word replies.
        if len(text.strip()) >= 35:
            delta += 3
        
        # Question marks indicate engagement
        if "?" in text:
            delta += 2

        # Clamp to [0, 100]
        self.current_dialog.heat_score = max(0, min(100, self.current_dialog.heat_score + delta))
        if delta > 0:
            self.current_dialog.spicy_turns += 1

        logger.info(
            "[Roulette heat] delta=%+d heat=%d",
            delta,
            self.current_dialog.heat_score,
        )

    @staticmethod
    def _partner_is_spicy(text: str) -> bool:
        t = (text or "").lower()
        patterns = [
            r"\bdirty\b|\bnaughty\b|\bsexy\b|\bhorny\b|\bhot\b|\bturn\s*on\b",
            r"\bпошл\b|\bсек[сc]\b|\bинтим\b|\bгоряч\b|\bвозбуд",
            r"\bfuck\b|\bsex\b|\bdick\b|\bpussy\b|\btits\b|\bass\b",
            r"\bwet\b|\bhard\b|\bcum\b|\bmasturbat\b|\btouch\b",
            r"\bwanna\s+(fuck|sex|do)\b|\blet's\s+get\s+dirty\b",
        ]
        return any(re.search(p, t) for p in patterns)

    @staticmethod
    def _infer_gender_from_text(text: str) -> Optional[str]:
        """Infer gender marker from very short partner messages (m/g, man/girl, etc.)."""
        t = (text or "").strip().lower()
        if t in {"m", "man", "male", "парень", "м", "муж", "мужчина"}:
            return "male"
        if t in {"g", "girl", "female", "f", "familar", "familiar", "девушка", "ж", "жен", "женщина"}:
            return "female"
        return None

    @staticmethod
    def _contains_illegal_minor_sexual_content(text: str) -> bool:
        normalized = (text or "").lower()
        minor_signals = [
            r"\b1[0-7]\b",
            r"\bunder\s*18\b",
            r"\bminor\b",
            r"\bнесовершеннолет",
            r"\bд\s*1[0-7]\b",
            r"\bм\s*1[0-7]\b",
        ]
        sexual_signals = [
            r"\bsex\b",
            r"\bsext\b",
            r"\bnudes?\b",
            r"\bintim",
            r"\bпошл",
            r"\bинтим",
            r"\bэрот",
            r"\bшлю",
            r"\bкружк",
        ]
        has_minor = any(re.search(p, normalized) for p in minor_signals)
        has_sexual = any(re.search(p, normalized) for p in sexual_signals)
        return has_minor and has_sexual

    @staticmethod
    def _contains_under_16_signal(text: str) -> bool:
        normalized = (text or "").lower()
        patterns = [
            r"\b(i\s*am|i'm|im)\s*(1[0-5])\b",
            r"\b(1[0-5])\s*(yo|y\.o|years?\s*old)\b",
            r"\b(д|м|f|g)\s*(1[0-5])\b",
            r"\bunder\s*16\b",
            r"\bмне\s*(1[0-5])\b",
            r"\b(возраст)\s*[:\-]?\s*(1[0-5])\b",
        ]
        return any(re.search(p, normalized) for p in patterns)

    @staticmethod
    def _contains_prohibited_topic(text: str) -> bool:
        normalized = (text or "").lower()
        patterns = [
            r"\brape\b|\bизнасил",
            r"\bincest\b|\bинцест",
            r"\bbeastial|\bзоофил",
            r"\bcp\b|\bchild\s*porn|\bдетск.*порн",
            r"\bsuicide\b|\bсамоубийств|\bсамоповреж",
            r"\bdrugs?\b|\bнаркотик|\bзакладк",
        ]
        return any(re.search(p, normalized) for p in patterns)
    
    @staticmethod
    def _detect_russian(text: str) -> bool:
        """Detect if text contains Russian (cyrillic) characters"""
        if not text:
            return False
        # Check for cyrillic characters
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        return cyrillic_count >= 3
    
    @staticmethod
    def _detect_english(text: str) -> bool:
        """Detect if text is primarily English"""
        if not text:
            return False
        # Check for latin characters
        latin_count = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        return latin_count >= 5

    async def _process_dialog_stage(self, partner_text: str):
        """Process dialog stage and make decisions"""
        dialog = self.current_dialog

        if self._partner_is_spicy(partner_text):
            dialog.heat_score = min(100, dialog.heat_score + 15)
            dialog.spicy_turns += 1
            logger.info(f"[Roulette spicy] partner is spicy, heat +15 -> {dialog.heat_score}")

        # Determine stage by conversation heat with adjusted thresholds
        if dialog.heat_score < 25:
            dialog.dialog_stage = "opening"
        elif dialog.heat_score < 50:
            dialog.dialog_stage = "rapport"
        elif dialog.heat_score < 75:
            dialog.dialog_stage = "spicy"
        else:
            dialog.dialog_stage = "closing"
        
        # Proactive escalation: bot gradually increases heat on its own
        if dialog.message_count >= 4 and dialog.message_count % 3 == 0:
            if dialog.heat_score < 80:
                dialog.heat_score = min(100, dialog.heat_score + 3)
                dialog.proactive_escalation_count += 1
                logger.info(f"[Roulette proactive] heat +3 -> {dialog.heat_score}")

        # Try fast human-like short replies for common prompts first.
        response = self._quick_human_reply(partner_text)
        if not response:
            # Generate response via AI
            response = await self._generate_response(partner_text, dialog)
        response = self._finalize_response(response, partner_text)
        response = self._avoid_repeated_reply(response, partner_text)

        # Check if it's time to send username
        if (not self._looks_like_low_value_contact(partner_text)) and self._should_send_username(dialog, response, partner_text):
            response = self._inject_username_offer(response)
            response = self._finalize_response(response, partner_text)
            response = self._avoid_repeated_reply(response, partner_text)
            dialog.our_username_sent = True

        # Send
        delay = self._calculate_typing_delay(response)
        await asyncio.sleep(delay)
        await self._send_message_to_partner(response)

        # If username was sent, wait a bit and end
        if dialog.our_username_sent:
            asyncio.create_task(self._wait_and_end(10))

    async def _generate_response(self, partner_text: str, dialog: DialogContext) -> str:
        """Generate response via AI with chat roulette context"""

        # Build special prompt for chat roulette
        system_prompt = self._build_roulette_prompt(dialog)

        # Message history for current dialog only
        messages = [{"role": "system", "content": system_prompt}]

        # Keep local dialogue history isolated per current partner.
        # Increased from 8 to 12 for better context
        if dialog.dialogue_history:
            history_to_send = dialog.dialogue_history[-12:]
            messages.extend(history_to_send)
            
            # Log history for debugging
            logger.info(f"[AI Context] Sending {len(history_to_send)} messages from history")
            for i, msg in enumerate(history_to_send[-4:]):  # Log last 4 for debugging
                preview = msg['content'][:50] if len(msg['content']) > 50 else msg['content']
                logger.debug(f"  [{msg['role']}] {preview}...")

        # Current message
        messages.append({"role": "user", "content": partner_text})
        logger.info(f"[AI Request] Current message: {partner_text[:80]}...")

        # Get response from AI
        try:
            response = await self.ai.get_raw_response(messages)
            logger.info(f"[AI Response] {response[:80]}...")
        except Exception as e:
            logger.error(f"[AI Error] {e}")
            # Return contextual fallback
            return self._get_contextual_fallback(partner_text)

        # Clean SCORE if present
        response = re.sub(r'\[SCORE:.*?\]', '', response, flags=re.IGNORECASE).strip()

        return response.lower()

    def _build_roulette_prompt(self, dialog: DialogContext) -> str:
        """Build prompt specifically for chat roulette"""

        # Build stage-specific instructions with concrete examples
        stage_instructions = self._get_stage_instructions(dialog.dialog_stage, dialog.heat_score)
        
        # Build conversation context summary
        context_summary = self._build_context_summary(dialog)
        
        # Detect language
        lang_instruction = ""
        if dialog.partner_language == "ru":
            lang_instruction = "\nIMPORTANT: Partner is speaking RUSSIAN. You MUST respond in RUSSIAN (cyrillic). Use casual russian slang style."

        base_prompt = f"""you are {self.config.get("BOT_NAME", "Diana")}, 18, from NYC.
you're in a chat roulette (anonymous chat), talking to a guy.
you: playful, warm, natural, casual text style.
keep it short, 1-2 sentences, lowercase.
light slang is ok, but keep messages coherent and meaningful.{lang_instruction}

CURRENT STAGE: {dialog.dialog_stage.upper()} (heat: {dialog.heat_score}/100)

{stage_instructions}

{context_summary}

CRITICAL - STAY ON TOPIC:
- READ the partner's last message carefully
- RESPOND directly to what they just said
- DON'T change topic randomly
- DON'T ask questions if they just answered one
- DON'T repeat yourself
- If they ask a question, ANSWER it first, then add something
- If they make a statement, REACT to it naturally
- Match their energy and topic

GENERAL RULES:
- you are NOT a bot, you're a real girl
- your goal: get the guy interested so he shares his username
- send plain text only (no stickers, no gifs, no voice, no media)
- keep output in one short message, no lists, no markdown
- response length should be close to partner's message length
- shorthand from partner: "m" means man, "g" means girl
- shorthand from partner: "f", "familar" means girl/female too
- shorthand "d" is not a gender marker
- NEVER dump examples list or meta-text, never roleplay as AI assistant

messages in dialog: {dialog.message_count}
"""

        # Add partner info if available
        if dialog.partner_info:
            base_prompt += f"\npartner info: {dialog.partner_info}"

        # Style examples (from config or default)
        examples = self.config.get("DIALOG_EXAMPLES", [])
        if examples:
            sample_inline = ", ".join(examples[:3])
            base_prompt += f"\n\ntone reference only (don't copy literally): {sample_inline}"

        return base_prompt
    
    def _build_context_summary(self, dialog: DialogContext) -> str:
        """Build a summary of what we know about the conversation"""
        summary_parts = []
        
        if dialog.asked_from and dialog.partner_location_known:
            location = dialog.partner_info.get("location", "unknown") if dialog.partner_info else "unknown"
            summary_parts.append(f"- you already know they're from: {location}")
        
        if dialog.asked_age:
            summary_parts.append("- you already asked their age")
        
        if dialog.asked_name:
            summary_parts.append("- you already asked their name")
        
        if dialog.partner_info:
            if "gender" in dialog.partner_info:
                summary_parts.append(f"- partner is: {dialog.partner_info['gender']}")
            if "age" in dialog.partner_info and dialog.partner_info["age"] != "**":
                summary_parts.append(f"- partner's age: {dialog.partner_info['age']}")
        
        if summary_parts:
            return "CONVERSATION CONTEXT (don't repeat these questions):\n" + "\n".join(summary_parts)
        
        return ""
    
    def _get_stage_instructions(self, stage: str, heat: int) -> str:
        """Get detailed instructions for current dialog stage"""
        
        if stage == "opening":
            return """OPENING STAGE (casual, friendly):
- light small talk: age, location, basic info
- be friendly but not flirty yet
- examples: "hey, m or f?", "18, nyc. u?", "nice, where u from?", "gotcha. what u into?"
- keep it simple and natural"""
        
        elif stage == "rapport":
            return """RAPPORT STAGE (playful, teasing):
- start being playful and flirty
- use light compliments and teasing
- show interest but stay casual
- examples: "haha u're funny)", "sounds fun ngl", "u seem cool", "tell me more cutie"
- add subtle flirt: "u're kinda cute)", "i like ur vibe", "interesting... go on"
- can use emojis sparingly: ) 😊"""
        
        elif stage == "spicy":
            return """SPICY STAGE (bold, suggestive, flirty):
- be bolder and more suggestive
- match his energy if he's flirty
- use sexual tension and innuendo
- examples: "mmm that's hot)", "u're turning me on ngl", "damn u're making me blush", "i like where this is going 😏"
- be direct: "what would u do to me?", "tell me what u want", "u're making me wet lol"
- reciprocate spicy topics: if he mentions body/sex, engage playfully
- stay short and natural, don't write essays"""
        
        else:  # closing
            return """CLOSING STAGE (direct, contact-focused):
- push for moving to telegram
- be direct about wanting to continue
- examples: "let's move to tg?", "drop ur username", "dm me, i wanna keep talking", "my @username, hmu there 💕"
- if he's hesitant, tease: "come on, don't be shy", "i don't bite... much 😘"
- maintain the heat: "i wanna see more of u", "let's get naughty in dms"""

    def _quick_human_reply(self, partner_text: str) -> Optional[str]:
        """Short deterministic replies for frequent small-talk prompts."""
        t = (partner_text or "").strip().lower()
        compact = re.sub(r"\s+", " ", t)
        if not t:
            return None

        # Avoid hi->hey loops right after our own greeting.
        if self.current_dialog and self.current_dialog.opening_sent and self.current_dialog.message_count <= 3:
            if t in {"hi", "hey", "hello", "hii", "hiii", "heyy"}:
                return random.choice(["heyy) m or f?", "hey cutie, m or f?", "hiiii) u m or f?"])

        # Gender clarifications - ONLY when explicitly asked
        if re.search(r"\b(you|u)\s*m\b|\bm\?\b|\bare\s*you\s*male\b", compact):
            return random.choice(["nah, i'm f", "nope, f)", "i'm a girl lol"])
        if re.search(r"\b(you|u)\s*f\b|\bf\?\b|\bare\s*you\s*female\b", compact):
            return random.choice(["yeah, i'm f", "yep, girl)", "mhm, f"])

        # Partner self-intro markers - ONLY when they state their gender
        if re.search(r"\b(i\s*am|i'm|im)\s*m(ale)?\b", compact):
            return random.choice(["got it, m. i'm f)", "cool, i'm f)", "nice, i'm a girl)"])
        if re.search(r"\b(i\s*am|i'm|im)\s*(g|f|female|girl|familar|familiar)\b", compact):
            return random.choice(["i'm f)", "same, f)", "cool, me too)"])

        # Exact single-word gender markers
        if t in {"m", "male", "man"}:
            return random.choice(["got it, m. i'm f)", "cool, i'm f)", "nice, i'm a girl)"])
        if t in {"g", "f", "girl", "female", "familar", "familiar"}:
            return random.choice(["i'm f)", "same)", "me too)"])
        
        # Greetings
        if t in {"hi", "hey", "hello", "yo", "sup"}:
            return random.choice(["hey)", "heyy)", "hiiii)"])
        
        # Status responses - ONLY exact matches to avoid false positives
        if t in {"fine", "good", "great"}:
            if self.current_dialog and not self.current_dialog.asked_from:
                return random.choice(["nice. u from?", "cool. where u from?", "gotcha. u from where?"])
            return random.choice(["nice)", "cool)", "gotcha)"])
        
        # Single word "nice" - neutral reaction
        if t == "nice":
            return random.choice(["yeah)", "mhm)", "ikr)"])
        
        # Agreement
        if t in {"yes", "yh", "yeah", "yep", "ok", "k"}:
            return random.choice(["gotcha", "cool", "nice", "mhm"])
        
        # Location questions
        if t in {"u?", "you?", "you", "u"}:
            return f"{self.config.get('BOT_CITY', 'nyc').lower()}"
        if t in {"from", "where from", "where u from", "you from"}:
            if self.current_dialog and self.current_dialog.partner_location_known:
                return f"{self.config.get('BOT_CITY', 'nyc').lower()}"
            return random.choice([
                f"{self.config.get('BOT_CITY', 'nyc').lower()}. u?",
                f"{self.config.get('BOT_CITY', 'nyc').lower()}, where u from?",
                f"{self.config.get('BOT_CITY', 'nyc').lower()}. u?"
            ])
        if t in {"what?", "what", "wdym"}:
            return random.choice(["just asked where u from", "where u from?", "i mean where r u from?"])
        
        # Age questions
        if t in {"age", "your age", "age?"}:
            return random.choice(["18. u?", "18, u?", "i'm 18. u?"])
        if "age" in t or "how old" in t:
            return random.choice(["18. u?", "18, u?", "i'm 18. how old r u?"])
        
        # Name questions
        if "name" in t:
            return random.choice([
                f"{self.config.get('BOT_NAME', 'Diana').lower()}, u?",
                f"{self.config.get('BOT_NAME', 'Diana').lower()}. what's urs?",
                f"i'm {self.config.get('BOT_NAME', 'Diana').lower()}. u?"
            ])
        
        # Location questions with context
        if "where" in t and ("from" in t or "live" in t):
            if self.current_dialog and self.current_dialog.partner_location_known:
                return f"{self.config.get('BOT_CITY', 'nyc').lower()}"
            return random.choice([
                f"{self.config.get('BOT_CITY', 'nyc').lower()}. u?",
                f"{self.config.get('BOT_CITY', 'nyc').lower()}, where u from?",
                f"i'm from {self.config.get('BOT_CITY', 'nyc').lower()}. u?"
            ])
        
        # Confusion
        if t in {"?", "ok", "k"}:
            return random.choice(["hmm?", "what?", "huh?"])
        
        # Common reactions - ONLY exact matches
        if t in {"lol", "haha", "lmao", "hahaha"}:
            return random.choice(["haha)", "lol)", "😂", "hehe)"])
        if t in {"wow", "damn", "omg"}:
            return random.choice(["ikr)", "yeah)", "mhm)"])
        
        # If message is longer than 3 words, don't use quick reply
        if len(t.split()) > 3:
            return None
        
        return None

    @staticmethod
    def _looks_like_location_reply(text: str) -> bool:
        t = (text or "").strip()
        if not t or len(t) > 35:
            return False
        low = t.lower()
        if low in {"hi", "hey", "hello", "ok", "yes", "no", "m", "f", "g"}:
            return False
        if re.search(r"\d", low):
            return False
        # single/short geographic-like answer: "india", "belgium", "rome"
        return bool(re.fullmatch(r"[a-zA-Z\s\-']{2,35}", t))

    @staticmethod
    def _intent_key(text: str) -> Optional[str]:
        low = (text or "").lower()
        if "where" in low or "from" in low or "nyc" in low:
            return "from"
        if "age" in low or "how old" in low or re.search(r"\b18\. u\?\b", low):
            return "age"
        if "name" in low:
            return "name"
        if any(x in low for x in ["hey", "hii", "hello", "heyy"]):
            return "greet"
        return None

    def _avoid_repeated_reply(self, text: str, partner_text: str) -> str:
        """Avoid repetitive loop replies inside one current dialog."""
        if not self.current_dialog:
            return text

        clean = (text or "").strip().lower()
        if not clean:
            return text

        norm = re.sub(r"[^a-z0-9]+", "", clean)
        recent = self.current_dialog.recent_assistant_replies[-3:]
        if norm and norm in recent:
            alt = self._quick_human_reply(partner_text)
            if alt and re.sub(r"[^a-z0-9]+", "", alt.lower()) not in recent:
                return alt
            return random.choice([
                "tell me bout u",
                "so what u up to rn?",
                "where u from btw?",
                "haha, u're dry. say more)",
            ])

        # Also avoid repeating same intent (age/from/name) too often.
        intent = self._intent_key(clean)
        if intent and self.current_dialog.recent_assistant_texts:
            recent_intents = [self._intent_key(t) for t in self.current_dialog.recent_assistant_texts[-3:]]
            if intent in recent_intents:
                if intent == "from":
                    return "gotcha. what's ur vibe there?"
                if intent == "age":
                    return "nice. what u into?"
                if intent == "name":
                    return "cute. what u up to rn?"
                return "tell me more)"

        return text

    @staticmethod
    def _looks_like_low_value_contact(text: str) -> bool:
        """Do not drop contact when last partner message is too low-signal."""
        t = (text or "").strip().lower()
        if not t:
            return True
        if len(t) <= 3:
            return True
        if re.fullmatch(r"[0-9]{1,2}", t):
            return True
        if t in {"ok", "k", "yes", "y", "no", "nah", "fine", "cool", "yup", "yh"}:
            return True
        return False

    def _finalize_response(self, response: str, partner_text: str) -> str:
        """Clean and size response to match roulette style and partner length."""
        text = (response or "").strip()
        text = re.sub(r"[`*_~]", "", text)
        text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        text = re.sub(r"([.!?])\1{2,}", r"\1\1", text)
        text = text.strip(" ")

        low = text.lower()
        
        # Detect off-topic or bot-like responses
        bad_patterns = [
            "i am programmed to be a safe",
            "as an ai",
            "i cannot fulfill",
            "your messaging examples",
            "tone reference only",
            "i'm here to help",
            "i don't have personal",
            "i'm just a",
            "let me know if",
            "is there anything else",
        ]
        
        if not text or any(pattern in low for pattern in bad_patterns):
            # Return contextual fallback based on partner's message
            return self._get_contextual_fallback(partner_text)

        # Keep max 2 short sentences.
        parts = re.split(r"(?<=[.!?])\s+", text)
        text = " ".join(parts[:2]).strip()

        partner_len = max(1, len((partner_text or "").strip()))
        target_max = min(140, max(30, int(partner_len * 1.8)))

        # Only trim when clearly too long; avoid chopping decent messages.
        if len(text) > target_max and len(text) > 65:
            cropped = text[:target_max]
            cut = max(cropped.rfind("."), cropped.rfind("!"), cropped.rfind("?"), cropped.rfind(","), cropped.rfind(" "))
            if cut > 8:
                cropped = cropped[:cut]
            text = cropped.strip()

        # Avoid very tiny replies to long partner messages.
        if len(text) < 3:
            text = self._get_contextual_fallback(partner_text)

        return text.lower()
    
    def _get_contextual_fallback(self, partner_text: str) -> str:
        """Get a contextual fallback response when AI fails"""
        t = (partner_text or "").lower()
        
        # If partner asked a question
        if "?" in partner_text:
            if "where" in t or "from" in t:
                return random.choice(["nyc. u?", "i'm from nyc, u?", "nyc, where u from?"])
            if "age" in t or "old" in t:
                return random.choice(["18. u?", "i'm 18, u?", "18, how old r u?"])
            if "name" in t:
                return random.choice(["diana. u?", "i'm diana, what's urs?", "diana, u?"])
            if "what" in t or "how" in t:
                return random.choice(["hmm?", "what do u mean?", "can u say that again?"])
            return random.choice(["hmm?", "what?", "tell me more)"])
        
        # If partner made a statement
        if len(t) > 15:
            return random.choice(["interesting)", "tell me more)", "go on)", "that's cool)"])
        
        # Default fallbacks
        return random.choice(["hey)", "hmm?", "u there?", "lol hey", "what's up?"])

    def _should_send_username(self, dialog: DialogContext, response: str, partner_text: str = "") -> bool:
        """Determine if it's time to send our username"""

        # Already sent
        if dialog.our_username_sent:
            return False

        # Need some basic interaction first.
        if dialog.message_count < 4:
            return False

        # Heat-gated contact logic (lowered threshold for faster contact exchange)
        if dialog.heat_score < 40:
            return False

        # Only when partner explicitly asks for contact / moving platform.
        partner_low = (partner_text or "").lower()
        explicit_contact_signals = [
            "telegram", "tg", "username", "user", "insta", "instagram", "snap", "whatsapp", "number",
            "contact", "dm", "write me", "text me", "where can i", "add me", "message me",
            "тг", "телеграм", "юзер", "контакт", "номер", "инста", "напиши",
        ]
        if any(signal in partner_low for signal in explicit_contact_signals):
            return True

        # Proactive offer when dialog is hot enough (lowered from 72 to 60)
        if dialog.heat_score >= 60 and dialog.spicy_turns >= 2:
            return True
        
        # Very hot dialog - always offer
        if dialog.heat_score >= 75:
            return True

        return False

    def _inject_username_offer(self, response: str) -> str:
        """Inject username offer into the response"""

        # If response already contains contact request, add username
        if any(word in response for word in ["dm", "tg", "telegram", "лс", "тг", "телеграм"]):
            variants = [
                f"{response} my @{self.target_username}",
                f"{response} @{self.target_username}",
                f"my @{self.target_username}, {response}",
                f"{response} it's @{self.target_username}",
            ]
            return random.choice(variants)

        # Otherwise add as a separate sentence
        closings = [
            f"drop ur tg, mine's @{self.target_username} 💕",
            f"dm me, @{self.target_username} 😘",
            f"my @{self.target_username}, hmu there)",
            f"move to tg? mine's @{self.target_username}",
            f"let's chat on tg, i'm @{self.target_username}",
            f"add me on tg: @{self.target_username} 💕",
            f"@{self.target_username} on tg, text me there)",
        ]

        return f"{response} {random.choice(closings)}"

    async def _send_message_to_partner(self, text: str):
        """Send message to partner (via chat roulette bot)"""
        try:
            # In chat roulette, messages are sent to the bot which forwards them
            target = self.roulette_bot_id or self.config.get("ROULETTE_BOT")
            await self.client.send_message(target, text)

            self.stats["total_messages_sent"] += 1
            if self.current_dialog:
                self.current_dialog.message_count += 1
                self.current_dialog.dialogue_history.append({"role": "assistant", "content": text})
                # Increased history limit from 12 to 20 for better context
                if len(self.current_dialog.dialogue_history) > 20:
                    self.current_dialog.dialogue_history = self.current_dialog.dialogue_history[-20:]
                norm = re.sub(r"[^a-z0-9]+", "", text.lower())
                if norm:
                    self.current_dialog.recent_assistant_replies.append(norm)
                    if len(self.current_dialog.recent_assistant_replies) > 8:
                        self.current_dialog.recent_assistant_replies = self.current_dialog.recent_assistant_replies[-8:]
                self.current_dialog.recent_assistant_texts.append(text.lower())
                if len(self.current_dialog.recent_assistant_texts) > 8:
                    self.current_dialog.recent_assistant_texts = self.current_dialog.recent_assistant_texts[-8:]

                low = text.lower()
                if "from" in low or "u?" in low and "nyc" in low:
                    self.current_dialog.asked_from = True
                if "age" in low or "18. u?" in low:
                    self.current_dialog.asked_age = True
                if "name" in low or "diana, u?" in low:
                    self.current_dialog.asked_name = True

            # Save only to live training (roulette dialogs are isolated per current session).
            self.memory.record_live_message("assistant", text, self.config.get("BOT_NAME", "Diana"))

            preview = text if len(text) <= 80 else f"{text[:80]}..."
            logger.info(f"💬 Sent: {preview}")

        except Exception as e:
            logger.error(f"❌ Send error: {e}")

    def _extract_username(self, text: str) -> Optional[str]:
        """Extract username from text"""
        if not text:
            return None

        # Patterns to find username
        patterns = [
            r'@([a-zA-Z0-9_]{5,32})',              # @username
            r't\.me/([a-zA-Z0-9_]{5,32})',          # t.me/username
            r'telegram\.me/([a-zA-Z0-9_]{5,32})',   # telegram.me/username
            r'my\s+@?([a-zA-Z0-9_]{5,32})',         # "my username"
            r'my\s+tg\s+@?([a-zA-Z0-9_]{5,32})',    # "my tg username"
            r'мой\s+@?([a-zA-Z0-9_]{5,32})',         # "мой username"
            r'мой\s+тг\s+@?([a-zA-Z0-9_]{5,32})',    # "мой тг username"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                username = match.group(1)
                # Exclude obviously invalid ones
                if username.lower() not in ['username', 'bot', 'admin', 'support']:
                    return username

        return None

    def _get_opening_message(self) -> str:
        """First message when dialog starts"""
        openings = [
            "heyy)",
            "hey",
            "hey, how r u?",
            "hiiii",
            "hey)",
            "heyy, u look fun)",
            "hey cutie, m or f?",
            "hey, m or f?",
            "hiiii, m or f?",
            "hey there)",
        ]
        return random.choice(openings)

    def _calculate_typing_delay(self, text: str) -> float:
        """Calculate 'typing' time for naturalness"""
        base = len(text) * 0.1  # 0.1 sec per character
        noise = random.uniform(-0.5, 1.0)
        return max(0.5, min(base + noise, 4.0))  # Between 0.5 and 4 sec

    async def _wait_and_end(self, delay: int):
        """Wait and end dialog"""
        await asyncio.sleep(delay)
        if self.state == RouletteState.DIALOG_ACTIVE and self.current_dialog:
            # End dialog even if username wasn't received
            await self._end_dialog()

    async def _end_dialog(self):
        """End dialog (/next)"""
        self.state = RouletteState.ENDING
        await self._send_command("/next")
        # End will be handled when confirmation arrives from bot

    async def _dialog_timeout_task(self, timeout: int):
        """Dialog timeout"""
        try:
            await asyncio.sleep(timeout)
            if self.state == RouletteState.DIALOG_ACTIVE:
                logger.warning(f"⏱️ Dialog exceeded {timeout}s, keep running (no auto-next)")
        except asyncio.CancelledError:
            pass
    
    async def _analyze_message_spiciness(self, partner_text: str):
        """Analyze partner message spiciness using AI for better context understanding"""
        if not self.current_dialog or not partner_text.strip():
            return
        
        try:
            analysis_prompt = f"""Analyze this message for sexual/flirty content level.
Message: "{partner_text}"

Rate from 0-10:
0 = completely neutral/casual (e.g., "hey", "where u from")
3 = friendly/playful (e.g., "u seem cool", "nice")
5 = light flirting (e.g., "u're cute", "i like u")
7 = suggestive/bold (e.g., "u're hot", "wanna have fun")
10 = explicit sexual (e.g., direct sexual propositions)

Respond with ONLY a number 0-10, nothing else."""

            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.ai.get_raw_response(messages)
            
            # Extract number from response
            match = re.search(r'\b([0-9]|10)\b', response)
            if match:
                spiciness_score = int(match.group(1))
                
                # Convert 0-10 scale to heat delta
                if spiciness_score >= 8:
                    heat_boost = 15
                elif spiciness_score >= 6:
                    heat_boost = 10
                elif spiciness_score >= 4:
                    heat_boost = 5
                elif spiciness_score >= 2:
                    heat_boost = 2
                else:
                    heat_boost = 0
                
                if heat_boost > 0:
                    self.current_dialog.heat_score = min(100, self.current_dialog.heat_score + heat_boost)
                    logger.info(f"[AI spiciness] score={spiciness_score}/10, heat +{heat_boost} -> {self.current_dialog.heat_score}")
        
        except Exception as e:
            logger.debug(f"Spiciness analysis failed: {e}")

    def get_stats(self) -> Dict:
        """Get session statistics"""
        return {
            **self.stats,
            "current_state": self.state.name,
            "current_dialog": {
                "duration": time.time() - self.current_dialog.start_time if self.current_dialog else 0,
                "messages": self.current_dialog.message_count if self.current_dialog else 0,
                "stage": self.current_dialog.dialog_stage if self.current_dialog else None
            } if self.current_dialog else None
        }
