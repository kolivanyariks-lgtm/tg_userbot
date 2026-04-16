# Railway Interactive Authorization Guide

## 🎯 Easiest Way: Interactive Auth in Railway Shell

Instead of dealing with SESSION_B64, you can authorize directly on Railway!

---

## 📋 Step-by-Step Instructions

### 1. Deploy to Railway (First Time)

1. Push your code to GitHub
2. Connect Railway to your repo
3. Add environment variables (WITHOUT SESSION_B64):
   ```
   API_ID=12345678
   API_HASH=your_api_hash
   PHONE_NUMBER=+375291234567
   OPENROUTER_API_KEY=sk-or-v1-...
   TARGET_USERNAME=your_username
   ROULETTE_BOT=anonymous_chat_bot
   DATA_DIR=/data
   ```

4. Create a Volume:
   - Settings → Volumes → New Volume
   - Mount path: `/data`
   - Size: 1GB

5. Deploy (it will fail - that's OK!)

### 2. Run Interactive Auth

Open Railway Shell:
```bash
# In Railway Dashboard → Deployments → Latest → Shell
python auth_interactive.py
```

The script will:
1. ✅ Connect to Telegram
2. ✅ Send code to your phone
3. ✅ Ask you to enter the code
4. ✅ Ask for 2FA password (if enabled)
5. ✅ Save session to `/data/userbot_session.session`

**Example interaction:**
```
📱 Phone: +375291234567
🔑 API ID: 12345678

🔄 Connecting to Telegram...
📲 Sending code request...

============================================================
📬 Check your Telegram app for the confirmation code
============================================================

Enter the code you received: 12345

✅ Code accepted!

============================================================
✅ Successfully authorized as: John
   Username: @john_doe
   Phone: +375291234567
============================================================

💾 Session file created: /data/userbot_session.session
   Size: 45678 bytes

🎉 Authorization complete!

Next steps:
1. Session is saved in the volume
2. Restart your deployment
3. Bot will use the saved session
```

### 3. Restart Deployment

Railway Dashboard → Deployments → Restart

Bot will now start with the saved session!

---

## 🔧 Alternative: Railway CLI

If you prefer command line:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and link
railway login
railway link

# Run interactive auth
railway run python auth_interactive.py

# Follow the prompts to enter code

# Deploy
railway up
```

---

## 🆘 Troubleshooting

### "Cannot read input in Railway Shell"
Railway Shell supports interactive input! Just type the code when prompted.

### "Session file not found after restart"
Make sure:
- Volume is mounted at `/data`
- `DATA_DIR=/data` is set in environment variables
- Session was created in `/data/userbot_session.session`

### "Code expired"
Telegram codes expire after 5 minutes. Run `auth_interactive.py` again.

### "Invalid code"
Make sure you're entering the code from the correct Telegram account.

---

## ✅ Benefits of This Method

- ✅ No need to deal with base64 encoding
- ✅ No 32KB limit issues
- ✅ Direct authorization on Railway
- ✅ Session stays in persistent volume
- ✅ Works with 2FA

---

## 📝 Files Created

- `auth_interactive.py` - Interactive authorization script
- Session saved to: `/data/userbot_session.session`

This is the **recommended method** for Railway deployment!
