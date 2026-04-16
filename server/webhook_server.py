"""
Webhook Server - server for running UserBot on hosting
Supports webhook mode and health checks
"""
import os
import json
import asyncio
import logging
import ssl
from flask import Flask, request, jsonify
from threading import Thread
from bot.config import Config
from bot.userbot_client import SimpleUserBot

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global variable for bot client
bot_client = None
bot_task = None


class WebhookServer:
    """
    Server for running UserBot on hosting
    Supports webhook and health check endpoints
    """
    
    def __init__(self):
        self.app = Flask(__name__)
        self.bot = None
        self.bot_thread = None
        self.is_running = False
        
        # Register routes
        self._register_routes()
        
        logger.info("WebhookServer initialized")
    
    def _register_routes(self):
        """Register HTTP routes"""
        
        @self.app.route('/')
        def index():
            """Main page - bot info"""
            return jsonify({
                "status": "running" if self.is_running else "stopped",
                "bot_name": Config.BOT_NAME,
                "mode": Config.SERVER_MODE,
                "version": "2.0.0"
            })
        
        @self.app.route('/health')
        def health_check():
            """Health check endpoint for monitoring"""
            return jsonify({
                "status": "healthy",
                "bot_running": self.is_running,
                "timestamp": asyncio.get_event_loop().time()
            }), 200
        
        @self.app.route('/status')
        def status():
            """Detailed bot status"""
            if not self.bot:
                return jsonify({
                    "status": "not_initialized",
                    "message": "Bot not started yet"
                }), 503
            
            return jsonify({
                "status": "running" if self.is_running else "stopped",
                "bot_name": Config.BOT_NAME,
                "mode": Config.SERVER_MODE,
                "model": Config.AI_MODEL,
                "allowed_chats": len(Config.ALLOWED_CHATS),
                "blocked_chats": len(Config.BLOCKED_CHATS)
            })
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Webhook endpoint for external notifications"""
            data = request.get_json()
            logger.info(f"Webhook received: {data}")
            
            # Here you can handle external notifications
            # E.g. notifications from other services
            
            return jsonify({"status": "ok"}), 200
        
        @self.app.route('/restart', methods=['POST'])
        def restart():
            """Restart bot"""
            logger.info("Restart request received")
            
            # Stop bot
            self.stop_bot()
            
            # Start again
            self.start_bot()
            
            return jsonify({"status": "restarting"}), 200
        
        @self.app.route('/stats')
        def stats():
            """Bot statistics"""
            if not self.bot:
                return jsonify({"error": "Bot not running"}), 503
            
            try:
                users = self.bot.memory.get_all_users()
                return jsonify({
                    "total_users": len(users),
                    "users": users[:10]  # First 10 users
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    
    def start_bot(self):
        """Start bot in a separate thread"""
        if self.bot_thread and self.bot_thread.is_alive():
            logger.warning("Bot is already running")
            return
        
        def run_bot():
            """Function to run bot in thread"""
            global bot_client
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                bot_client = SimpleUserBot()
                self.bot = bot_client
                self.is_running = True
                
                logger.info("Starting bot in thread...")
                loop.run_until_complete(bot_client.start())
                
            except Exception as e:
                logger.error(f"Error in bot thread: {e}")
                self.is_running = False
        
        self.bot_thread = Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        
        logger.info("Bot thread started")
    
    def stop_bot(self):
        """Stop bot"""
        if self.bot:
            try:
                # Create new event loop for stopping
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.bot.client.disconnect())
                
                self.is_running = False
                logger.info("Bot stopped")
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")
    
    def run(self, host=None, port=None, ssl_context=None):
        """
        Run server
        
        Args:
            host: Server host
            port: Server port
            ssl_context: SSL context for HTTPS
        """
        host = host or Config.SERVER_HOST
        port = port or Config.WEBHOOK_PORT
        
        # Start bot
        self.start_bot()
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Start Flask
        self.app.run(
            host=host,
            port=port,
            ssl_context=ssl_context,
            debug=False,
            use_reloader=False
        )


# ==================== SIMPLIFIED STARTUP ====================

def create_ssl_context():
    """
    Create SSL context for HTTPS
    
    Returns:
        ssl.SSLContext or tuple: SSL context or (cert, key) paths
    """
    if Config.SSL_CERT and Config.SSL_KEY:
        if os.path.exists(Config.SSL_CERT) and os.path.exists(Config.SSL_KEY):
            return (Config.SSL_CERT, Config.SSL_KEY)
        else:
            logger.warning("SSL certificates not found, starting without HTTPS")
    
    return None


def run_server():
    """Run server with bot"""
    # Validate config
    if not Config.validate():
        return
    
    # Create directories
    Config.create_directories()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    # Create and start server
    server = WebhookServer()
    
    # Create SSL context if certificates available
    ssl_context = create_ssl_context()
    
    try:
        server.run(ssl_context=ssl_context)
    except KeyboardInterrupt:
        logger.info("Stop signal received")
        server.stop_bot()
    except Exception as e:
        logger.error(f"Critical server error: {e}")
        server.stop_bot()


# ==================== FOR GUNICORN ====================

def create_app():
    """
    Create Flask app for Gunicorn
    Usage: gunicorn -w 1 -b 0.0.0.0:8443 server.webhook_server:create_app()
    """
    # Validate config
    if not Config.validate():
        raise ValueError("Invalid configuration")
    
    Config.create_directories()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create server
    server = WebhookServer()
    
    # Start bot in separate thread
    server.start_bot()
    
    return server.app


if __name__ == '__main__':
    run_server()
