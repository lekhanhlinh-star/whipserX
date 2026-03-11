from fastapi import FastAPI
import os
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import user, audio, transcribe, summarize, chat

app = FastAPI()

origins = [
    "http://localhost:8080",
    "https://speech-minute-cloud-v1.onrender.com",
    "https://speech-minute-app-latest.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user.router)
app.include_router(audio.router)
app.include_router(transcribe.router)
app.include_router(summarize.router)
app.include_router(chat.router)

# Serve uploaded files from LOCAL_UPLOAD_DIR at /uploads
UPLOAD_ROOT = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    