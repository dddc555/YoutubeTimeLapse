#!/usr/bin/env python3
import os
import time
import datetime
import requests
import subprocess
from pathlib import Path
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request


# =========================================================
# CONFIGURATION PARAMETERS
# =========================================================

SNAPSHOT_URL = "http://192.168.1.253/snapshot.cgi?stream=1&username=admin&password=123456"

INTERVAL_SECONDS = 10
TOTAL_SNAPSHOTS = 8640

WORKDIR = "/opt/timelapse"
VIDEO_TITLE = "Sky Timelapse"

CHUNK_SIZE = 2000
FRAMERATE = 30
RESOLUTION = "1280:720"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "/opt/timelapse/client_secret.json"
TOKEN_FILE = "/opt/timelapse/youtube_token.json"


# =========================================================
# OOB AUTHENTICATION (MANUAL COPY-PASTE CODE)
# =========================================================

def youtube_authenticate():
    """Authenticate via OOB flow and reuse token.json for refreshes."""
    creds = None

    # Load existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.valid:
            return build("youtube", "v3", credentials=creds)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return build("youtube", "v3", credentials=creds)

    print("\n===== FIRST-TIME AUTHORIZATION REQUIRED =====")

    # Manual OAuth OOB flow
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob"
    )

    auth_url, _ = flow.authorization_url(prompt="consent")

    print("\nOpen this URL in ANY browser:")
    print(auth_url)
    print("\nAfter approving, Google will give you a verification code.")
    code = input("Enter verification code here: ")

    # Exchange code for tokens
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Save token
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print("Authorization successful.\n")
    return build("youtube", "v3", credentials=creds)


# =========================================================
# SNAPSHOT CAPTURE
# =========================================================

def capture_snapshots():
    snapshot_dir = Path(WORKDIR) / "frames"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print("Starting snapshot capture...")
    for i in range(TOTAL_SNAPSHOTS):
        outfile = snapshot_dir / f"frame_{i:08d}.jpg"

        try:
            r = requests.get(SNAPSHOT_URL, timeout=10)
            if r.status_code == 200:
                with open(outfile, "wb") as f:
                    f.write(r.content)
                print(f"[{i+1}/{TOTAL_SNAPSHOTS}] Snapshot captured")
            else:
                print(f"[{i+1}/{TOTAL_SNAPSHOTS}] ERROR HTTP {r.status_code}")
        except Exception as e:
            print(f"[{i+1}/{TOTAL_SNAPSHOTS}] Snapshot error: {e}")

        time.sleep(INTERVAL_SECONDS)

    print("Snapshot capture complete.")


# =========================================================
# INCREMENTAL CHUNK ENCODING
# =========================================================

def encode_video():
    snapshot_dir = Path(WORKDIR) / "frames"
    chunks_dir = Path(WORKDIR) / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    frames = sorted(snapshot_dir.glob("frame_*.jpg"))
    total = len(frames)
    chunk_index = 0

    print("Encoding chunks...")

    for i in range(0, total, CHUNK_SIZE):
        chunk_frames = frames[i:i+CHUNK_SIZE]
        listfile = chunks_dir / f"chunk_{chunk_index:04d}.txt"

        with open(listfile, "w") as f:
            for frame in chunk_frames:
                f.write(f"file '{frame.absolute()}'\n")

        chunk_out = chunks_dir / f"chunk_{chunk_index:04d}.mp4"

        print(f"Encoding chunk {chunk_index} ({len(chunk_frames)} frames)...")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(listfile),
            "-r", str(FRAMERATE),
            "-vf", f"scale={RESOLUTION}:force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            str(chunk_out)
        ]

        subprocess.run(cmd, check=True)
        chunk_index += 1

    # Merge chunks
    merge_list = chunks_dir / "merge.txt"
    with open(merge_list, "w") as f:
        for i in range(chunk_index):
            f.write(f"file 'chunk_{i:04d}.mp4'\n")

    final_mp4 = Path(WORKDIR) / "timelapse_final.mp4"

    print("Merging final MP4...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(merge_list),
        "-c", "copy",
        str(final_mp4)
    ]
    subprocess.run(cmd, check=True)

    return final_mp4


# =========================================================
# CLEANUP
# =========================================================

def cleanup_snapshots_and_chunks():
    snapshot_dir = Path(WORKDIR) / "frames"
    chunks_dir = Path(WORKDIR) / "chunks"

    print("Cleaning up snapshots...")
    for f in snapshot_dir.glob("*"): 
        try: f.unlink()
        except: pass
    try: snapshot_dir.rmdir()
    except: pass

    print("Cleaning up chunks...")
    for f in chunks_dir.glob("*"): 
        try: f.unlink()
        except: pass
    try: chunks_dir.rmdir()
    except: pass


# =========================================================
# YOUTUBE UPLOAD
# =========================================================

def upload_to_youtube(filepath: Path):
    youtube = youtube_authenticate()

    today = datetime.date.today().isoformat()
    full_title = f"{VIDEO_TITLE} - {today}"

    body = {
        "snippet": {
            "title": full_title,
            "description": "Automatically generated timelapse",
            "categoryId": "22",
            "tags": ["timelapse"]
        },
        "status": {"privacyStatus": "public"}
    }

    media = MediaFileUpload(str(filepath), chunksize=8 * 1024 * 1024, resumable=True)

    print("Uploading to YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")

    print("Upload complete.")
    return True


# =========================================================
# MAIN WORKFLOW
# =========================================================

def main():
    work = Path(WORKDIR)
    work.mkdir(parents=True, exist_ok=True)

    final_mp4 = work / "timelapse_final.mp4"

    if final_mp4.exists():
        print("Found existing final MP4. Attempting re-upload...")
        try:
            if upload_to_youtube(final_mp4):
                final_mp4.unlink()
        except Exception as e:
            print("Upload failed again:", e)
        return

    capture_snapshots()
    final_mp4 = encode_video()
    cleanup_snapshots_and_chunks()

    try:
        if upload_to_youtube(final_mp4):
            final_mp4.unlink()
    except Exception as e:
        print("Upload failed — leaving MP4 for retry:", e)


if __name__ == "__main__":
    main()
