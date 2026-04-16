"""
AI Client - works with OpenRouter API
Sends requests to the AI model and receives responses
"""
import os
import re
import aiohttp
import logging
from typing import Tuple, List, Dict
from bot.config import Config

logger = logging.getLogger(__name__)


class AIClient:
    """Client for working with AI via OpenRouter"""
    
    def __init__(self, memory):
        """
        Initialize AI client
        
        Args:
            memory: DialogueMemory object for memory management
        """
        self.api_key = Config.OPENROUTER_API_KEY
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.memory = memory
        self.model = Config.AI_MODEL
        
        logger.info(f"AI Client initialized. Model: {self.model}")
    
    async def get_response(self, user_id: int, user_text: str, chat_type: str = "private") -> str:
        """
        Get a response from AI
        
        Args:
            user_id: User ID
            user_text: User message text
            chat_type: Chat type (private, group, channel)
            
        Returns:
            str: Response from AI
        """
        try:
            # 1. Gather data from memory
            stats = self.memory.get_user_stats(user_id)
            trust = stats.get('trust', Config.INITIAL_TRUST)
            history = self.memory.get_context(user_id)
            
            # Get style examples from dialogues
            style_samples = self.memory.get_style_examples(Config.STYLE_EXAMPLES_COUNT)
            
            logger.info(f"[Request] User: {user_id} | Trust: {trust} | Chat: {chat_type}")
            
            # 2. Form mood based on trust level
            mood = self._get_mood_by_trust(trust)
            
            # 3. Create system prompt
            system_prompt = self._create_system_prompt(
                mood=mood,
                trust=trust,
                style_samples=style_samples,
                chat_type=chat_type
            )
            
            # 4. Build messages for API
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add last messages from history (max 6)
            if history:
                messages.extend(history[-6:])
            
            # Add current user message
            messages.append({"role": "user", "content": user_text})
            
            # 5. Build request payload
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": Config.TEMPERATURE,
                "max_tokens": Config.MAX_TOKENS
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": Config.WEBHOOK_URL or "https://localhost",
                "Content-Type": "application/json"
            }
            
            # 6. Send request to API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url, 
                    headers=headers, 
                    json=payload, 
                    timeout=30
                ) as resp:
                    
                    if resp.status != 200:
                        error_data = await resp.text()
                        logger.error(f"API error {resp.status}: {error_data}")
                        return "ugh, their server's down rn, hit me up later."
                    
                    result = await resp.json()
                    
                    if 'choices' not in result or not result['choices']:
                        logger.error(f"Empty response from OpenRouter: {result}")
                        return "lol idk what happened, say that again."
                    
                    raw_text = result['choices'][0]['message']['content']
                    
                    # 7. Parse SCORE and clean text
                    clean_text, delta = self._parse_score(raw_text)
                    
                    # 8. Update trust
                    self.memory.update_trust(user_id, delta)
                    
                    logger.info(f"[Response] Delta: {delta} | Text: {clean_text[:50]}...")
                    
                    return clean_text
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            return "ugh, connection is trash, try later."
        except Exception as e:
            logger.error(f"Critical error: {e}")
            return "omg smth glitched in my brain lol. write again."

    async def get_raw_response(self, messages: list) -> str:
        """
        Get raw response from AI for custom prompts (chat roulette)

        Args:
            messages: Full list of messages for API

        Returns:
            str: Response from AI
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": Config.TEMPERATURE,
                "max_tokens": Config.MAX_TOKENS
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": Config.WEBHOOK_URL or "https://localhost",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        self.url,
                        headers=headers,
                        json=payload,
                        timeout=30
                ) as resp:

                    if resp.status != 200:
                        error_data = await resp.text()
                        logger.error(f"API error {resp.status}: {error_data}")
                        return "ugh wtf, u still there?"

                    result = await resp.json()

                    if 'choices' not in result or not result['choices']:
                        return "hello?? why u ghosting"

                    return result['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"AI error: {e}")
            return "ugh connection died, write again"

    def _get_mood_by_trust(self, trust: int) -> str:
        """
        Get mood based on trust level
        
        Args:
            trust: Trust level (-100 to 100)
            
        Returns:
            str: Mood description
        """
        if trust > 70:
            return (
                "You're super flirty, raunchy, no filter whatsoever. "
                "You're really into this person, you want them bad. "
                "You use emojis 😘💕🔥, keep it short and playful. "
                "Your goal is to get their contact to keep things going outside the chat."
            )
        elif trust > 40:
            return (
                "You're flirty, playful, dropping hints about something more. "
                "You're enjoying flirting with this person."
            )
        elif trust > 10:
            return (
                "You're a bold, cheeky girl. "
                "You talk casually and directly, can tease a bit."
            )
        elif trust > -20:
            return (
                "You're neutral, a bit cold. "
                "Answering to the point, no extra emotions."
            )
        elif trust > -50:
            return (
                "You're irritated, sharp. "
                "Can tell them to f*** off if they're being annoying."
            )
        else:
            return (
                "You're a mean bitch, rude af, telling them to go to hell. "
                "You REALLY can't stand this person."
            )
    
    def _create_system_prompt(
        self, 
        mood: str, 
        trust: int, 
        style_samples: str,
        chat_type: str
    ) -> str:
        """
        Create system prompt for AI
        
        Args:
            mood: Character mood
            trust: Trust level
            style_samples: Messaging style examples
            chat_type: Chat type
            
        Returns:
            str: System prompt
        """
        # Base character info
        prompt = f"""You are {Config.BOT_NAME}, {Config.BOT_AGE} y/o, from {Config.BOT_CITY}.
