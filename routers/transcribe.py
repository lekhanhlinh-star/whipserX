
from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from core.db import get_db, Audio, TranscribeResult
from core.auth import get_current_user
from uuid import uuid4
import json
import runpod
from os import getenv
runpod.api_key = getenv("RUNPOD_API_KEY")
endpoint_asr = runpod.Endpoint(getenv("RUNPOD_ENDPOINT_ASR_ID"))

router = APIRouter()

@router.post("/transcribe/")
async def transcribe_audio(
    audio_id: str = Form(...),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    audio = db.query(Audio).filter(Audio.id == audio_id, Audio.user_id == current_user.id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found.")
    file_url = audio.s3_url
    try:
        run_request = endpoint_asr.run_sync({
            "audio_path": file_url,
            "language": language,
            "diarization": True,
            "batch_size": 32
        })
        transcribe_id = str(uuid4())
        transcription_text = run_request.get("transcription", "")
        segments_json = json.dumps(run_request.get("segments", []))
        transcribe = TranscribeResult(
            id=transcribe_id, 
            audio_id=audio_id, 
            user_id=current_user.id, 
            segments=segments_json,
            transcription=transcription_text
        )
        db.add(transcribe)
        db.commit()
        return {
            "transcribe_id": transcribe_id, 
            "audio_id": audio_id, 
            "transcription": transcription_text,
            "segments": run_request.get("segments", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# @router.get("/transcribe/list/")
# async def list_transcribes(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     transcribes = db.query(TranscribeResult).filter(TranscribeResult.user_id == current_user.id).all()
#     return [{"transcribe_id": t.id, "audio_id": t.audio_id, "segments": json.loads(t.segments), "created_at": t.created_at.isoformat() if t.created_at else None} for t in transcribes]

# @router.get("/transcribe/{transcribe_id}/")
# async def get_transcribe(transcribe_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     t = db.query(TranscribeResult).filter(TranscribeResult.id == transcribe_id, TranscribeResult.user_id == current_user.id).first()
#     if not t:
#         raise HTTPException(status_code=404, detail="Transcribe result not found.")
#     return {"transcribe_id": t.id, "audio_id": t.audio_id, "segments": json.loads(t.segments), "created_at": t.created_at.isoformat() if t.created_at else None}
@router.get("/transcribe/audio/{audio_id}/")
async def get_transcribes_by_audio(audio_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    transcribes = db.query(TranscribeResult).filter(TranscribeResult.audio_id == audio_id, TranscribeResult.user_id == current_user.id).all()
    return [
        {
            "transcribe_id": t.id,
            "audio_id": t.audio_id,
            "transcription": t.transcription,
            "segments": json.loads(t.segments) if t.segments else [],
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in transcribes
    ]