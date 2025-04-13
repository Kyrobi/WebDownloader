import yt_dlp
import os
import uuid
import time
from urllib.parse import urlparse

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from threading import Thread
from pathlib import Path

# TODO
# 2. Cap max amount of video stored on the server to X at a time
# 3. Rate limit?

# Set up FastAPi config
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static") # Serve static files (css) for my html

# Make a videos folder if it doesn't exist
os.makedirs("videos", exist_ok=True)


def validateURL(url: str) -> bool:
    parsed_url = urlparse(url)

    # Parses the URL and breaks it down to the following object:
    # "https://google.com/search?key=123abc#otherInfo"
    # ParseResult(
    #     scheme='https',
    #     netloc='google.com',
    #     path='/search',
    #     params='',
    #     query='key=123abc',
    #     fragment='otherInfo'
    # )
    
    has_valid_scheme = parsed_url.scheme == "http" or parsed_url.scheme == "https"

    has_netloc = parsed_url.netloc != ""

    if has_valid_scheme and has_netloc:
        return True
    else:
        return False

# Serve the homepage index.html
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Request object contains things like headers, cookies, methods (post/get), IP, etc

    return templates.TemplateResponse(
        "index.html", 
        {"request": request} # dictionary that is being passed to your HTML template. Required using Jinja2
    )

@app.post("/download")
async def download_video(request: Request, url: str = Form(...)):

    if not validateURL(url):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"Link is invalid",
                "success": False
            },
            status_code=400
        )

    try:

        unique_id = str(uuid.uuid4())
        folder = "videos/"

        # These placeholder values will be filled in my ydl once the video is downloaded
        title_placeholder = "%(title)s"
        extension_placeholder = "%(ext)s"

        # Create the output template with regular string concatenation
        # Creates the directory and file name of the video
        output_file = folder + title_placeholder + " " + unique_id + "." + extension_placeholder
        
        ydl_opts = {
            'outtmpl': output_file,
            'format': 'best',
            'quiet': True,
            'noplaylist': True,  # Add this to download only single videos
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Get clean filename without temporary .part extension
            final_filename = filename.replace('.part', '') if '.part' in filename else filename
            if os.path.exists(filename):
                os.rename(filename, final_filename)
            
            print(final_filename)
            delete_file_after_delay(final_filename)

            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "download_url": f"/download/{os.path.basename(final_filename)}",
                    "filename": os.path.basename(final_filename),
                    "success": True  # Add success flag for template
                }
            )
            
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"Failed to download: {str(e)}",
                "success": False
            },
            status_code=400
        )

# Endpoint to request the item to download
@app.get("/download/{filename}")
async def get_video(filename: str):
    filepath = f"videos/{filename}"
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        filename=filename,
        media_type='application/octet-stream'
    )

    # application/octet-stream is like a generic file instead of a specific file type. For example:
    # video/mp4 for MP4 files
    # video/webm for WebM files
    # video/x-matroska for MKV files

def delete_file_after_delay(file_path: str):
    delay_minutes = 2
    
    def _delete_file():
        time.sleep(delay_minutes * 60)  # Convert minutes to seconds
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                print(f"Deleted file: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    # Start the deletion thread
    Thread(target=_delete_file, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)