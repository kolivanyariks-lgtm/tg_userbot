# Simple Deployment Guide

## 🚀 Quick Deploy (3 steps)

### 1. Run Locally & Authorize
```bash
python run_polling.py
```
- Enter Telegram code when prompted
- Session saved to `data/userbot_session.session`

### 2. Commit Session to Git
```bash
git add data/userbot_session.session
git commit -m "Add Telegram session"
git push
```

### 3. Deploy to Railway
- Railway will use the committed session file
- No authorization needed on Railway
- Bot starts immediately

---

## 📁 Project Structure

```
telegram_userbot/
├── data/
│   └── userbot_session.session  ← Commit this!
├── bot/
├── run_polling.py
└── requirements.txt
```

---

## ⚙️ Railway Setup

**Environment Variables:**
```
API_ID=12345678
API_HASH=your_hash
PHONE_NUMBER=+1234567890
OPENROUTER_API_KEY=sk-or-v1-...
TARGET_USERNAME=your_username
ROULETTE_BOT=anonymous_chat_bot
```

**No need for:**
- ❌ SESSION_B64
- ❌ Volumes
- ❌ Interactive auth
- ❌ Railway Shell

Just push and deploy!

---

## 🔄 Updating Session

If session expires or you need to re-authorize:

1. Run locally: `python run_polling.py`
2. Commit: `git add data/userbot_session.session && git commit -m "Update session"`
3. Push: `git push`
4. Railway auto-deploys

---

## 🔐 Security Note

Session file contains your Telegram authorization. Keep your repo **private**!

- ✅ Private GitHub repo
- ✅ Session file committed
- ✅ Simple deployment
- ❌ Don't share repo publicly
