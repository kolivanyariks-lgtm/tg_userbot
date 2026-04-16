# Using Existing Telegram Code

## 🎯 Quick Answer

You have **3 options** to provide the code:

### Option 1: Environment Variable (Best for Railway)

Add to Railway environment variables:
```
TELEGRAM_CODE=12345
```

Then run:
```bash
python auth_with_code.py
```

### Option 2: Interactive Input (Railway Shell)

```bash
railway shell
python auth_with_code.py
# Enter code when prompted: 12345
```

### Option 3: Railway CLI

```bash
railway run -e TELEGRAM_CODE=12345 python auth_with_code.py
```

---

## 📋 Full Instructions

### For Railway Dashboard:

1. **Get the code from Telegram** (check your messages)

2. **Add environment variable:**
   - Railway Dashboard → Variables
   - Add: `TELEGRAM_CODE=12345` (your actual code)
   - Optional: `TELEGRAM_2FA_PASSWORD=yourpassword` (if you have 2FA)

3. **Open Railway Shell:**
   - Deployments → Latest → Shell

4. **Run the script:**
   ```bash
   python auth_with_code.py
   ```

5. **Remove the variables after success:**
   - Delete `TELEGRAM_CODE` from Railway variables (for security)
   - Delete `TELEGRAM_2FA_PASSWORD` if you added it

6. **Restart deployment**

---

## ⚠️ Important Notes

- **Codes expire in 5 minutes** - use it quickly!
- **Remove TELEGRAM_CODE after use** - don't leave it in env vars
- If code expired, use `auth_interactive.py` to get a new one
- FloodWait is now over (19:53:29 passed), you can request new codes

---

## 🔐 Security

The code is temporary and only valid for a few minutes. After successful authorization:
1. Session is saved to `/data/userbot_session.session`
2. Remove `TELEGRAM_CODE` from environment variables
3. Bot will use the saved session for future runs

---

## 🆘 Troubleshooting

### "Code expired"
- Codes are valid for ~5 minutes
- Request a new one: `python auth_interactive.py`

### "Invalid code"
- Make sure you entered all digits correctly
- Check if you're using the latest code from Telegram

### "FloodWait"
- Wait time is over now (19:55+)
- You can safely request new codes
