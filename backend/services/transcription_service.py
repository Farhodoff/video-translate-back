# PyTorch 2.6+ security fix for WhisperX/Omegaconf
# We patch torch.load to avoid "WeightsUnpickler error" during model loading
import torch
import torch.serialization
import whisperx
import os
import json

_orig_load = torch.load
def _patched_load(*args, **kwargs):
    # Forced weights_only=False to allow loading models with custom classes
    kwargs['weights_only'] = False
    return _orig_load(*args, **kwargs)

torch.load = _patched_load
torch.serialization.load = _patched_load

# Also try to add safe globals for better compatibility
try:
    from omegaconf.listconfig import ListConfig
    from omegaconf.dictconfig import DictConfig
    from omegaconf.base import ContainerMetadata, Metadata
    if hasattr(torch.serialization, 'add_safe_globals'):
        torch.serialization.add_safe_globals([ListConfig, DictConfig, ContainerMetadata, Metadata])
except Exception:
    pass

# Cache for loaded models
_models = {}
_alignment_models = {}

from backend.utils.device_manager import get_whisperx_device

def get_device():
    return get_whisperx_device()

def get_model(model_size: str = "base"):
    global _models
    device = get_device()
    compute_type = "int8" if device == "cpu" else "float16" # int8 is faster on CPU
    
    if model_size not in _models:
        print(f"WhisperX modeli yuklanmoqda ({model_size}) on {device}...")
        _models[model_size] = whisperx.load_model(model_size, device, compute_type=compute_type)
        print(f"WhisperX ({model_size}) tayyor!")
    return _models[model_size]

def get_alignment_model(language_code: str):
    global _alignment_models
    device = get_device()
    if language_code not in _alignment_models:
        print(f"Alignment modeli yuklanmoqda ({language_code})...")
        model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        _alignment_models[language_code] = (model_a, metadata)
    return _alignment_models[language_code]

def transcribe_video(video_path: str, quality: str = "standard"):
    """
    Transcribes a video file using WhisperX to get word-level timestamps.
    quality: tiny, standard (base), high (small)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    model_map = {
        "tiny": "tiny",
        "standard": "base",
        "high": "small"
    }
    model_name = model_map.get(quality, "base")
    device = get_device()

    try:
        # 1. Transcribe
        model = get_model(model_name)
        audio = whisperx.load_audio(video_path)
        result = model.transcribe(audio, batch_size=4 if device == "cpu" else 16)
        
        # 2. Align whisper output
        language_code = result["language"]
        model_a, metadata = get_alignment_model(language_code)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_align=False)
        
        # result["segments"] endi so'z darajasidagi (word-level) timestamp-larni ichiga oladi
        return result["segments"]
    except Exception as e:
        print(f"Error during transcription with WhisperX: {e}")
        # O'zbek tili uchun alignment modeli topilmasligi mumkin, shunda oddiy natijani qaytaramiz
        try:
            model = get_model(model_name)
            audio = whisperx.load_audio(video_path)
            result = model.transcribe(audio)
            return result["segments"]
        except:
            raise e

def transcribe_file(video_path: str, output_json: str = None, quality: str = "standard"):
    """Alias for transcribe_video for backward compatibility"""
    segments = transcribe_video(video_path, quality)
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
    return segments
