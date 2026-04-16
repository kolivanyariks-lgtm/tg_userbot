#!/usr/bin/env python3
"""
Start UserBot on server (webhook mode)
Usage: python run_server.py
"""
from server.webhook_server import run_server

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║              🤖 Telegram UserBot Server v2.0                 ║
║                                                              ║
║  Mode: Webhook + Polling                                     ║
║  Running on your account via Telethon                       ║
╚══════════════════════════════════════════════════════════════╝
    """)
    run_server()
