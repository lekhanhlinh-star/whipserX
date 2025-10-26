import torch
import whisperx
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from whisperx.diarize import DiarizationPipeline
import os
hf_token = os.getenv("HF_AUTH_TOKEN")
class ASRService:
    def __init__(self, model_name: str = 'large-v2',
                 batch_size: int = 16,
                 compute_type: str = 'int8',
                 num_workers: int = 8,
                 device: str = None):
        """
        Initializes the ASRService with the specified model and parameters.
        Args:
            model_name (str): Name of the WhisperX model to load.
            batch_size (int): Batch size for transcription.
            compute_type (str): Type of computation (e.g., 'int8', 'float16').
            device (str): Device to run the model on ('cuda' or 'cpu'). If None, automatically selects.
        """
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        self.batch_size = batch_size

        print(f"[INFO] Loading WhisperX model: {model_name} ({compute_type}) on {device}")
        self.model = whisperx.load_model(
            model_name,
            device=device,
            compute_type=compute_type,
            threads=num_workers,
            vad_options={"vad_onset": 0.500, "vad_offset": 0.300}
        )

        print(f"[INFO] Loading diarization pipeline on {device}")
        self.diarization_model = DiarizationPipeline(
            use_auth_token=hf_token,
            device=device
        )

    def transcribe_audio(self, audio_path, language=None, diarization: bool = False,
                         alignment: bool = False, task='transcribe',
                         min_speakers: int = None, max_speakers: int = None):
        """
        Transcribe an audio file with optional alignment and diarization.
        """
        print(f"[INFO] Loading audio: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # --- Step 1: Transcription ---
        print("[INFO] Transcribing audio...")
        result = self.model.transcribe(
            audio,
            batch_size=self.batch_size,
            language=language,
            task=task
        )

        # --- Step 2: Optional alignment ---
        if alignment:
            print("[INFO] Performing alignment...")
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"],
                device=self.device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
        
        if diarization:
            print("[INFO] Performing diarization...")
            diarize_segments = self.diarization_model(audio)
            if min_speakers is not None and max_speakers is not None:
                result = whisperx.assign_word_speakers(
                    diarize_segments, result,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
            else:
                result = whisperx.assign_word_speakers(diarize_segments, result)

        print("[INFO] Transcription completed successfully.")
        return result


if __name__ == "__main__":
    service = ASRService(
        model_name='tiny',
        batch_size=8,
        compute_type='int8'
    )

    transcription = service.transcribe_audio(
        "https://ai-runpod-audio.s3.us-east-1.amazonaws.com/0edb32e7bc444e0e8b488229a250df2f_segment_1_%E6%98%9F%E6%9C%9F%E4%B8%89%2B%E4%B8%8B%E5%8D%883-56.m4a",
        diarization=True,
        alignment=True,
        language='zh'
    )

    print("\n========= FINAL RESULT =========\n")
    print(transcription)
