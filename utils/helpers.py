import os
import subprocess
import json

def get_video_duration(filepath):
    """Mendapatkan durasi video dalam detik menggunakan ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data['format']['duration'])

def cleanup_temp_folder(path):
    """Hapus folder temporary beserta isinya."""
    import shutil
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)