import os
import subprocess
import shutil

from backend.utils.device_manager import get_demucs_device

def separate_audio(video_path: str, output_dir: str):
    """
    Uses Demucs to separate audio into 'vocals' and 'no_vocals' (background).
    Returns a tuple of (vocals_path, no_vocals_path).
    """
    print(f"Demucs orqali audio ajratilmoqda: {video_path}")
    
    # Demucs outputs to a specific folder structure: <output_dir>/mdx_extra_q/filename/...
    # Demucs command: demucs -n mdx_extra_q --two-stems=vocals <input> -o <output_dir>
    # We use a fast model 'htdemucs_ft' or 'mdx_extra_q'
    model_name = "htdemucs"
    device = get_demucs_device()
    
    cmd = [
        "demucs",
        "-n", model_name,
        "--two-stems=vocals",
        "-d", device,
        "-o", output_dir,
        video_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Demucs xatoligi: {e}")
        raise RuntimeError("Audio separation failed.")
        
    filename_no_ext = os.path.splitext(os.path.basename(video_path))[0]
    result_dir = os.path.join(output_dir, model_name, filename_no_ext)
    
    vocals_path = os.path.join(result_dir, "vocals.wav")
    no_vocals_path = os.path.join(result_dir, "no_vocals.wav")
    
    if not os.path.exists(vocals_path) or not os.path.exists(no_vocals_path):
        raise FileNotFoundError("Demucs result files not found.")
        
    return vocals_path, no_vocals_path

def adjust_audio_speed(input_audio_path: str, target_duration_ms: int, output_audio_path: str):
    """
    Adjusts the speed of the audio to match the `target_duration_ms` exactly using ffmpeg's atempo.
    """
    # First, get the current duration using ffprobe
    probe_cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        input_audio_path
    ]
    
    try:
        result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        current_duration_sec = float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"ffprobe error: {e.stderr}")
        raise RuntimeError("Failed to get audio duration.")
        
    current_duration_ms = current_duration_sec * 1000.0
    
    # Calculate speed multiplier
    if target_duration_ms <= 0:
        target_duration_ms = current_duration_ms # fallback
        
    speed_multiplier = current_duration_ms / target_duration_ms
    
    print(f"Speed adjustment: {current_duration_ms:.0f}ms -> {target_duration_ms:.0f}ms (Multiplier: {speed_multiplier:.3f}x)")
    
    if abs(speed_multiplier - 1.0) < 0.02:
        # If it's very close, just copy to save processing
        shutil.copy(input_audio_path, output_audio_path)
        return output_audio_path

    # atempo filter strictly accepts values between 0.5 and 100.0
    # If the multiplier is outside this range, we would need to chain multiple atempo filters.
    # We will implement a chaining approach dynamically just in case, though it's rare to need < 0.5 or > 100
    
    filters = []
    temp_mult = speed_multiplier
    while temp_mult < 0.5:
        filters.append("atempo=0.5")
        temp_mult /= 0.5
    while temp_mult > 100.0:
        filters.append("atempo=100.0")
        temp_mult /= 100.0
    
    if 0.5 <= temp_mult <= 100.0 and temp_mult != 1.0:
        filters.append(f"atempo={temp_mult}")
        
    atempo_str = ",".join(filters)
    
    if not atempo_str:
        shutil.copy(input_audio_path, output_audio_path)
        return output_audio_path
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_audio_path,
        "-filter:a", atempo_str,
        output_audio_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg atempo xatoligi: {e.stderr.decode()}")
        raise RuntimeError("Failed to adjust audio speed.")
        
    return output_audio_path
