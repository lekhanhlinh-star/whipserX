
import logging
from fastapi import APIRouter, Form, HTTPException, Depends
from core.auth import get_current_user
from core.db import Audio, TranscribeResult, get_db
from sqlalchemy.orm import Session
import runpod
import json
from os import getenv
runpod.api_key = getenv("RUNPOD_API_KEY")
endpoint_summarization = runpod.Endpoint(getenv("RUNPOD_ENDPOINT_SUMMARIZATION_ID"))

router = APIRouter()

@router.post("/chat/")
async def chat_with_summary(
    audio_id: str = Form(...),
    user_message: str = Form(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if audio_id is valid
    audio = db.query(Audio).filter(Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found")

    # Call Runpod endpoint for summarization
    response = endpoint_summarization.run_sync({
        "task": "chat",
        "meeting_id": audio_id,
        "query": user_message
    })

    return {"response": response}

# @router.post("/chat/add_transcript/")
# async def add_transcript(
#     audio_id: str = Form(...),
#     current_user = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     # Check if audio_id is valid
#     audio = db.query(Audio).filter(Audio.id == audio_id).first()
#     if not audio:
#         raise HTTPException(status_code=404, detail="Audio not found")
    
#     # Get transcript from database
#     transcribe_result = db.query(TranscribeResult).filter(
#         TranscribeResult.audio_id == audio_id
#     ).first()
    
#     if not transcribe_result:
#         raise HTTPException(status_code=404, detail="Transcript not found for this audio")
    
#     # Convert SQLAlchemy object to dict
#     transcript_dict = [{
#         "id": transcribe_result.id,
#         "audio_id": transcribe_result.audio_id,
#         "user_id": transcribe_result.user_id,
#         "segments": json.loads(transcribe_result.segments) if transcribe_result.segments else [],
#         "created_at": transcribe_result.created_at.isoformat() if transcribe_result.created_at else None
#     }]
    
#     logging.info(f"Adding transcript for audio_id={audio_id} to Runpod endpoint")

#     # Call Runpod endpoint to add transcript
#     response = endpoint_summarization.run_sync({
#         "task": "add_transcript",
#         "meeting_id": audio_id,
#         "transcript": transcript_dict
#     })

#     return {"detail": "Transcript added successfully", "transcript": transcript_dict}  