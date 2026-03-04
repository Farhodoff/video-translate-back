import os
import subprocess
import traceback

WAV2LIP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "third_party", "Wav2Lip")
CHECKPOINT_PATH = os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth")
INFERENCE_SCRIPT = os.path.join(WAV2LIP_DIR, "inference.py")

def apply_lipsync(video_path: str, audio_path: str, output_path: str) -> bool:
    """
    Executes the Wav2Lip inference script to synchronize the source video's
    lip movements with the provided dubbed audio track.
    """
    if not os.path.exists(CHECKPOINT_PATH):
        print(f"Error: Wav2Lip checkpoint not found at {CHECKPOINT_PATH}")
        return False
        
    if not os.path.exists(video_path):
        print(f"Error: Source face video not found at {video_path}")
        return False
        
    if not os.path.exists(audio_path):
        print(f"Error: Source dubbed audio not found at {audio_path}")
        return False

    print(f"Starting Lip-Sync process. Face: {video_path}, Audio: {audio_path}")
    
    # Optional performance enhancements
    # --nosmooth reduces jitter/smoothing on the mask
    # --pads can help adjust the face bounding box (top, bottom, left, right)
    
    command = [
        "python3", INFERENCE_SCRIPT,
        "--checkpoint_path", CHECKPOINT_PATH,
        "--face", video_path,
        "--audio", audio_path,
        "--outfile", output_path
    ]
    
    try:
        # Run subprocess, streaming logs if desired or just waiting
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Wav2Lip completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Wav2Lip execution failed with exit code {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error running Wav2Lip: {e}")
        traceback.print_exc()
        return False
