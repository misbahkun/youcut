import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from utils.video_processor import _download_with_options


class _YoutubeDLProbe:
    def __init__(self, options):
        youtube_options = options["extractor_args"]["youtube"]
        assert youtube_options["player_client"] == [
            "web_safari",
            "web_embedded",
            "-tv_downgraded",
        ]

    def __enter__(self):
        raise RuntimeError("options captured")

    def __exit__(self, exception_type, exception, traceback):
        return False


class VideoProcessorOptionsTest(unittest.TestCase):
    def test_cookie_download_uses_compatible_youtube_clients(self):
        fake_yt_dlp = types.SimpleNamespace(YoutubeDL=_YoutubeDLProbe)

        with tempfile.TemporaryDirectory() as output_path:
            with patch.dict(
                os.environ,
                {"YOUTUBE_COOKIES_FILE": "/tmp/youtube-cookies.txt"},
            ):
                with patch.dict(sys.modules, {"yt_dlp": fake_yt_dlp}):
                    with self.assertRaisesRegex(RuntimeError, "options captured"):
                        _download_with_options(
                            "https://www.youtube.com/watch?v=5bId3N7QZec",
                            output_path,
                            720,
                        )


if __name__ == "__main__":
    unittest.main()
