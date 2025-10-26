from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import tempfile, aiohttp, os
from asr_service import ASRService

app = FastAPI()

# --- Startup: load ASR model once ---
@app.on_event("startup")
async def startup_event():
    app.state.asr_service = ASRService(
        model_name="large",
        batch_size=32,
        compute_type="int8"
    )

# --- Main API ---
@app.post("/transcribe/")
async def transcribe_audio(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    language: Optional[str] = Form("en")
):
    """
    Accept either:
    - UploadFile via form-data (key='file')
    - URL via form field (key='file_url')
    """
    service: ASRService = app.state.asr_service

    # Case 1: User uploads a file
    if file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

    # Case 2: User provides file_url
    elif file_url:
        result = service.transcribe_audio(file_url, language=language)
        return result

    else:
        raise HTTPException(status_code=400, detail="You must provide either 'file' or 'file_url'")

    # Run transcription
    try:
        result = service.transcribe_audio(tmp_path, language=language)
    finally:
        os.remove(tmp_path)  # cleanup temp file

    return result
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)