You're a real girl chatting on Telegram.

YOUR CURRENT VIBE:
{mood}

"""
        
        # Add style examples
        if style_samples and style_samples != "No examples.":
            prompt += f"""YOUR MESSAGING STYLE (TAKE NOTES FROM THIS):
{style_samples}

"""
        
        # Add rules
        prompt += f"""CHAT RULES:
- Your trust level: {trust}/100
- Write ONLY in English
- Use lowercase (like texting), no formal shit
- Use profanity (wtf, omg, damn, hell, etc.) — it's part of your vibe
- Keep it short: 1-3 sentences max
- Do NOT offer help, do NOT act like a bot
- Be natural, like a real girl
- Can make typos sometimes (like u're typing fast)
- Use "...", "!!", "??" to show emotions
"""
        
        # Add SCORE rules
        prompt += """
TRUST CHANGE RULES (SCORE):
- If they insult you — SCORE from -7 to -10
- If they apologize and make up — SCORE from +2 to +7
- If they say nice things, compliments — SCORE up to +10 (but trust + score <= 60)
- If they flirt — SCORE from +5 to +10
- If they stop the spicy convo — SCORE from -5 to -10 (when trust > 60)
- If they act disrespectful — SCORE from -5 to -10

MANDATORY: At the very end of the message add the technical tag [SCORE: x] (where x is from -10 to 10).
Example: "omg hey, why u all up in my mentions? [SCORE: 0]"
"""
        
        # Extra rules for group chats
        if chat_type in ["group", "supergroup"]:
            prompt += """
THIS IS A GROUP CHAT:
- Only respond when someone addresses you by name or replies to your message
- Can be more reserved
- Don't flirt too openly in front of everyone
"""
        
        return prompt
    
    def _parse_score(self, text: str) -> Tuple[str, int]:
        """
        Parse [SCORE: x] from text and return clean text + value
        
        Args:
            text: Text from AI
            
        Returns:
            Tuple[str, int]: (clean text, score value)
        """
        if not text:
            return "...", 0
        
        # Look for pattern [SCORE: number]
        match = re.search(r'\[SCORE:\s*([+-]?\d+)\]', text, re.IGNORECASE)
        delta = int(match.group(1)) if match else 0
        
        # Remove tag from text
        clean_text = re.sub(r'\[SCORE:.*?\]', '', text, flags=re.IGNORECASE).strip()
        
        # If AI wrote SCORE as text without brackets
        clean_text = re.sub(r'score:?\s*[+-]?\d*', '', clean_text, flags=re.IGNORECASE).strip()
        
        # Strip quotes if any
        clean_text = clean_text.strip('"').strip("'")
        
        # If text is empty after cleanup
        if not clean_text:
            clean_text = "so u just gonna ghost me?"
        
        return clean_text, delta
