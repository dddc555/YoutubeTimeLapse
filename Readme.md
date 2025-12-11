✅ Install Dependencies (once) \
sudo apt update \
sudo apt install -y ffmpeg python3-pip \
pip3 install --user google-api-python-client google-auth google-auth-oauthlib requests

✅ Google YouTube API Setup (once) \
Create Google Cloud Project \
Enable YouTube Data API v3 \
Create OAuth Client ID (Desktop app) \
Download client_secret.json \
First run will open a browser to authorize; afterward it auto-refreshes.

✅ Make executable:
chmod +x timelapse_youtube.py

✅ Cron Job Example

Runs every minute:
* * * * * /usr/bin/python3 /var/timelapse/timelapse_youtube.py >> /var/log/timelapse.log 2>&1

✅ Behavior Summary
Scenario	Result
Snapshot fails	Retries, continues next run
Upload fails	MP4 kept, retried next run
Cron overlap	Prevented via lock file
Power outage	Safe, resumes cleanly
YouTube auth expires	Auto refresh
