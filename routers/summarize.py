
from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from core.db import get_db, SummarizeResult, TranscribeResult, Audio
from core.auth import get_current_user
from uuid import uuid4
import runpod
from os import getenv
runpod.api_key = getenv("RUNPOD_API_KEY")
endpoint_summarization = runpod.Endpoint(getenv("RUNPOD_ENDPOINT_SUMMARIZATION_ID"))

router = APIRouter()

    
@router.post("/summarize/")
async def summarize_meeting(
    audio_id: str = Form(...),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Find latest transcript for this audio_id and user
    transcript = db.query(TranscribeResult).filter(
        TranscribeResult.audio_id == audio_id,
        TranscribeResult.user_id == current_user.id
    ).order_by(TranscribeResult.created_at.desc()).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript found for this audio.")
    # Assume transcript.segments is a JSON list of dicts with 'text' field
    import json
    try:
        segments = json.loads(transcript.segments)
        transcript_text = " ".join([seg.get("text", "") for seg in segments])
    except Exception:
        transcript_text = transcript.segments
    try:
        run_request = endpoint_summarization.run_sync({
            "task": "summarize",
            "language": language,
            "transcript": transcript_text,
        })
        summary_id = str(uuid4())
        import json as _json
        summary_json = _json.dumps(run_request["summary"])
        summary = SummarizeResult(
            id=summary_id,
            transcribe_id=transcript.id,
            audio_id=audio_id,
            user_id=current_user.id,
            summary=summary_json
        )
        db.add(summary)
        db.commit()
        return {"summary_id": summary_id, "transcribe_id": transcript.id, "audio_id": audio_id, "summary": run_request["summary"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# @router.get("/summarize")
# async def list_summaries(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     summaries = db.query(SummarizeResult).filter(SummarizeResult.user_id == current_user.id).all()
#     return [{"summary_id": s.id, "transcribe_id": s.transcribe_id, "audio_id": s.audio_id, "summary": s.summary, "created_at": s.created_at.isoformat() if s.created_at else None} for s in summaries]

# @router.get("/summarize/{summary_id}/")
# async def get_summary(summary_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
#     s = db.query(SummarizeResult).filter(SummarizeResult.id == summary_id, SummarizeResult.user_id == current_user.id).first()
#     if not s:
#         raise HTTPException(status_code=404, detail="Summary not found.")
#     return {"summary_id": s.id, "transcribe_id": s.transcribe_id, "audio_id": s.audio_id, "summary": s.summary, "created_at": s.created_at.isoformat() if s.created_at else None}

@router.get("/summarize/audio/{audio_id}/")
async def get_first_summary_by_audio(audio_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    s = db.query(SummarizeResult).filter(SummarizeResult.audio_id == audio_id, SummarizeResult.user_id == current_user.id).order_by(SummarizeResult.created_at.asc()).first()
    import json as _json
    if not s:
        return None
    return {
        "summary_id": s.id,
        "transcribe_id": s.transcribe_id,
        "audio_id": s.audio_id,
        "summary": _json.loads(s.summary) if s.summary else None,
        # "created_at": s.created_at.isoformat() if s.created_at else None
    }