#!/usr/bin/env python3
import os
import sys
import time
import glob
import yaml
import shutil
import requests
import subprocess
from datetime import datetime
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)

def acquire_lock(lockfile):
    if os.path.exists(lockfile):
        print("Lock exists, exiting.")
        sys.exit(0)
    with open(lockfile, "w") as f:
        f.write(str(os.getpid()))

def release_lock(lockfile):
    if os.path.exists(lockfile):
        os.remove(lockfile)

def fetch_snapshot(url, path, timeout, retries):
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

def create_timelapse_mp4(workdir, prefix, fps, resolution):
    mp4_path = os.path.join(workdir, "timelapse.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob",
        "-i", f"{prefix}_*.jpg",
        "-s", resolution,
        "-pix_fmt", "yuv420p",
        mp4_path
    ]
    subprocess.check_call(cmd, cwd=workdir)
    return mp4_path

def get_youtube_service(creds_file, token_file):
    creds = None
    if os.path.exists(token_file):
        creds = google.auth.load_credentials_from_file(token_file, SCOPES)[0]
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_console()
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(youtube, mp4_path, title, description, privacy):
    req = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy}
        },
        media_body=MediaFileUpload(mp4_path, chunksize=-1, resumable=True)
    )
    req.execute()

def main():
    cfg = load_config()
    acquire_lock(cfg["system"]["lock_file"])

    try:
        wd = Path(cfg["working_dir"])
        wd.mkdir(parents=True, exist_ok=True)

        # Retry upload first
        mp4 = wd / "timelapse.mp4"
        if mp4.exists():
            yt = get_youtube_service(
                cfg["youtube"]["credentials_file"],
                cfg["youtube"]["token_file"]
            )
            title = f"{cfg['youtube']['title_base']} {datetime.now():%Y-%m-%d}"
            upload_to_youtube(
                yt, str(mp4), title,
                cfg["youtube"]["description"],
                cfg["youtube"]["privacy_status"]
            )
            mp4.unlink()
            return

        snaps = list(wd.glob(f"{cfg['snapshot_prefix']}_*.jpg"))
        snap_id = len(snaps) + 1

        snap_name = f"{cfg['snapshot_prefix']}_{snap_id:06d}.jpg"
        snap_path = wd / snap_name

        if fetch_snapshot(
            cfg["snapshot_url"],
            snap_path,
            cfg["network"]["snapshot_timeout"],
            cfg["network"]["snapshot_retries"]
        ):
            print(f"Saved {snap_name}")
        else:
            print("Snapshot failed")

        snaps = list(wd.glob(f"{cfg['snapshot_prefix']}_*.jpg"))
        if len(snaps) >= cfg["snapshots_per_video"]:
            mp4_path = create_timelapse_mp4(
                str(wd),
                cfg["snapshot_prefix"],
                cfg["video_fps"],
                cfg["video_resolution"]
            )
            for s in snaps:
                s.unlink()
            print("Timelapse created")

    finally:
        release_lock(cfg["system"]["lock_file"])

if __name__ == "__main__":
    main()
