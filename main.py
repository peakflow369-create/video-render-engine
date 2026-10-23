from fastapi import FastAPI, BackgroundTasks
import moviepy.editor as mp
import requests
import os

app = FastAPI()

def process_video_task(data):
    try:
        video_url = data.get("video_url")
        scenes = data.get("scenes", [])
        
        # 1. Cloud-to-cloud download (Tera mobile data nahi lagega)
        video_path = "input.mp4"
        r = requests.get(video_url, stream=True)
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        video = mp.VideoFileClip(video_path)
        clips = []

        # 2. Cut clips based on AI JSON timestamps
        for scene in scenes:
            start = float(scene.get("start_time", 0))
            end = float(scene.get("end_time", video.duration))
            sub_clip = video.subclip(start, end)
            clips.append(sub_clip)

        if clips:
            final_video = mp.concatenate_videoclips(clips)
            final_video.write_videofile("output.mp4", codec="libx264", audio_codec="aac")
            
            # TODO: Upload 'output.mp4' to Google Drive "Final Edits" folder via API
            print("Rendering completed successfully!")
            
    except Exception as e:
        print(f"Error during rendering: {e}")

@app.post("/render")
async def render_video(payload: dict, background_tasks: BackgroundTasks):
    # Background task me dalne se n8n timeout nahi hoga
    background_tasks.add_task(process_video_task, payload)
    return {"status": "Rendering started in background successfully"}

@app.get("/")
async def root():
    return {"status": "Render Engine is Online!"}
  
