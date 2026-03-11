from celery import Celery
import os
from core.db import SessionLocal, Audio, TranscribeResult, SummarizeResult
from sqlalchemy.exc import SQLAlchemyError
import json
import runpod
from os import getenv
runpod.api_key = getenv("RUNPOD_API_KEY")
endpoint_asr = runpod.Endpoint(getenv("RUNPOD_ENDPOINT_ASR_ID"))
endpoint_summarization = runpod.Endpoint(getenv("RUNPOD_ENDPOINT_SUMMARIZATION_ID"))
from uuid import uuid4
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

celery_app = Celery(
    'speech_minute',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://140.115.59.61:6379/7'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://140.115.59.61:6379/3')
)



@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def asr_and_summary_task(self, audio_id, language, diarization=True, hotwords=[]):
    db = SessionLocal()
    try:
        logger.info(f"[START] ASR+Summary for audio_id={audio_id}, language={language}")
        audio = db.query(Audio).filter(Audio.id == audio_id).first()

        if not audio:
            logger.error(f"Audio not found: {audio_id}")
            return False

        audio.status = "processing"
        db.commit()

        file_url = audio.s3_url

        # ✅ ASR call
        logger.info(f"Calling ASR endpoint with URL: {file_url}")
        logger.info(f"ASR parameters: language={language}, diarization=True, batch_size=64")
        
        try:
            run_request = endpoint_asr.run_sync({
                "audio_path": file_url,
                
            
            }, timeout=900)  # 15 minutes timeout
            logger.info(f"ASR request completed successfully")
        except Exception as asr_error:
            logger.error(f"ASR endpoint error: {asr_error}")
            logger.error(f"File URL that failed: {file_url}")
            raise Exception(f"ASR service failed: {asr_error}")

        # Nếu API lỗi hoặc return None → retry
        if run_request is None or "transcription" not in run_request:
            raise Exception("ASR service failed")

        transcribe_id = str(uuid4())
        transcription_text = run_request["transcription"]
        
        # Keep segments for backward compatibility if available
        segments_json = json.dumps(run_request.get("segments", []))
        
        transcribe = TranscribeResult(
            id=transcribe_id,
            audio_id=audio_id,
            user_id=audio.user_id,
            segments=segments_json,
            transcription=transcription_text
        )
        db.add(transcribe)
        db.commit()

        transcript_text = transcription_text
        if language == "zh":
            language = "zh-TW"

        # ✅ Summarization
        logger.info(f"Calling summarization endpoint with language: {language}")
        try:
            run_request_sum = endpoint_summarization.run_sync({
                "task": "summarize",
                "language": language,
                "transcript": transcript_text,
            }, timeout=900)  # 15 minutes timeout
            logger.info(f"Summarization completed successfully")
        except Exception as sum_error:
            logger.error(f"Summarization endpoint error: {sum_error}")
            raise Exception(f"Summarization service failed: {sum_error}")

        if run_request_sum is None or "summary" not in run_request_sum:
            raise Exception("Summarization service failed")

        summary_id = str(uuid4())
        summary = SummarizeResult(
            id=summary_id,
            transcribe_id=transcribe_id,
            audio_id=audio_id,
            user_id=audio.user_id,
            summary=json.dumps(run_request_sum["summary"])
        )
        db.add(summary)

        # ✅ Add transcript again
        logger.info(f"Adding transcript to meeting_id: {audio_id}")
        transcript_dict = [{
            "id": transcribe.id,
            "audio_id": transcribe.audio_id,
            "user_id": transcribe.user_id,
            "transcription": transcription_text,
            "segments": json.loads(segments_json) if segments_json else [],
            "created_at": transcribe.created_at.isoformat() if transcribe.created_at else None
        }]

        try:
            response = endpoint_summarization.run_sync({
                "task": "add_transcript",
                "meeting_id": audio_id,
                "transcript": transcript_dict
            }, timeout=60)  # 1 minute timeout
            logger.info(f"Add transcript completed successfully")
        except Exception as add_error:
            logger.error(f"Add transcript endpoint error: {add_error}")
            # Don't fail the whole task if add_transcript fails
            logger.warning("Continuing despite add_transcript failure")

        if response is None:
            logger.warning("Add transcript returned None, but continuing")

        audio.status = "completed"
        db.commit()
        return True

    except Exception as e:
        logger.error(f"[FAILED] error={e}")

        # ✅ Retry nếu còn lượt retry
        raise self.retry(exc=e, countdown=10)  # retry sau 10 giây

    finally:
        db.close()
