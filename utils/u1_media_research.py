"""Native local media tools and an explicitly attributed research casebook.

The parent server calls handle_request after its normal safety gate. No media
URL, caller-supplied filesystem path, network lookup, or legacy OSINT tool runs.
"""

import base64
import hashlib
import hmac
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
from urllib.parse import parse_qs, urlsplit
import uuid

from utils import integrations_hub
from utils import prism_workspace as workspace


ENDPOINT = "/api/workspace/media-research"
MAX_FILE = 25 * 1024 * 1024
MAX_OUTPUT = 25 * 1024 * 1024
MAX_BODY = 65536
MAX_LOG = 65536
MAX_CASES = 200
MAX_EVIDENCE = 100
MAX_CAPTIONS = 48000
MAX_CLIP = 120
PROBE_TIMEOUT = 4
EXPORT_TIMEOUT = 12
MEDIA_TIMEOUT = 18
MAX_PROBE_BYTES = 4 * 1024 * 1024
MAX_PROBE_PACKETS = 50000
MEDIA_LOCK = threading.BoundedSemaphore(1)
FORMATS = {
    ".mp4": "mov", ".m4v": "mov", ".mov": "mov", ".m4a": "mov",
    ".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".ogg": "ogg",
    ".oga": "ogg", ".ogv": "ogg", ".webm": "matroska", ".mkv": "matroska",
    ".avi": "avi", ".aac": "aac",
}
NOTICE = ("Local, unencrypted research records. Verification labels are the author's "
          "assessment, not automatic identity verification. Source links are not fetched.")


def text(value, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Text is missing or exceeds the field limit.")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise ValueError("Control characters are not supported.")
    value = value.strip()
    if required and not value:
        raise ValueError("Complete the required field.")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Choose a valid local record or managed source ID.")
    return value


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def timestamp(value):
    value = text(value, 40, True)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError):
        raise ValueError("Use a valid timestamp with a timezone.") from None


def source_url(value):
    value = text(value, 2000, True)
    if any(c.isspace() for c in value) or "\\" in value:
        raise ValueError("Use an HTTP or HTTPS source URL without whitespace.")
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError()
        _ = parsed.port
    except ValueError:
        raise ValueError("Use an HTTP or HTTPS source URL without credentials.") from None
    return value


