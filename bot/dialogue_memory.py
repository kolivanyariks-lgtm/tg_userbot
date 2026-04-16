"""
Dialogue Memory - memory management via text files
NO DATABASE - only .txt and .json files
"""
import os
import json
import re
import random
import time
import logging
from typing import List, Dict, Optional
from bot.config import Config

logger = logging.getLogger(__name__)


class DialogueMemory:
    """
    Class for managing dialogue memory
    All data stored in text files
    """
    
    def __init__(self):
        """Initialize dialogue memory"""
        # User contexts (in memory)
        self.user_contexts: Dict[int, List[Dict]] = {}
        
        # User stats (in memory)
        self.user_stats: Dict[int, Dict] = {}
        
        # Training examples (in memory)
        self.learned_examples: List[str] = []
        
        # File paths
        self.live_training_file = os.path.join(Config.DIALOGUES_DIR, "live_training.txt")
        self.contexts_file = os.path.join(Config.CONTEXTS_DIR, "contexts.json")
        self.stats_file = os.path.join(Config.CONTEXTS_DIR, "user_stats.json")
        
        # Create directories if needed
        Config.create_directories()
        
        # Load data from disk
        self._load_from_disk()
        self._load_dialogue_examples()
        
        logger.info("DialogueMemory initialized")
    
    def _load_from_disk(self):
        """Load saved data from files"""
        # Load contexts
        if os.path.exists(self.contexts_file):
            try:
                with open(self.contexts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert keys back to int
                    self.user_contexts = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self.user_contexts)} contexts")
            except Exception as e:
                logger.error(f"Error loading contexts: {e}")
                self.user_contexts = {}
        
        # Load stats
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert keys back to int
                    self.user_stats = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self.user_stats)} user stats")
            except Exception as e:
                logger.error(f"Error loading stats: {e}")
                self.user_stats = {}
    
    def _save_to_disk(self):
        """Save data to disk"""
        try:
            # Save contexts
            with open(self.contexts_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_contexts, f, ensure_ascii=False, indent=2)
            
            # Save stats
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_stats, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving to disk: {e}")
    
    def _load_dialogue_examples(self):
        """Load dialogue examples from all .txt files"""
        self.learned_examples = []
        
        if not os.path.exists(Config.DIALOGUES_DIR):
            logger.warning(f"Directory {Config.DIALOGUES_DIR} does not exist")
            return
        
        # Iterate through all .txt files in directory
        for filename in os.listdir(Config.DIALOGUES_DIR):
            if filename.endswith('.txt'):
                filepath = os.path.join(Config.DIALOGUES_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Parse dialogues from file
                        # Format: "Name, [date time]\nmessage text\n\n"
                        messages = self._parse_dialogue_file(content)
                        self.learned_examples.extend(messages)
                        
                    logger.info(f"Loaded file {filename}: {len(messages)} messages")
                    
                except Exception as e:
                    logger.error(f"Error reading file {filename}: {e}")
        
        logger.info(f"Total loaded {len(self.learned_examples)} examples")
    
    def _parse_dialogue_file(self, content: str) -> List[str]:
        """
        Parse dialogue file and return list of messages
        
        Args:
            content: File content
            
        Returns:
            List[str]: List of messages
        """
        messages = []
        
        # Split by pattern "Name, [date time]"
        # Support different delimiter formats
        parts = re.split(r'\n?[^,]+,\s*\[\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}\]\n', content)
        
        for part in parts:
            clean_part = part.strip()
            if len(clean_part) > 1:
                messages.append(clean_part)
        
        return messages
    
    def reset_user_memory(self, user_id: int):
        """
        Reset user memory (for /start command)
        
        Args:
            user_id: User ID
        """
        if user_id in self.user_contexts:
            self.user_contexts[user_id] = []
        
        # Reset trust to initial value
        self.user_stats[user_id] = {
            'trust': Config.INITIAL_TRUST,
            'mood': 'neutral',
            'last_interaction': time.time()
        }
        
        self._save_to_disk()
        logger.info(f"[RESET] User {user_id} forgotten. Trust: {Config.INITIAL_TRUST}")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        Get user statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Dict: User statistics
        """
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'trust': Config.INITIAL_TRUST,
                'mood': 'neutral',
                'last_interaction': time.time()
            }
        return self.user_stats[user_id]
    
    def update_trust(self, user_id: int, delta: int):
        """
        Update user trust level
        
        Args:
            user_id: User ID
            delta: Trust change (from -10 to 10)
        """
        stats = self.get_user_stats(user_id)
        
        # Apply multiplier for positive changes
        applied_delta = int(delta * 1.5) if delta > 0 else delta
        
        # Update trust with limits
        new_trust = stats['trust'] + applied_delta
        stats['trust'] = max(Config.MIN_TRUST, min(Config.MAX_TRUST, new_trust))
        stats['last_interaction'] = time.time()
        
        self._save_to_disk()
        
        # Nice scale in log
        self._print_trust_bar(user_id, stats['trust'], delta)
    
    def _print_trust_bar(self, user_id: int, trust: int, delta: int):
        """Print trust bar to log"""
        bar_len = 20
        filled = int((trust + 100) / 200 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        logger.info(f"Trust [{bar}] {trust}% (change: {delta:+d}) | User: {user_id}")
    
    def add_to_context(self, user_id: int, role: str, text: str, username: str = "User"):
        """
        Add message to user context
        
        Args:
            user_id: User ID
            role: Role ("user" or "assistant")
            text: Message text
            username: Username (for logs)
        """
        # Initialize context if needed
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        # Add message to context
        self.user_contexts[user_id].append({
            "role": role,
            "content": text
        })
        
        # Save to live_training.txt for training
        self._save_to_live_training(role, text, username)
        
        # Add to style examples
        self.learned_examples.append(text)
        
        # Limit context size
        max_context = Config.MAX_HISTORY * 2
        if len(self.user_contexts[user_id]) > max_context:
            self.user_contexts[user_id] = self.user_contexts[user_id][-max_context:]
        
        # Save to disk
        self._save_to_disk()
    
    def _save_to_live_training(self, role: str, text: str, username: str):
        """
        Save message to live_training.txt file
        
        Args:
            role: Role ("user" or "assistant")
            text: Message text
            username: Username
        """
        timestamp = time.strftime("%d.%m.%Y %H:%M")
        name = Config.BOT_NAME if role == "assistant" else username
        
        entry = f"{name}, [{timestamp}]\n{text}\n\n"
        
        try:
            with open(self.live_training_file, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Error writing to live_training: {e}")

    def record_live_message(self, role: str, text: str, username: str = "User"):
        """Append a message to live training without touching dialogue context."""
        if not text or not text.strip():
            return
        self._save_to_live_training(role, text.strip(), username)
        self.learned_examples.append(text.strip())
    
    def get_context(self, user_id: int) -> List[Dict]:
        """
        Get dialogue context for user
        
        Args:
            user_id: User ID
            
        Returns:
            List[Dict]: List of messages in {"role": ..., "content": ...} format
        """
        context = self.user_contexts.get(user_id, [])
        return [{"role": m["role"], "content": m["content"]} for m in context]
    
    def get_style_examples(self, limit: int = 15) -> str:
        """
        Get random messaging style examples
        
        Args:
            limit: Max number of examples
            
        Returns:
            str: Style examples for prompt
        """
        if not self.learned_examples:
            return "No examples."
        
        # Get random examples
        samples = random.sample(
            self.learned_examples, 
            min(len(self.learned_examples), limit)
        )
        
        return "\n---\n".join(samples)
    
    def clear_context(self, user_id: int) -> bool:
        """
        Clear user context (/clear command)
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if context was cleared
        """
        if user_id in self.user_contexts:
            self.user_contexts[user_id] = []
            self._save_to_disk()
            logger.info(f"[CLEAR] User {user_id} context cleared")
            return True
        return False
    
    def get_all_users(self) -> List[int]:
        """
        Get list of all users
        
        Returns:
            List[int]: List of user IDs
        """
        return list(self.user_stats.keys())
    
    def export_dialogue(self, user_id: int, filename: str = None) -> str:
        """
        Export dialogue with user to file
        
        Args:
            user_id: User ID
            filename: File name (optional)
            
        Returns:
            str: Path to saved file
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"dialogue_{user_id}_{timestamp}.txt"
        
        filepath = os.path.join(Config.DIALOGUES_DIR, filename)
        context = self.get_context(user_id)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Dialogue with user {user_id}\n")
                f.write(f"Export date: {time.strftime('%d.%m.%Y %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                
                for msg in context:
                    role = "🤖 Bot" if msg["role"] == "assistant" else "👤 User"
                    f.write(f"{role}:\n{msg['content']}\n\n")
            
            logger.info(f"Dialogue exported: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting dialogue: {e}")
            return None
