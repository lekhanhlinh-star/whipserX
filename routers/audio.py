

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, BackgroundTasks
from typing import List, Optional
from sqlalchemy.orm import Session
from core.db import get_db, Audio, TranscribeResult, SummarizeResult
from core.auth import get_current_user
from background_tasks import asr_and_summary_background_task
from utils import upload_file_to_s3
from uuid import uuid4
from urllib.parse import quote
import boto3
import subprocess
import os
from os import getenv

router = APIRouter()

def convert_to_wav(input_path: str) -> str:
    """Convert audio file to wav format using ffmpeg"""
    try:
        # Generate a distinct output path (don't overwrite input)
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_conv.wav"
        
        # Use ffmpeg to convert to compressed wav (mu-law encoding for smaller size)
        cmd = [
            'ffmpeg', '-i', input_path,
            '-acodec', 'pcm_mulaw',  # mu-law encoding for compression
            '-ar', '8000',  # 8kHz sample rate for speech (reduces size)
            '-ac', '1',  # mono
            '-y',  # Overwrite output file
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # If ffmpeg fails, include stderr for debugging
            raise Exception(f"FFmpeg conversion failed: {result.stderr}")

        # Remove original file only if output was created and is different
        if os.path.exists(output_path):
            try:
                os.remove(input_path)
            except Exception:
                # ignore cleanup error
                pass
            return output_path
        else:
            raise Exception("FFmpeg did not produce output file")
        
    except Exception as e:
        print(f"Failed to convert audio to m4a: {e}")
        # Return original path if conversion fails
        return input_path

def delete_file_from_s3(s3_url: str):
    """Delete file from S3 using the S3 URL"""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=getenv('S3_REGION', 'us-east-1')
        )
        # Extract bucket and key from S3 URL
        # Format: https://bucket-name.s3.region.amazonaws.com/key
        parts = s3_url.replace('https://', '').split('/')
        bucket_name = parts[0].split('.')[0]  # Extract bucket name
        s3_key = '/'.join(parts[1:])  # Everything after first slash is the key
        s3_key = quote(s3_key, safe='/')  # URL decode the key
        
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        return True
    except Exception as e:
        print(f"Failed to delete S3 file: {e}")
        return False

@router.post("/audio")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("zh"),
    diarization: bool = Form(False),
    hotwords: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Convert audio to wav format
    converted_file_path = convert_to_wav(temp_file_path)
    
    # Update filename to have .wav extension
    original_name = os.path.splitext(file.filename)[0]
    converted_filename = f"{original_name}.wav"
    
    bucket_name = getenv('S3_BUCKET_NAME', 'ai-runpod-audio-1')
    s3_key = f"uploads/{current_user.id}/{converted_filename}"
    file_url = upload_file_to_s3(converted_file_path, bucket_name, s3_key)
    print("Uploaded file URL:", file_url)
    
    # Clean up converted file
    if os.path.exists(converted_file_path):
        os.remove(converted_file_path)
    
    if not file_url:
        raise HTTPException(status_code=500, detail="Failed to upload file to S3.")
    # Always use the correct region endpoint for s3_url
    s3_url = f"https://{bucket_name}.s3.{getenv('S3_REGION', 'us-east-1')}.amazonaws.com/{quote(s3_key)}"
    audio_id = str(uuid4())
    audio = Audio(
        id=audio_id,
        filename=file.filename,
        s3_url=s3_url,
        user_id=current_user.id,
        status="pending"
    )
    db.add(audio)
    db.commit()
    print("Audio uploaded successfully:", audio_id
          )
    print(f"Triggering ASR processing for audio_id={audio_id}, language={language}, diarization={diarization}")
    # Ensure hotwords is a list (Form may return None)
    if hotwords is None:
        hotwords = []

    # Trigger ASR processing as Background Task
    background_tasks.add_task(asr_and_summary_background_task, audio_id, language, diarization, hotwords)
    return {"audio_id": audio_id, "s3_url": s3_url, "status": audio.status}

@router.get("/audio/status/{audio_id}")
async def get_audio_status(audio_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    audio = db.query(Audio).filter(Audio.id == audio_id, Audio.user_id == current_user.id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found.")
    return {"audio_id": audio.id, "status": audio.status}

@router.get("/audio")
async def list_audio(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    audios = db.query(Audio).filter(Audio.user_id == current_user.id).order_by(Audio.upload_time.desc()).all()
    if not audios:
        raise HTTPException(status_code=404, detail="No audio files found.")
    from datetime import timedelta
    return [
        {
            "audio_id": a.id,
            "filename": a.filename,
            "s3_url": a.s3_url,
            # Chuyển sang múi giờ Việt Nam (UTC+7)
            "upload_time": (a.upload_time + timedelta(hours=8)).isoformat(),
            "status": a.status
        }
        for a in audios
    ]

@router.delete("/audio/{audio_id}")
async def delete_audio(audio_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    audio = db.query(Audio).filter(Audio.id == audio_id, Audio.user_id == current_user.id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found.")
    
    # Store S3 URL before deleting from DB
    s3_url = audio.s3_url
    
    # Delete dependent transcribes and summaries first to avoid FK constraint errors
    try:
        db.query(SummarizeResult).filter(SummarizeResult.audio_id == audio_id).delete(synchronize_session=False)
        db.query(TranscribeResult).filter(TranscribeResult.audio_id == audio_id).delete(synchronize_session=False)
        db.delete(audio)
        db.commit()
        
        # Delete file from S3 after successful DB deletion
        s3_deleted = delete_file_from_s3(s3_url)
        if s3_deleted:
            return {"message": "Audio, related data, and S3 file deleted successfully."}
        else:
            return {"message": "Audio and related data deleted, but S3 file deletion failed."}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete audio: {e}")