@contextmanager
def database():
    with workspace.database() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS u1_mr_cases (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, scope TEXT NOT NULL,
                notes TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS u1_mr_evidence (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
                source_url TEXT NOT NULL, note TEXT NOT NULL, label TEXT NOT NULL,
                verification_note TEXT NOT NULL, observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS u1_mr_evidence_case ON u1_mr_evidence(case_id);
        """)
        yield conn


def ffmpeg_binary():
    path = shutil.which("ffmpeg")
    if path:
        return path, "system PATH"
    # Resolve only the already installed wheel; never install or download here.
    try:
        module = importlib.import_module("imageio_ffmpeg")
        candidate = Path(module.get_ffmpeg_exe())
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate), "installed imageio_ffmpeg wheel"
    except (ImportError, OSError, ValueError, RuntimeError):
        pass
    return None, "unavailable"


def capabilities():
    binary, provider = ffmpeg_binary()
    return {
        "local_playback": True, "playback_codecs": "Browser-dependent",
        "srt_export": True, "ffmpeg_available": bool(binary), "ffmpeg_provider": provider,
        "ffmpeg_notice": "Executable detected; codec support is checked by the actual export."
        if binary else "FFmpeg is unavailable. Local playback and SRT export still work.",
        "max_file_bytes": MAX_FILE, "max_output_bytes": MAX_OUTPUT,
        "max_clip_seconds": MAX_CLIP, "probe_timeout_seconds": PROBE_TIMEOUT,
        "export_timeout_seconds": EXPORT_TIMEOUT,
        "network_media_download": False, "subscription_sync": False,
        "rdap": False, "automatic_osint": False, "external_search_handoffs": True,
    }


def media_row(row):
    return (row and row["status"] == "ready" and row["deleted"] is None
            and Path(row["name"]).suffix.lower() in FORMATS
            and 0 < row["size"] <= MAX_FILE and row["received"] == row["size"])


def snapshot():
    with database() as conn:
        cases = [dict(row) for row in conn.execute("""
            SELECT c.*, (SELECT COUNT(*) FROM u1_mr_evidence e WHERE e.case_id=c.id)
            AS evidence_count FROM u1_mr_cases c ORDER BY c.updated_at DESC LIMIT ?
        """, (MAX_CASES,))]
        media = [dict(id=row["id"], name=row["name"], size=row["size"], mime=row["mime"])
                 for row in conn.execute("SELECT * FROM files WHERE deleted IS NULL AND status='ready' ORDER BY created DESC")
                 if media_row(row)]
    return dict(success=True, capabilities=capabilities(), cases=cases, media=media, notice=NOTICE)


def case_detail(case_id):
    case_id = identifier(case_id)
    with database() as conn:
        row = conn.execute("SELECT * FROM u1_mr_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise ValueError("That case was not found.")
        case = dict(row)
        case["evidence"] = [dict(item) for item in conn.execute(
            "SELECT * FROM u1_mr_evidence WHERE case_id=? ORDER BY created_at,id", (case_id,))]
    return dict(success=True, case=case, notice=NOTICE)


def unchanged(row, body):
    if not row:
        raise ValueError("That record was not found.")
    if body.get("expected_updated") != row["updated_at"]:
        raise ValueError("This record changed. Reload it before saving or deleting.")


def record_action(body):
    action = body["action"]
    with database() as conn:
        if action == "case_save":
            if body.get("authorised_confirmed") is not True:
                raise ValueError("Confirm this research uses public or authorised information.")
            title = text(body.get("title"), 160, True)
            notes = text(body.get("notes", ""), 8000)
            scope = body.get("scope")
            if scope not in {"public", "authorised"}:
                raise ValueError("Choose public or authorised research.")
            created = now()
            if body.get("id"):
                case_id = identifier(body["id"])
                row = conn.execute("SELECT * FROM u1_mr_cases WHERE id=?", (case_id,)).fetchone()
                unchanged(row, body)
                conn.execute("UPDATE u1_mr_cases SET title=?,scope=?,notes=?,updated_at=? WHERE id=?",
                             (title, scope, notes, created, case_id))
            else:
                if conn.execute("SELECT COUNT(*) FROM u1_mr_cases").fetchone()[0] >= MAX_CASES:
                    raise ValueError("The casebook is full. Export cases before removing any.")
                case_id = uuid.uuid4().hex
                conn.execute("INSERT INTO u1_mr_cases VALUES(?,?,?,?,?,?)",
                             (case_id, title, scope, notes, created, created))
            return dict(success=True, id=case_id, updated_at=created)
        if action == "case_delete":
            case_id = identifier(body.get("id"))
            row = conn.execute("SELECT * FROM u1_mr_cases WHERE id=?", (case_id,)).fetchone()
            unchanged(row, body)
            conn.execute("DELETE FROM u1_mr_evidence WHERE case_id=?", (case_id,))
            conn.execute("DELETE FROM u1_mr_cases WHERE id=?", (case_id,))
            return dict(success=True)
        case_id = identifier(body.get("case_id"))
        if not conn.execute("SELECT id FROM u1_mr_cases WHERE id=?", (case_id,)).fetchone():
            raise ValueError("That case was not found.")
        evidence_id = identifier(body["id"]) if body.get("id") else None
        if action == "evidence_delete":
            row = conn.execute("SELECT * FROM u1_mr_evidence WHERE id=? AND case_id=?",
                               (evidence_id, case_id)).fetchone()
            unchanged(row, body)
            conn.execute("DELETE FROM u1_mr_evidence WHERE id=?", (evidence_id,))
            conn.execute("UPDATE u1_mr_cases SET updated_at=? WHERE id=?", (now(), case_id))
            return dict(success=True)
        title = text(body.get("title"), 160, True)
        url = source_url(body.get("source_url"))
        note = text(body.get("note", ""), 8000, True)
        label = body.get("label", "unverified")
        if label not in {"verified", "unverified"}:
            raise ValueError("Choose verified or unverified.")
        verification = text(body.get("verification_note", ""), 1200, label == "verified")
        observed = timestamp(body["observed_at"]) if body.get("observed_at") else now()
        updated = now()
        values = (title, url, note, label, verification, observed)
        if evidence_id:
            row = conn.execute("SELECT * FROM u1_mr_evidence WHERE id=? AND case_id=?",
                               (evidence_id, case_id)).fetchone()
            unchanged(row, body)
            conn.execute("""UPDATE u1_mr_evidence SET title=?,source_url=?,note=?,label=?,
                verification_note=?,observed_at=?,updated_at=? WHERE id=?""", (*values, updated, evidence_id))
        else:
            if conn.execute("SELECT COUNT(*) FROM u1_mr_evidence WHERE case_id=?", (case_id,)).fetchone()[0] >= MAX_EVIDENCE:
                raise ValueError("This case has reached its 100-evidence limit.")
            evidence_id = uuid.uuid4().hex
            conn.execute("INSERT INTO u1_mr_evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (evidence_id, case_id, *values, updated, updated))
        conn.execute("UPDATE u1_mr_cases SET updated_at=? WHERE id=?", (updated, case_id))
        return dict(success=True, id=evidence_id, case_id=case_id, updated_at=updated)


def download(raw, filename, mime, **extra):
    if len(raw) > MAX_OUTPUT:
        raise ValueError("The export exceeds the 25 MB output limit.")
    return dict(success=True, filename=filename, mime=mime, size=len(raw),
                content=base64.b64encode(raw).decode("ascii"), **extra)


def export_case(case_id):
    detail = case_detail(case_id)
    payload = dict(format="u1-research-casebook", version=1, exported_at=now(),
                   case=detail["case"], notice=NOTICE)
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return download(raw, "research-case-" + detail["case"]["id"] + ".json", "application/json")


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Clip times must be finite numbers in seconds.")
    if not 0 <= value <= 86400:
        raise ValueError("Clip times must be between zero and 24 hours.")
    return float(value)


def clip_range(body, duration=None):
    start, end = seconds(body.get("clip_in")), seconds(body.get("clip_out"))
    if end <= start or end - start > MAX_CLIP:
        raise ValueError("Choose an increasing clip range of at most 120 seconds.")
    if duration is not None and (start >= duration or end > duration + 0.05):
        raise ValueError("The clip range extends beyond this media file.")
    return start, end


def srt_time(value):
    match = re.fullmatch(r"(\d{2}):([0-5]\d):([0-5]\d),(\d{3})", value)
    if not match:
        raise ValueError("Use SRT timestamps such as 00:00:01,250.")
    h, m, s, ms = map(int, match.groups())
    total = ((h * 60 + m) * 60 + s) * 1000 + ms
    if total > 86400000:
        raise ValueError("Caption timestamps must stay within 24 hours.")
    return total


def parse_srt(value):
    value = text(value, MAX_CAPTIONS).replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if not value:
        return []
    blocks = re.split(r"\n[ \t]*\n", value)
    if len(blocks) > 500:
        raise ValueError("Use at most 500 caption cues.")
    cues, previous = [], 0
    for index, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if len(lines) < 3 or lines[0].strip() != str(index):
            raise ValueError("Number SRT cues consecutively from 1, with a blank line between cues.")
        pair = lines[1].split(" --> ")
        if len(pair) != 2:
            raise ValueError("Separate SRT timestamps with ' --> '.")
        start, end = map(srt_time, pair)
        content = "\n".join(lines[2:]).strip()
        if start < previous or end <= start or not content or "<" in content or ">" in content:
            raise ValueError("Use ordered, non-overlapping captions with plain text and increasing times.")
        cues.append((start, end, content))
        previous = end
    return cues


def format_srt_time(value):
    seconds_total, ms = divmod(value, 1000)
    minutes, sec = divmod(seconds_total, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}:{sec:02d},{ms:03d}"


def captions_export(body):
    if body.get("rights_confirmed") is not True:
        raise ValueError("Confirm that you have permission to use and export this material.")
    cues = parse_srt(body.get("captions", ""))
    if not cues:
        raise ValueError("Add at least one caption before exporting.")
    if body.get("trim_to_clip") is True:
        start, end = clip_range(body)
        lo, hi = round(start * 1000), round(end * 1000)
        if (end - start) * 1000 < 1 - 1e-7 or hi <= lo:
            raise ValueError("SRT clips must span at least one representable millisecond.")
        cues = [(max(a, lo) - lo, min(b, hi) - lo, line) for a, b, line in cues if b > lo and a < hi]
    if not cues:
        raise ValueError("There are no captions inside the selected clip.")
    output = "\n\n".join(f"{i}\n{format_srt_time(a)} --> {format_srt_time(b)}\n{line}"
                         for i, (a, b, line) in enumerate(cues, 1)) + "\n"
    return download(output.encode("utf-8"), "captions.srt", "application/x-subrip", cues=len(cues))


def managed_source(source_id):
    source_id = identifier(source_id)
    with workspace.database() as conn:
        row = conn.execute("SELECT * FROM files WHERE id=?", (source_id,)).fetchone()
        if not media_row(row):
            raise ValueError("Choose a completed, supported managed audio or video upload of at most 25 MB.")
        metadata = dict(row)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        # Open both directories without following symlinks, then the ID relative
        # to the held directory FD. This also avoids a check/open replacement race.
        data_fd = os.open(workspace.DATA, flags | os.O_DIRECTORY)
        try:
            files_fd = os.open("files", flags | os.O_DIRECTORY, dir_fd=data_fd)
            try:
                fd = os.open(source_id, flags | os.O_NONBLOCK, dir_fd=files_fd)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size != metadata["size"]:
                        raise ValueError("The managed upload is incomplete or unavailable.")
                    raw = stream.read(MAX_FILE + 1)
            finally:
                os.close(files_fd)
        finally:
            os.close(data_fd)
    except OSError:
        raise ValueError("The managed upload is unavailable. Import it again.") from None
    if len(raw) != metadata["size"] or len(raw) > MAX_FILE:
        raise ValueError("The managed upload changed or exceeds the file limit.")
    if metadata["checksum"] and not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), metadata["checksum"]):
        raise ValueError("The managed upload checksum changed. Import it again.")
    return metadata, raw


def run_bounded(arguments, timeout, *, stdout_line=None):
    """Bound diagnostics; optionally consume structured stdout separately.

    Decoder diagnostics and metadata must never be parsed as structured results.
    Both pipes are drained concurrently, with bounded records and byte counts.
    """
    process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE if stdout_line else subprocess.STDOUT,
                               shell=False, close_fds=True)
    log, overflow = bytearray(), threading.Event()
    structured_errors = []

    def drain():
        try:
            pipe = process.stderr if stdout_line else process.stdout
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                remaining = MAX_LOG - len(log)
                log.extend(chunk[:max(0, remaining)])
                if len(chunk) > remaining:
                    overflow.set()
                    process.kill()
                    break
        except (OSError, ValueError):
            pass

    def structured():
        total = 0
        try:
            while True:
                line = process.stdout.readline(1025)
                if not line:
                    break
                total += len(line)
                if len(line) > 1024 or total > MAX_PROBE_BYTES:
                    raise ValueError("Decoded stream data exceeded its bounded probe limit.")
                stdout_line(line.decode("ascii"))
        except (ValueError, OSError) as error:
            structured_errors.append(error)
            process.kill()

    readers = [threading.Thread(target=drain, daemon=True)]
    if stdout_line:
        readers.append(threading.Thread(target=structured, daemon=True))
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise ValueError("FFmpeg reached its time limit. Try a shorter clip or smaller source.") from None
    finally:
        for reader in readers:
            reader.join(timeout=1)
        process.stdout.close()
        if stdout_line:
            process.stderr.close()
    if overflow.is_set():
        raise ValueError("FFmpeg exceeded its diagnostic output limit.")
    if structured_errors or any(reader.is_alive() for reader in readers):
        raise ValueError("FFmpeg returned invalid or excessive decoded stream data.")
    return process.returncode, bytes(log)


def input_options(metadata, source):
    demuxer = FORMATS[Path(metadata["name"]).suffix.lower()]
    options = ["-protocol_whitelist", "file,pipe", "-format_whitelist", demuxer, "-f", demuxer]
    if demuxer == "mov":
        options += ["-enable_drefs", "0", "-use_absolute_path", "0"]
    return options + ["-i", str(source)]


class DecodedStreams:
    """Aggregate FFmpeg framehash records, never tags or human-readable logs."""

    def __init__(self):
        self.streams = {}
        self.packets = 0

    def line(self, line):
        line = line.strip()
        if not line:
            return
        if line.startswith("#"):
            header = re.fullmatch(r"#(tb|media_type|codec_id|sample_rate|dimensions) ([01]): (.+)", line)
            if header:
                key, index, value = header.groups()
                stream = self.streams.setdefault(int(index), {})
                if key in stream:
                    raise ValueError("Duplicate decoded stream header.")
                if key == "tb":
                    if not re.fullmatch(r"[1-9]\d{0,8}/[1-9]\d{0,8}", value):
                        raise ValueError("Invalid decoded time base.")
                    value = Fraction(value)
                elif key == "sample_rate":
                    if not re.fullmatch(r"[1-9]\d{0,5}", value):
                        raise ValueError("Invalid decoded sample rate.")
                    value = int(value)
                stream[key] = value
            return
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 6 or any(not re.fullmatch(r"-?\d{1,18}", value) for value in fields[:5]) or not re.fullmatch(r"[a-fA-F0-9]{8}", fields[5]):
            raise ValueError("Invalid decoded frame record.")
        index, _, pts, duration, size = map(int, fields[:5])
        stream = self.streams.get(index, {})
        if "tb" not in stream or duration <= 0 or size <= 0 or abs(pts * stream["tb"]) > 86400:
            raise ValueError("Missing or invalid decoded frame timing.")
        if "end" in stream and pts < stream["end"]:
            raise ValueError("Overlapping decoded timestamps are unsupported.")
        self.packets += 1
        if self.packets > MAX_PROBE_PACKETS:
            raise ValueError("Decoded stream packet limit exceeded.")
        stream.setdefault("start", pts)
        stream["end"] = pts + duration
        stream["units"] = stream.get("units", 0) + duration
        stream["packets"] = stream.get("packets", 0) + 1
        stream["bytes"] = stream.get("bytes", 0) + size

    def result(self):
        result = []
        for stream in self.streams.values():
            if not stream.get("packets"):
                continue
            kind = stream.get("media_type")
            if kind not in {"audio", "video"} or stream.get("codec_id") != ("pcm_s16le" if kind == "audio" else "rawvideo"):
                raise ValueError("Unsupported decoded stream description.")
            duration = stream["units"] * stream["tb"]
            end = stream["end"] * stream["tb"]
            span = (stream["end"] - stream["start"]) * stream["tb"]
            if not 0 < duration <= 86400 or not 0 < end <= 86400 or not 0 < span <= 86400:
                raise ValueError("Decoded stream duration is unavailable or exceeds 24 hours.")
            item = dict(kind=kind, decoded_duration_seconds=float(duration), end_seconds=float(end),
                        span_seconds=float(span), tick_seconds=float(stream["tb"]),
                        video_frames=stream["packets"] if kind == "video" else 0, audio_samples=0)
            if kind == "audio":
                samples = duration * stream.get("sample_rate", 0)
                if samples.denominator != 1 or samples <= 0 or stream["bytes"] < samples * 2:
                    raise ValueError("Decoded audio has no complete PCM samples.")
                item["audio_samples"] = int(samples)
            result.append(item)
        if not result:
            raise ValueError("This file has no decodable audio samples or video frames.")
        return dict(duration_seconds=max(item["end_seconds"] for item in result),
                    audio=any(item["kind"] == "audio" for item in result),
                    video=any(item["kind"] == "video" for item in result), streams=result,
                    metadata_source="FFmpeg decoded frame/sample checksums; not metadata tags")


def probe(binary, metadata, source, timeout=PROBE_TIMEOUT):
    decoded = DecodedStreams()
    code, _ = run_bounded([
        binary, "-hide_banner", "-nostdin", "-loglevel", "error", "-xerror", "-threads", "2",
        *input_options(metadata, source), "-map", "0:v:0?", "-map", "0:a:0?",
        "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn",
        "-c:v", "rawvideo", "-c:a", "pcm_s16le", "-fps_mode", "passthrough",
        "-threads", "2", "-f", "framehash", "-hash", "crc32", "pipe:1",
    ], timeout, stdout_line=decoded.line)
    if code != 0:
        raise ValueError("FFmpeg could not fully decode this file within the probe limits. Browser playback may still work.")
    return decoded.result()


def validate_output(binary, output, output_format, requested, source_info, timeout):
    decoded = probe(binary, {"name": output.name}, output, timeout)
    required = {"audio"} if output_format == "wav" else {"video"}
    if output_format == "mp4" and source_info["audio"]:
        required.add("audio")
    for kind in required:
        stream = next((item for item in decoded["streams"] if item["kind"] == kind), None)
        if stream is None:
            raise ValueError("The exported clip is missing required decoded frames or audio samples.")
        tolerance = 0.05 if kind == "audio" else max(0.05, min(0.5, stream["tick_seconds"] + 0.001))
        if abs(stream["decoded_duration_seconds"] - requested) > tolerance or abs(stream["span_seconds"] - requested) > tolerance:
            raise ValueError("The decoded export does not cover the requested clip duration. Choose a supported shorter range.")
    return {"method": "decoded_frame_and_sample_checksums", "duration_seconds": decoded["duration_seconds"],
            "video_frames": sum(item["video_frames"] for item in decoded["streams"]),
            "audio_samples": sum(item["audio_samples"] for item in decoded["streams"])}


def media_action(body):
    if body["action"] == "clip_export":
        if body.get("rights_confirmed") is not True:
            raise ValueError("Confirm that you have permission to use and export this material.")
        clip_range(body)
        if body.get("format") not in {"mp4", "wav"}:
            raise ValueError("Choose MP4 video or WAV audio.")
    binary, provider = ffmpeg_binary()
    if not binary:
        raise ValueError("FFmpeg is unavailable. Install a trusted FFmpeg or imageio_ffmpeg wheel; playback and SRT export work now.")
    if not MEDIA_LOCK.acquire(blocking=False):
        raise ValueError("Another local media operation is running. Try again after it finishes.")
    try:
        deadline = time.monotonic() + MEDIA_TIMEOUT

        def remaining(limit):
            value = min(limit, deadline - time.monotonic())
            if value <= 0:
                raise ValueError("Media verification reached its total time limit. Try a shorter clip or smaller source.")
            return value

        metadata, raw = managed_source(body.get("source_id"))
        with tempfile.TemporaryDirectory(prefix="u1-media-research-") as directory:
            source = Path(directory) / ("source" + Path(metadata["name"]).suffix.lower())
            source.write_bytes(raw)
            del raw
            info = probe(binary, metadata, source, remaining(PROBE_TIMEOUT))
            if body["action"] == "inspect":
                return dict(success=True, source_id=metadata["id"], name=metadata["name"], size=metadata["size"], **info)
            start, end = clip_range(body, info["duration_seconds"])
            if (end - start) * 1000 < 1 - 1e-7:
                raise ValueError("Media clips must span at least one millisecond.")
            output_format = body["format"]
            if output_format == "wav" and not info["audio"]:
                raise ValueError("This source does not contain an audio stream.")
            if output_format == "mp4" and not info["video"]:
                raise ValueError("Choose WAV for an audio-only source.")
            output = Path(directory) / ("clip." + output_format)
            arguments = [binary, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                         "-threads", "2", *input_options(metadata, source), "-ss", f"{start:.6f}",
                         "-t", f"{end - start:.6f}", "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn"]
            if output_format == "wav":
                arguments += ["-map", "0:a:0", "-vn", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2"]
            else:
                arguments += ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "ultrafast",
                              "-crf", "26", "-pix_fmt", "yuv420p", "-vf",
                              "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
                              "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"]
            arguments += ["-threads", "2", "-fs", str(MAX_OUTPUT), "-f", output_format, str(output)]
            code, _ = run_bounded(arguments, remaining(EXPORT_TIMEOUT))
            if code != 0 or not output.is_file() or output.stat().st_size <= 0:
                raise ValueError("FFmpeg could not create this clip. The file or installed codecs may be unsupported.")
            if output.stat().st_size >= MAX_OUTPUT - 65536:
                raise ValueError("The clip reached the output limit. Choose a shorter range.")
            validation = validate_output(binary, output, output_format, end - start, info, remaining(PROBE_TIMEOUT))
            return download(output.read_bytes(), "clip." + output_format,
                            "video/mp4" if output_format == "mp4" else "audio/wav",
                            engine="FFmpeg", provider=provider, clip_in=start, clip_out=end,
                            validation=validation,
                            captions="Export edited captions separately as an SRT sidecar.")
    finally:
        MEDIA_LOCK.release()


def action(body):
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object.")
    name = body.get("action")
    if name in {"case_save", "case_delete", "evidence_save", "evidence_delete"}:
        return record_action(body)
    if name == "srt_export":
        return captions_export(body)
    if name in {"inspect", "clip_export"}:
        return media_action(body)
    raise ValueError("That Media and Research action is not supported.")


def handle_request(handler):
    parsed = urlsplit(handler.path)
    if parsed.path.rstrip("/") != ENDPOINT:
        return False
    if not handler.integration_request_allowed():
        handler.send_json(dict(success=False, error="Local same-origin request required."), 403)
        return True
    if handler.command not in {"GET", "POST"}:
        handler.send_json(dict(success=False, error="Use GET or POST for this endpoint."), 405)
        return True
    if handler.command == "POST":
        token = handler.headers.get("X-U1-CSRF", "")
        if not token or len(token) > 512 or not hmac.compare_digest(token.encode("utf-8"), integrations_hub.CSRF_TOKEN.encode("utf-8")):
            handler.send_json(dict(success=False, error="Reload the workspace before saving or exporting."), 403)
            return True
    try:
        if handler.command == "GET":
            query = parse_qs(parsed.query)
            if "export" in query:
                result = export_case(query["export"][0])
            elif "case_id" in query:
                result = case_detail(query["case_id"][0])
            else:
                result = snapshot()
        else:
            if handler.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported here.")
            if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("Send a JSON request body.")
            length = int(handler.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("The request body must be between 1 and 65536 bytes.")
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise ValueError("The request body was incomplete.")
            result = action(json.loads(raw))
        handler.send_json(result)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Invalid Media and Research request."
        handler.send_json(dict(success=False, error=message), 400)
    except (OSError, RuntimeError, sqlite3.Error):
        handler.send_json(dict(success=False, error="The local media or casebook service is unavailable. No export was completed."), 503)
    return True
