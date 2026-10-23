from fastapi import FastAPI, BackgroundTasks
import moviepy.editor as mp
import requests
import os

app = FastAPI()

def process_video_task(data):
    try:
        video_url = data.get("video_url")
        scenes = data.get("scenes", [])
        
        if not video_url:
            print("Error: No video_url provided in payload.")
            return

        # 1. Cloud-to-cloud download (Zero local mobile data consumed)
        video_path = "input.mp4"
        print(f"Downloading video from cloud: {video_url}")
        r = requests.get(video_url, stream=True)
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download completed. Starting video editing...")
        
        video = mp.VideoFileClip(video_path)
        clips = []

        # 2. Cut clips based on AI JSON timestamps
        for scene in scenes:
            start = float(scene.get("start_time", 0))
            end = float(scene.get("end_time", video.duration))
            
            # Safety check for timeline bounds
            if start < video.duration and end <= video.duration and start < end:
                sub_clip = video.subclip(start, end)
                clips.append(sub_clip)

        if clips:
            # 3. Concatenate and render final output
            final_video = mp.concatenate_videoclips(clips)
            output_path = "output.mp4"
            final_video.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac",
                preset="fast",
                threads=4
            )
            print("Rendering completed successfully!")
            
            # TODO: Add your Google Drive API upload function here 
            # to push 'output.mp4' directly to your "Final Edits" folder.
            
        else:
            print("Error: No valid clips found to render.")
            
    except Exception as e:
        print(f"Critical Error during rendering: {e}")

@app.post("/render")
async def render_video(payload: dict, background_tasks: BackgroundTasks):
    # Background task triggers rendering so n8n doesn't timeout
    background_tasks.add_task(process_video_task, payload)
    return {"status": "Rendering started in background successfully"}

@app.get("/")
async def root():
    return {"status": "Render Engine is Online and Ready!"}
