#!/usr/bin/env python3
import os
import time
import datetime
import requests
import subprocess
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# =========================================================
# CONFIGURATION PARAMETERS
# =========================================================

SNAPSHOT_URL = "http://camera/snapshot.jpg"
INTERVAL_SECONDS = 10
TOTAL_SNAPSHOTS = 8640
WORKDIR = "/opt/timelapse"
VIDEO_TITLE = "Sky Timelapse"
CHUNK_SIZE = 2000                        # Number of frames per encoding chunk

# YouTube API parameters
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "/opt/timelapse/client_secret.json"  # Download from Google Cloud
TOKEN_FILE = "/opt/timelapse/youtube_token.json"


# =========================================================
# AUTHENTICATE YOUTUBE
# =========================================================

def youtube_authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_console()

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

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
            else:
                print(f"Failed to get snapshot {i}, HTTP {r.status_code}")
        except Exception as e:
            print(f"Snapshot error {i}: {e}")

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

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(listfile),
            "-r", "30",
            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            str(chunk_out)
        ]

        print("Encoding", chunk_out)
        subprocess.run(cmd, check=True)
        chunk_index += 1

    # Merge final
    merge_list = Path(WORKDIR) / "chunks" / "merge.txt"
    with open(merge_list, "w") as f:
        for i in range(chunk_index):
            f.write(f"file 'chunk_{i:04d}.mp4'\n")

    final_mp4 = Path(WORKDIR) / "timelapse_final.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(merge_list),
        "-c", "copy",
        str(final_mp4)
    ]

    print("Merging chunks...")
    subprocess.run(cmd, check=True)

    return final_mp4


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
            "tags": ["timelapse", "sky"],
            "categoryId": "22"
        },
        "status": {"privacyStatus": "public"}
    }

    media = MediaFileUpload(str(filepath), chunksize=1024*1024*8, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print("Uploading to YouTube...")

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload: {int(status.progress() * 100)}%")

    print("Upload complete.")
    return True


# =========================================================
# MAIN WORKFLOW
# =========================================================

def main():
    work = Path(WORKDIR)
    work.mkdir(parents=True, exist_ok=True)

    final_mp4 = work / "timelapse_final.mp4"

    # If previous run failed leaving MP4, attempt upload
    if final_mp4.exists():
        print("Found existing MP4. Attempting re-upload.")
        try:
            if upload_to_youtube(final_mp4):
                final_mp4.unlink()
        except Exception as e:
            print("Upload failed again:", e)
        return

    # 1. Capture frames
    capture_snapshots()

    # 2. Encode incremental chunks
    final_mp4 = encode_video()

    # 3. Clean frames
    snapshot_dir = Path(WORKDIR) / "frames"
    for f in snapshot_dir.glob("*"):
        f.unlink()
    snapshot_dir.rmdir()

    # 4. Try uploading
    try:
        if upload_to_youtube(final_mp4):
            final_mp4.unlink()
    except Exception as e:
        print("Upload failed — leaving MP4 for retry:", e)


if __name__ == "__main__":
    main()
