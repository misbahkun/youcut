import os
import subprocess
import zipfile


def _find_latest_mp4(output_path):
    """
    Cari file MP4 terbaru di folder output.
    """
    candidates = []

    if not os.path.exists(output_path):
        return None

    for name in os.listdir(output_path):
        path = os.path.join(
            output_path,
            name
        )

        if (
            os.path.isfile(path)
            and
            name.lower().endswith(".mp4")
        ):
            candidates.append(path)

    if not candidates:
        return None

    candidates.sort(
        key=os.path.getmtime,
        reverse=True
    )

    return candidates[0]


def _find_any_video(output_path):
    """
    Cari file video terbaru jika output bukan MP4.
    """
    extensions = (
        ".mp4",
        ".mkv",
        ".webm",
        ".mov",
        ".avi",
        ".m4v",
    )

    candidates = []

    if not os.path.exists(output_path):
        return None

    for name in os.listdir(output_path):
        path = os.path.join(
            output_path,
            name
        )

        if (
            os.path.isfile(path)
            and
            name.lower().endswith(extensions)
        ):
            candidates.append(path)

    if not candidates:
        return None

    candidates.sort(
        key=os.path.getmtime,
        reverse=True
    )

    return candidates[0]


def _find_downloaded_file(
    output_path,
    info=None,
    ydl=None
):
    """
    Cari file hasil download dengan beberapa fallback.
    """

    # -----------------------------------------------------
    # 1. requested_downloads
    # -----------------------------------------------------

    if info:

        requested_downloads = (
            info.get(
                "requested_downloads"
            )
            or
            []
        )

        for item in requested_downloads:

            path = (
                item.get(
                    "filepath"
                )
                or
                item.get(
                    "filename"
                )
            )

            if not path:
                continue

            if os.path.exists(path):

                if path.lower().endswith(
                    ".mp4"
                ):
                    return path

                base, _ = os.path.splitext(
                    path
                )

                mp4_path = (
                    base
                    +
                    ".mp4"
                )

                if os.path.exists(
                    mp4_path
                ):
                    return mp4_path

                return path


    # -----------------------------------------------------
    # 2. prepare_filename
    # -----------------------------------------------------

    if (
        info
        and
        ydl
    ):

        try:

            prepared = (
                ydl.prepare_filename(
                    info
                )
            )

            if os.path.exists(
                prepared
            ):

                if prepared.lower().endswith(
                    ".mp4"
                ):
                    return prepared

                base, _ = os.path.splitext(
                    prepared
                )

                mp4_path = (
                    base
                    +
                    ".mp4"
                )

                if os.path.exists(
                    mp4_path
                ):
                    return mp4_path

                return prepared

        except Exception:
            pass


    # -----------------------------------------------------
    # 3. latest mp4
    # -----------------------------------------------------

    latest_mp4 = _find_latest_mp4(
        output_path
    )

    if latest_mp4:
        return latest_mp4


    # -----------------------------------------------------
    # 4. latest video file
    # -----------------------------------------------------

    latest_video = _find_any_video(
        output_path
    )

    if latest_video:
        return latest_video


    return None


def _download_with_options(
    url,
    output_path,
    height,
    extra_options=None
):
    """
    Jalankan yt-dlp dengan konfigurasi tertentu.
    """

    from yt_dlp import YoutubeDL


    # -----------------------------------------------------
    # Format utama
    #
    # Prioritas:
    # 1. MP4 video + M4A audio
    # 2. MP4 single file
    # 3. video + audio generic
    # 4. single generic
    # -----------------------------------------------------

    format_selector = (
        f"bv*[height<={height}]"
        f"[ext=mp4]+"
        f"ba[ext=m4a]/"

        f"b[height<={height}]"
        f"[ext=mp4]/"

        f"bv*[height<={height}]"
        f"+ba/"

        f"b[height<={height}]/"

        f"best"
    )


    options = {

        "format":
            format_selector,

        "outtmpl":
            os.path.join(
                output_path,
                "%(title).180B.%(ext)s"
            ),

        "merge_output_format":
            "mp4",

        "noplaylist":
            True,

        "quiet":
            False,

        "no_warnings":
            False,

        "nocheckcertificate":
            True,

        "retries":
            5,

        "fragment_retries":
            5,

        "extractor_retries":
            5,

        "file_access_retries":
            5,

        "socket_timeout":
            60,

        "continuedl":
            True,

        "overwrites":
            True,

        "windowsfilenames":
            True,

        "concurrent_fragment_downloads":
            1,

    }

    cookies_file = os.environ.get("YOUTUBE_COOKIES_FILE")
    if cookies_file:
        options["cookiefile"] = cookies_file
        options["extractor_args"] = {
            "youtube": {
                "player_client": [
                    "web_safari",
                    "web_embedded",
                    "-tv_downgraded",
                ]
            }
        }


    if extra_options:
        options.update(
            extra_options
        )


    with YoutubeDL(
        options
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )


        if not info:

            raise RuntimeError(
                "yt-dlp tidak mendapatkan informasi video."
            )


        result = _find_downloaded_file(
            output_path,
            info=info,
            ydl=ydl
        )


        if result:

            return result


        raise RuntimeError(
            "yt-dlp selesai tetapi file video tidak ditemukan."
        )


