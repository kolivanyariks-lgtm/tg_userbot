# Telegram UserBot - Deployment Guide for Railway

## 🚀 Quick Start

### 1. Create Session Locally

First, you need to authorize with Telegram on your local machine:

```bash
# Install dependencies
pip install -r requirements.txt

# Run bot locally (will ask for Telegram code)
python run_polling.py
```

Telegram will ask for:
- Phone number (already in .env)
- Confirmation code (from SMS/Telegram app)
- 2FA password (if enabled)

After successful login, file `data/userbot_session.session` will be created.

### 2. Encode Session for Railway

Run the helper script:

```bash
python encode_session.py
```

This will:
- Read `data/userbot_session.session`
- Encode it to base64
- Save to `session_b64.txt`
- Print the value to copy

**Alternative (manual):**

Windows PowerShell:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("data\userbot_session.session")) | Set-Clipboard
```

Linux/Mac:
```bash
base64 data/userbot_session.session | pbcopy
```

### 3. Configure Railway

1. Go to Railway Dashboard → Your Project
2. Click **Variables** tab
3. Add these environment variables:

**Required:**
```
API_ID=12345678
API_HASH=your_api_hash_here
PHONE_NUMBER=+375291234567
OPENROUTER_API_KEY=sk-or-v1-your-key-here
SESSION_B64=<paste base64 from step 2>
TARGET_USERNAME=your_telegram_username
ROULETTE_BOT=anonymous_chat_bot
```

**Optional:**
```
AI_MODEL=meta-llama/llama-3.3-70b-instruct:free
BOT_NAME=Diana
BOT_AGE=18
BOT_CITY=NYC
DATA_DIR=/tmp/data
LOG_LEVEL=INFO
```

### 4. Deploy

Railway will automatically:
- Detect `Procfile` or `railway.toml`
- Install dependencies from `requirements.txt`
- Restore session from `SESSION_B64`
- Start the bot with `python run_polling.py`

### 5. Check Logs

In Railway dashboard:
- Go to **Deployments** tab
- Click on latest deployment
- View logs to see:
  - `✅ Session restored from env`
  - `✅ Connected!`
  - `🎰 Chat roulette manager ready`

---

## 🔧 Troubleshooting

### "Session file not found"
- Make sure `SESSION_B64` variable is set in Railway
- Check that base64 string is complete (no line breaks)

### "API_ID not set"
- Add all required environment variables in Railway dashboard

### "Connection timeout"
- Railway might be blocking Telegram API
- Try using a different region in Railway settings

### Bot keeps restarting
- Check logs for errors
- Make sure `DATA_DIR=/tmp/data` is set (Railway uses ephemeral storage)

---

## 📁 Project Structure

```
telegram_userbot/
├── bot/
│   ├── ai_client.py          # AI integration (OpenRouter)
│   ├── chat_roulette/
│   │   └── manager.py        # Chat roulette automation
│   ├── config.py             # Configuration
│   ├── dialogue_memory.py    # Memory management
│   ├── handlers.py           # Message handlers
│   └── userbot_client.py     # Telegram client
├── data/                     # Local data (not deployed)
│   ├── userbot_session.session
│   └── captured_usernames.txt
├── run_polling.py            # Main entry point
├── encode_session.py         # Helper script
├── requirements.txt          # Python dependencies
├── .env.example              # Example config
└── README.md                 # This file
```

---

## 🔐 Security Notes

- **Never commit** `.env` or `data/userbot_session.session` to git
- Keep `SESSION_B64` secret (it's your Telegram account access)
- Use environment variables for all sensitive data
- On Railway, data in `/tmp` is ephemeral (deleted on restart)
- Captured usernames are saved to `/tmp/data/captured_usernames.txt`

---

## 📊 Monitoring

Check bot status:
- Railway logs show all bot activity
- Look for `🎉🎉🎉 GOT USERNAME: @username` messages
- Heat score and dialog stages are logged
- AI requests/responses are logged at INFO level

---

## 🛑 Stopping the Bot

Railway dashboard:
- Click **Stop** button to pause deployment
- Or delete the deployment entirely

The bot will:
- Send `/stop` to chat roulette
- Save any pending data
- Disconnect gracefully
