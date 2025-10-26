import runpod
from asr_service import ASRService
service = ASRService(
        model_name='large-v2',
        batch_size=64,
        compute_type='int8'
    )
def handler(event):
    # Fix: lấy audio_path từ event["input"]
    audio_path = event.get("input", {}).get("audio_path")
    if not audio_path:
        return {"error": "audio_path is required"}

    language = event.get("input", {}).get("language", "en")
    diarization = event.get("input", {}).get("diarization", False)
    alignment = event.get("input", {}).get("alignment", False)
    min_speakers = event.get("input", {}).get("min_speakers", None)
    max_speakers = event.get("input", {}).get("max_speakers", None)
    task = event.get("input", {}).get("task", "transcribe")

    transcription = service.transcribe_audio(
        audio_path,
        diarization=diarization,
        alignment=alignment,
        language=language,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        task=task
    )

    return transcription


runpod.serverless.start({"handler": handler})