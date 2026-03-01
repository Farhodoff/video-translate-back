import whisper
import os
import json
import time

# Cache for loaded models
_models = {}

def get_model(model_size: str = "base"):
    global _models
    if model_size not in _models:
        print(f"Whisper modeli yuklanmoqda ({model_size})...")
        _models[model_size] = whisper.load_model(model_size)
        print(f"Whisper ({model_size}) tayyor!")
    return _models[model_size]

def transcribe_video(video_path: str, quality: str = "standard"):
    """
    Transcribes a video file using OpenAI Whisper.
    quality: tiny, standard (base), high (small)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Map quality to whisper model name
    model_map = {
        "tiny": "tiny",
        "standard": "base",
        "high": "small"
    }
    model_name = model_map.get(quality, "base")

    try:
        model = get_model(model_name)
        result = model.transcribe(video_path)
        
        return result["segments"]
    except Exception as e:
        print(f"Error during transcription: {e}")
        raise e

def transcribe_file(video_path: str, output_json: str = None, quality: str = "standard"):
    """Alias for transcribe_video for backward compatibility"""
    segments = transcribe_video(video_path, quality)
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
    return segments
