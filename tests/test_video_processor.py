import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from utils.video_processor import _download_with_options


class _YoutubeDLProbe:
    options = None

    def __init__(self, options):
        type(self).options = options

    def __enter__(self):
        raise RuntimeError("options captured")

    def __exit__(self, exception_type, exception, traceback):
        return False


class VideoProcessorOptionsTest(unittest.TestCase):
    def setUp(self):
        _YoutubeDLProbe.options = None

    def test_download_without_cookies_uses_embedded_youtube_client(self):
        fake_yt_dlp = types.SimpleNamespace(YoutubeDL=_YoutubeDLProbe)

        with tempfile.TemporaryDirectory() as output_path:
            with patch.dict(os.environ, {}, clear=True):
                with patch.dict(sys.modules, {"yt_dlp": fake_yt_dlp}):
                    with self.assertRaisesRegex(RuntimeError, "options captured"):
                        _download_with_options(
                            "https://www.youtube.com/watch?v=TLvMXOEXi_k",
                            output_path,
                            720,
                        )

        youtube_options = _YoutubeDLProbe.options["extractor_args"]["youtube"]
        self.assertEqual(youtube_options["player_client"], ["web_embedded"])

    def test_cookie_download_passes_cookie_file(self):
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

        self.assertEqual(
            _YoutubeDLProbe.options["cookiefile"],
            "/tmp/youtube-cookies.txt",
        )
        youtube_options = _YoutubeDLProbe.options["extractor_args"]["youtube"]
        self.assertEqual(
            youtube_options["player_client"],
            ["web_safari", "web_embedded", "-tv_downgraded"],
        )


if __name__ == "__main__":
    unittest.main()
