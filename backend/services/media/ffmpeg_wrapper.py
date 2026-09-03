import subprocess
import json
import logging
from .binary_resolver import get_executable_path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class MediaValidationError(Exception):
    pass

class MediaProcessingError(Exception):
    pass

def probe_video(file_path: str) -> Dict:
    """
    Runs ffprobe to validate container, streams, and duration.
    Raises MediaValidationError if invalid.
    """
    command = [
        get_executable_path("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type",
        "-of", "json",
        file_path
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        streams = data.get("streams", [])
        if not any(s.get("codec_type") == "video" for s in streams):
            raise MediaValidationError("No video stream found.")
            
        fmt = data.get("format", {})
        duration = float(fmt.get("duration", 0))
        if duration <= 0:
            raise MediaValidationError("Invalid or zero duration.")
            
        return {"duration": duration, "streams": len(streams)}
    except subprocess.CalledProcessError as e:
        raise MediaValidationError(f"ffprobe failed: {e.stderr}")
    except FileNotFoundError:
        raise EnvironmentError("ffprobe not found on system PATH.")

def clip_video(input_path: str, output_path: str, start: float, end: float) -> None:
    """
    Uses ffmpeg to clip the video precisely.
    """
    if start < 0 or start >= end:
        raise ValueError(f"Invalid clip timestamps: start={start}, end={end}")
        
    duration = end - start
    
    command = [
        get_executable_path("ffmpeg"),
        "-y", # Overwrite output
        "-ss", str(start),
        "-i", input_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path
    ]
    
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise MediaProcessingError(f"FFmpeg clipping failed: {e.stderr}")
    except FileNotFoundError:
        raise EnvironmentError("ffmpeg not found on system PATH.")
