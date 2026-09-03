import os
import sys
import shutil

def get_executable_path(name: str) -> str:
    # 1. Check virtual environment
    venv_dir = os.path.join(os.path.dirname(__file__), "../../../venv/Scripts")
    venv_path = os.path.abspath(os.path.join(venv_dir, f"{name}.exe"))
    if os.path.exists(venv_path):
        return venv_path
        
    # 2. Check local ffmpeg bundle
    ffmpeg_dir = os.path.join(os.path.dirname(__file__), "../../../ffmpeg/ffmpeg-master-latest-win64-gpl/bin")
    ffmpeg_path = os.path.abspath(os.path.join(ffmpeg_dir, f"{name}.exe"))
    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
        
    # 3. Explicit check for node on known physical host path
    if name == 'node':
        if os.path.exists('D:\\nodejs\\node.exe'):
            return 'D:\\nodejs\\node.exe'
            
    # 4. Fallback to system PATH
    sys_path = shutil.which(name)
    if sys_path:
        return sys_path
        
    # Default to name and let FileNotFoundError bubble up
    return name
