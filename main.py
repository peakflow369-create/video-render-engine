from fastapi import FastAPI, BackgroundTasks
import moviepy.editor as mp
import requests
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

app = FastAPI()
OUTPUT_FILE = "output.mp4"
FOLDER_ID = "1pylExuSqjHhAFiftEzWUoimRH8ry8sYk"

# Securely load credentials from Render Environment Variables
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

# Global state tracker for live monitoring
job_state = {
    "status": "IDLE",
    "message": "System online. Awaiting quest."
}

def upload_direct_to_drive(file_path):
    global job_state
    try:
        job_state["status"] = "UPLOADING"
        job_state["message"] = "Uploading processed video directly to Google Drive..."
        
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
        if not refresh_token:
            raise ValueError("GOOGLE_REFRESH_TOKEN is missing in Render environment variables.")

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES
        )
        
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': 'Solo_Leveling_Explanation.mp4',
            'parents': [FOLDER_ID]
        }
        media = MediaFileUpload(file_path, mimetype='video/mp4', resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # Make the uploaded file publicly readable via link
        service.permissions().create(
            fileId=file['id'],
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        link = file.get('webViewLink')
        job_state["status"] = "COMPLETED"
        job_state["message"] = f"Upload successful! Drive Link: {link}"
        return link
    except Exception as e:
        error_msg = f"Drive Upload Error: {e}"
        print(error_msg)
        job_state["status"] = "FAILED"
        job_state["message"] = error_msg
        return None

def process_and_upload(data):
    global job_state
    try:
        video_url = data.get("video_url")
        scenes = data.get("scenes", [])
        
        if not video_url:
            job_state["status"] = "FAILED"
            job_state["message"] = "Error: No video_url provided."
            return

        job_state["status"] = "DOWNLOADING"
        job_state["message"] = "Cloud-to-cloud downloading source video..."
        
        video_path = "input.mp4"
        r = requests.get(video_url, stream=True)
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        job_state["status"] = "RENDERING"
        job_state["message"] = "Starting FFmpeg scene cutting & editing..."
        
        video = mp.VideoFileClip(video_path)
        clips = []

        for scene in scenes:
            start = float(scene.get("start_time", 0))
            end = float(scene.get("end_time", video.duration))
            if start < video.duration and end <= video.duration and start < end:
                clips.append(video.subclip(start, end))

        if clips:
            final_video = mp.concatenate_videoclips(clips)
            final_video.write_videofile(
                OUTPUT_FILE, 
                codec="libx264", 
                audio_codec="aac",
                preset="fast",
                threads=4
            )
            print("Rendering completed! Uploading directly to Google Drive...")
            upload_direct_to_drive(OUTPUT_FILE)
        else:
            job_state["status"] = "FAILED"
            job_state["message"] = "Error: No valid clips found to render."
            
    except Exception as e:
        error_msg = f"Pipeline Error: {e}"
        print(error_msg)
        job_state["status"] = "FAILED"
        job_state["message"] = error_msg

@app.post("/render")
async def render_video(payload: dict, background_tasks: BackgroundTasks):
    global job_state
    job_state["status"] = "QUEUED"
    job_state["message"] = "Quest received. Initializing pipeline..."
    background_tasks.add_task(process_and_upload, payload)
    return {"status": "PROCESSING_STARTED", "message": "Video rendering and cloud upload initiated."}

@app.get("/status")
async def get_status():
    return job_state

@app.get("/")
async def root():
    return {"status": "Render Engine Online"}
    
