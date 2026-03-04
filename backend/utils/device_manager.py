import torch

def get_best_device() -> str:
    """
    Returns the best available device for PyTorch and AI models.
    Prioritizes NVIDIA CUDA, then Apple MPS, and falls back to CPU.
    """
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        # Apple Silicon GPU (M1, M2, M3 series)
        return "mps"
    return "cpu"

def get_whisperx_device() -> str:
    """
    WhisperX sometimes requires specific formats depending on the backend.
    """
    return get_best_device()
    
def get_demucs_device() -> str:
    """
    Returns device string formatted for demucs command line.
    """
    return get_best_device()

def get_xtts_device() -> str:
    """
    Returns device string for Coqui XTTS v2.
    """
    return get_best_device()