def download_youtube(
    url,
    output_path,
    quality="720p"
):
    """
    Download video YouTube.

    Digunakan oleh Manual Cut dan Timeline Cut.

    quality:
        720p
        1080p
    """

    os.makedirs(
        output_path,
        exist_ok=True
    )


    requested_quality = str(
        quality
        or
        "720p"
    ).lower()


    if requested_quality not in (
        "720p",
        "1080p"
    ):

        requested_quality = "720p"


    height = (

        1080

        if requested_quality == "1080p"

        else

        720

    )


    errors = []


    # =====================================================
    # ATTEMPT 1
    # =====================================================

    try:

        return _download_with_options(

            url,

            output_path,

            height

        )

    except Exception as exc:

        errors.append(

            "Percobaan utama: "
            +
            str(exc)

        )


    # =====================================================
    # ATTEMPT 2
    #
    # Single-file fallback.
    # Tidak memerlukan merge video/audio.
    # =====================================================

    try:

        return _download_with_options(

            url,

            output_path,

            height,

            {

                "format":
                    (
                        f"b[height<={height}]"
                        f"[ext=mp4]/"
                        f"b[height<={height}]/"
                        f"best"
                    ),

                "merge_output_format":
                    "mp4",

            }

        )

    except Exception as exc:

        errors.append(

            "Fallback single-file: "
            +
            str(exc)

        )


    # =====================================================
    # ATTEMPT 3
    #
    # Format paling sederhana.
    # =====================================================

    try:

        return _download_with_options(

            url,

            output_path,

            height,

            {

                "format":
                    "best",

            }

        )

    except Exception as exc:

        errors.append(

            "Fallback best: "
            +
            str(exc)

        )


    # =====================================================
    # LAST CHANCE
    # =====================================================

    latest = _find_latest_mp4(
        output_path
    )

    if latest:
        return latest


    latest_video = _find_any_video(
        output_path
    )

    if latest_video:
        return latest_video


    raise RuntimeError(

        "Gagal mendownload video. "
        +
        " | ".join(errors)

    )


def cut_video_ffmpeg(
    input_path,
    output_path,
    start_sec,
    end_sec,
    orientation="landscape",
    quality="720p"
):
    """
    Potong video dengan FFmpeg.
    """

    quality = str(
        quality
        or
        "720p"
    ).lower()


    orientation = str(
        orientation
        or
        "landscape"
    ).lower()


    # =====================================================
    # RESOLUTION
    # =====================================================

    if orientation == "portrait":

        if quality == "1080p":

            width = 1080
            height = 1920

        else:

            width = 720
            height = 1280

    else:

        if quality == "1080p":

            width = 1920
            height = 1080

        else:

            width = 1280
            height = 720


    # =====================================================
    # VIDEO FILTER
    # =====================================================

    filter_complex = (

        f"[0:v]"
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
        f"[v]"

    )


    cmd = [

        "ffmpeg",

        "-hide_banner",

        "-loglevel",
        "error",

        "-ss",
        str(start_sec),

        "-to",
        str(end_sec),

        "-i",
        input_path,

        "-filter_complex",
        filter_complex,

        "-map",
        "[v]",

        "-map",
        "0:a?",

        "-c:v",
        "libx264",

        "-preset",
        "ultrafast",

        "-crf",
        "23",

        "-threads",
        "0",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-movflags",
        "+faststart",

        "-avoid_negative_ts",
        "make_zero",

        "-y",

        output_path,

    ]


    try:

        subprocess.run(

            cmd,

            check=True,

            capture_output=True,

            text=True,

        )

    except subprocess.CalledProcessError as exc:

        detail = (

            exc.stderr

            or

            exc.stdout

            or

            str(exc)

        ).strip()


        raise RuntimeError(

            f"FFmpeg gagal: {detail}"

        ) from exc


def create_zip(
    job_folder,
    zip_path
):
    """
    Buat ZIP dari semua file MP4.
    """

    with zipfile.ZipFile(

        zip_path,

        "w",

        compression=
            zipfile.ZIP_DEFLATED

    ) as zf:

        for name in os.listdir(
            job_folder
        ):

            if not name.lower().endswith(
                ".mp4"
            ):

                continue


            file_path = os.path.join(

                job_folder,

                name

            )


            if os.path.isfile(
                file_path
            ):

                zf.write(

                    file_path,

                    arcname=
                        name

                )
