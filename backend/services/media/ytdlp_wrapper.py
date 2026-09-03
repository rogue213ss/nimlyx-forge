import subprocess
import logging
import os
import shutil
from .binary_resolver import get_executable_path

logger = logging.getLogger(__name__)

class AcquisitionError(Exception):
    pass

class AcquisitionUnavailableError(AcquisitionError):
    pass

def download_video(url: str, output_path: str) -> None:
    """
    Downloads video using yt-dlp to exact output_path.
    Raises specific errors for unavailability vs network timeouts.
    """
    node_path = get_executable_path("node")
    if node_path == "node" and not shutil.which("node"):
        raise EnvironmentError("JavaScript runtime (node) not found. Forge requires node for yt-dlp to process YouTube signatures.")

    command = [
        get_executable_path("yt-dlp"),
        "--js-runtimes", f"node:{node_path}",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", output_path,
        "--no-playlist",
        url
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        err_out = e.stderr.lower()
        if "video unavailable" in err_out or "private video" in err_out or "sign in" in err_out:
            raise AcquisitionUnavailableError(f"Video unavailable: {e.stderr}")
        raise AcquisitionError(f"yt-dlp failed: {e.stderr}")
    except FileNotFoundError:
        raise EnvironmentError("yt-dlp not found on system PATH.")
