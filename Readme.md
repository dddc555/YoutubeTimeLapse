# YouTube Timelapse Uploader  
Automated daily timelapse creator + uploader using Google OAuth **OOB (Out-of-band) flow**.

This project captures still images throughout the day, assembles them into a timelapse MP4, and uploads it to YouTube automatically. It is designed to run unattended on a Linux machine (Raspberry Pi, NUC, server, etc.).

## ✨ Features
- Uses **OOB OAuth** (because Device Flow no longer works for new Google Cloud apps).
- Automatically refreshes OAuth tokens.
- Generates a daily image timelapse.
- Uploads to YouTube from CLI without browser dependencies.
- Avoids overlap by recording **23-hour** intervals instead of 24.
- Supports chunk-based timelapse creation (e.g., 2–300 images per chunk).

---

## 📁 Project Structure (recommended)

project/\
├─ client_secret.json\
├─ token.json\
├─ images/\
│ └─ (your JPEG images collected throughout the day)\
├─ output/\
│ └─ final.mp4\
├─ timelapse.py\
├─ youtube_oauth_oob.py\
└─ README.md

---

## 🔐 Google Cloud Setup (OOB Auth)

### 1. Create OAuth Client
Google Cloud → APIs & Services → Credentials → **Create OAuth Client → Desktop App**

### 2. Download the JSON  
Click **Download JSON** and save it as:

client_secret.json

OOB no longer requires redirect URIs — Google auto-assigns `urn:ietf:wg:oauth:2.0:oob`.

### 3. Enable APIs
Enable:
- **YouTube Data API v3**
- **OAuth2 API**

---

## 🔑 First-Time Authentication (OOB)

Run:

python3 youtube_oauth_oob.py

This will output something like:

Please visit this URL:
https://accounts.google.com/o/oauth2/auth?....

Enter the code Google gives you:

Paste the code → press Enter → `token.json` is generated automatically.

---

## ▶️ Daily Operation

### 1. Collect images  
Your external script or camera system dumps `.jpg` images into:

images/

### 2. Run timelapse + upload script  

Example:

python3 timelapse.py

The script:

1. Loads images from `images/`
2. Creates timelapse in chunks (configurable)
3. Encodes final.mp4
4. Uploads to YouTube
5. Moves old images to archive or deletes them (optional)

---

## 🕒 Avoiding Overlap (Important)
To ensure uploads never overlap with the next day:

✔ Use a **23-hour capture window**  \
✔ Start the script at the same time daily  \
✔ No need for waits or cron padding  \
✔ Dark hours have no meaningful visual data anyway

We verified this is the simplest stable solution.

---

## 🛠 Requirements

pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client\
pip install opencv-python\
pip install requests

FFmpeg must be installed:

sudo apt install ffmpeg

---

## ⚙️ Configuration

Inside the script, you can adjust:

- CHUNK_SIZE = 200 # images per chunk
- FPS = 30 # video framerate
- IMAGE_DIR = "images"
- OUTPUT = "output/final.mp4"
- TITLE = "Daily Timelapse"
- DESCRIPTION = "Automatically generated timelapse."

---

## 📤 Uploading Behavior

- Token auto-refreshes through Google OAuth library  
- Upload resumes if interrupted  
- If final.mp4 exists and already uploaded, re-upload is attempted once  
- Any 401 invalid_grant errors → delete token.json and re-auth

---

## 🧪 Testing Auth Separately

You can run:

python3 youtube_oauth_oob.py --test

This checks that:
- client_secret.json is valid  
- token.json can refresh  
- YouTube API responds normally  

---

## 🔧 Resetting Authentication

If anything breaks:

rm token.json
python3 youtube_oauth_oob.py

Re-authenticate via OOB code again.

---

## 📝 Notes

- Device Flow is **retired** for new Google Cloud apps (as of 2022).  
- OOB Auth *does* still work for Desktop applications.  
- Uploads require `youtube.upload` scope.  
- Keep your client_secret.json private — **do not commit it to Git**.

---

## 📒 Changelog

### v1.0
- OOB OAuth implemented  
- Timelapse chunking  
- 23-hour window  
- Stable daily YouTube upload  
- Token auto-refresh  

---

## 🙋 Support

If you run into:
- 401 errors  
- unauthorized_client  
- invalid_grant  
- upload quota issues  

Just ping ChatGPT again and paste your logs.
