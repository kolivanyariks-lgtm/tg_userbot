# Railway Deployment - Session Size Fix

## Problem
Railway environment variables have a 32KB limit, but Telegram session files are often larger.

## Solutions

### ✅ Solution 1: Use Render.com (Recommended)
Render.com supports larger env vars (100KB+) with no issues.

### ✅ Solution 2: Railway Volume
Use Railway's persistent volume storage instead of env vars.

### ✅ Solution 3: Railway CLI
Upload session directly using Railway CLI.

---

## Quick Fix for Railway

### Option A: Railway CLI (5 minutes)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Link to your project
railway link

# 4. Create volume
railway volume create data --mount /data

# 5. Upload session
railway run bash -c "cat data/userbot_session.session > /data/userbot_session.session"

# 6. Set env var
railway variables set DATA_DIR=/data

# 7. Deploy
railway up
```

### Option B: Manual Volume Setup

1. **Railway Dashboard → Your Project → Settings → Volumes**
   - Click "New Volume"
   - Name: `data`
   - Mount path: `/data`
   - Size: 1GB

2. **Add environment variable:**
   ```
   DATA_DIR=/data
   ```

3. **Deploy (will fail first time - that's OK)**

4. **Railway Dashboard → Deployments → Click latest → Shell**
   ```bash
   mkdir -p /data
   # Paste your SESSION_B64 value and run:
   echo "PASTE_YOUR_SESSION_B64_HERE" | base64 -d > /data/userbot_session.session
   exit
   ```

5. **Redeploy** - now it works!

---

## Why This Happens

Telegram session files contain:
- Authorization keys
- Server info
- Encryption data

This can be 50-100KB when base64 encoded, exceeding Railway's 32KB limit.

---

## Recommended: Switch to Render.com

Render.com is better for this use case:
- ✅ Larger env var limit (100KB+)
- ✅ Easier setup
- ✅ Better logging
- ✅ Free tier available

Just use the same `SESSION_B64` approach - it will work without issues.
