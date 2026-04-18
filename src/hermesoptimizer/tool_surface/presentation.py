"""Tool Surface presentation layer (v0.8.0 Task 4).

This module provides the presentation-layer hardening for the Tool Surface IR.
It separates raw execution truth from LLM-facing rendering.

Key concerns:
- stable footer with status, duration, and truncation metadata
- overflow artifact handles for large output
- stderr retention on failure
- next-step navigation hints for large/failing output
- binary/media routing based on content, not just file extension

Design principles:
- deterministic and testable
- small pure functions and dataclasses
- reusable by later command-layer and audit outputs
- NOT a shell runtime or command parser
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# ExecutionResult — raw execution truth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionResult:
    """Captures raw execution truth from a tool or command surface.

    This is the raw output before any LLM-facing rendering. It preserves
    all information including stdout, stderr, exit code, and timing.

    Attributes:
        stdout: Raw stdout output (bytes or str depending on content)
        stderr: Raw stderr output
        exit_code: Exit code of the execution
        duration_seconds: Duration of execution in seconds (None if unknown)
    """

    stdout: str | bytes
    stderr: str
    exit_code: int
    duration_seconds: Optional[float] = None


# ---------------------------------------------------------------------------
# ContentType — content classification for routing
# ---------------------------------------------------------------------------


class ContentType(Enum):
    """Classification of content type for routing decisions.

    Unlike filename-based detection, this classifies based on actual
    content bytes (magic bytes, structure detection).
    """

    TEXTUAL = "textual"
    JSON = "json"
    BINARY = "binary"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    APPLICATION = "application"


# ---------------------------------------------------------------------------
# OverflowHandle — overflow/truncation metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OverflowHandle:
    """Describes how to access truncated or overflowed output.

    Attributes:
        was_truncated: True if output was truncated
        overflow_bytes: Number of bytes that were cut off (0 if not truncated)
    """

    was_truncated: bool
    overflow_bytes: int = 0


# ---------------------------------------------------------------------------
# Status — execution outcome
# ---------------------------------------------------------------------------


class Status(Enum):
    """Execution outcome status for footer rendering."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


# --------------------------------------------------------------------------~
# Priority — hint priority levels
# --------------------------------------------------------------------------~


class Priority(Enum):
    """Priority levels for next-step hints."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Module constant for stderr excerpt length limit
STDERR_EXCERPT_LENGTH: int = 500


# --------------------------------------------------------------------------
# NextStepHint — navigation guidance
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NextStepHint:
    """A navigation hint for the user/agent when output is large or failed.

    Attributes:
        hint: The hint text describing a suggested next step
        priority: Priority level, defaults to Priority.MEDIUM
    """

    hint: str
    priority: Priority = Priority.MEDIUM


# ---------------------------------------------------------------------------
# LLMRenderedOutput — LLM-facing rendered output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMRenderedOutput:
    """LLM-facing rendered output with stable metadata.

    This is the rendered representation designed for LLM consumption.
    It includes all the metadata needed for the LLM to understand
    the execution context and decide on next steps.

    Attributes:
        content: The rendered content (text for textual, placeholder for binary)
        status: Execution outcome status
        duration_seconds: Duration in seconds (None if unknown)
        overflow_handle: Overflow metadata if content was truncated (None otherwise)
        stderr_excerpt: Excerpt of stderr for failure cases (None on success)
        next_step_hints: List of navigation hints (empty if no hints)
        content_type: Classified content type
    """

    content: str
    duration_seconds: Optional[float] = None
    overflow_handle: Optional[OverflowHandle] = None
    stderr_excerpt: Optional[str] = None
    next_step_hints: list[NextStepHint] = field(default_factory=list)
    content_type: ContentType = ContentType.TEXTUAL
    status: Status = Status.SUCCESS


# ---------------------------------------------------------------------------
# Content classification
# ---------------------------------------------------------------------------


# Magic bytes for binary content detection
# Order matters: check more specific patterns before generic ones
_IMAGE_MAGIC = [
    (b"\x89PNG\r\n\x1a\n",),  # PNG
    (b"\xff\xd8\xff",),  # JPEG
    (b"GIF87a",),  # GIF87a
    (b"GIF89a",),  # GIF89a
    (b"\x00\x00\x01\x00",),  # ICO
]

_VIDEO_MAGIC = [
    (b"\x00\x00\x00\x18ftypisom",),  # MP4/M4V
    (b"\x00\x00\x00\x1cftypisom",),  # MP4/M4V
    (b"\x00\x00\x00\x20ftypisom",),  # MP4/M4V
    (b"\x1aE\xdf\xa3",),  # WebM
    (b"\x00\x00\x01\xb3",),  # MPEG1
    (b"\x00\x00\x01\xba",),  # MPEG2 PS
]

_AUDIO_MAGIC = [
    (b"ID3",),  # MP3 with ID3
    (b"\xff\xfb",),  # MP3 without ID3
    (b"\xff\xfa",),  # MP3 without ID3
    (b"\xff\xf3",),  # MP3 without ID3
    (b"\xff\xf2",),  # MP3 without ID3
    (b"OggS",),  # OGG
]


def _is_riff_wav(content: bytes) -> bool:
    """Check if RIFF header is actually a WAV file (not WebP or other RIFF formats)."""
    if not content.startswith(b"RIFF"):
        return False
    # WAV files have "WAVE" at offset 8
    if len(content) >= 12 and content[8:12] == b"WAVE":
        return True
    return False


def classify_content_type(content: bytes | str) -> ContentType:
    """Classify content type from bytes, not file extension.

    Uses magic bytes and structural detection to determine content type.
    This is more reliable than extension-based detection for cases where
    content is streamed or has non-standard filenames.

    Args:
        content: Raw content bytes or string

    Returns:
        ContentType classification
    """
    # Convert string to bytes if needed
    if isinstance(content, str):
        content = content.encode("utf-8", errors="replace")

    # Empty content defaults to textual
    if len(content) == 0:
        return ContentType.TEXTUAL

    # Check for JSON first (most common structured format)
    if _looks_like_json(content):
        return ContentType.JSON

    # Check for WAV audio before video/image (RIFF is ambiguous)
    if _is_riff_wav(content):
        return ContentType.AUDIO

    # Check for image formats
    for magic in _IMAGE_MAGIC:
        if content.startswith(magic[0]):
            return ContentType.IMAGE

    # Check for video formats
    for magic in _VIDEO_MAGIC:
        if content.startswith(magic[0]):
            return ContentType.VIDEO

    # Check for audio formats
    for magic in _AUDIO_MAGIC:
        if content.startswith(magic[0]):
            return ContentType.AUDIO

    # Check for PDF
    if content.startswith(b"%PDF-"):
        return ContentType.APPLICATION

    # Check for binary vs textual
    if _is_binary(content):
        return ContentType.BINARY

    return ContentType.TEXTUAL


def _looks_like_json(content: bytes) -> bool:
    """Check if content looks like JSON."""
    # Strip whitespace and check for JSON structural characters
    stripped = content.lstrip()
    if len(stripped) == 0:
        return False
    # JSON typically starts with { or [
    if stripped[0:1] in (b"{", b"["):
        return True
    # Also accept bare strings (JSON text)
    if stripped[0:1] == b'"':
        return True
    return False


def _is_binary(content: bytes) -> bool:
    """Check if content appears to be binary (contains null bytes or high proportion of non-printable)."""
    # Null bytes are strong indicator of binary
    if b"\x00" in content[:1024]:  # Check first 1KB
        return True

    # Count non-printable characters
    non_printable = 0
    sample = content[:512]
    for byte in sample:
        # Allow printable ASCII, common control chars (tab, newline, cr), and high bytes
        if byte < 32 and byte not in (9, 10, 13):  # Not tab, newline, or CR
            non_printable += 1
        elif byte > 127:
            # High bytes could be UTF-8 multi-byte chars, be conservative
            pass

    # If more than 10% non-printable, consider binary
    if len(sample) > 0 and non_printable / len(sample) > 0.1:
        return True

    return False


# ---------------------------------------------------------------------------
# Footer building
# ---------------------------------------------------------------------------


def build_footer(
    status: Status,
    duration_seconds: Optional[float] = None,
    overflow_handle: Optional[OverflowHandle] = None,
) -> str:
    """Build a stable footer string with status, duration, and truncation metadata.

    The footer provides a consistent, machine-parseable summary of the execution
    that can be appended to LLM output for reliable parsing.

    Args:
        status: Execution status
        duration_seconds: Duration in seconds (None if unknown)
        overflow_handle: Overflow metadata if content was truncated

    Returns:
        Footer string suitable for appending to LLM output
    """
    parts = [f"[status: {status.value}]"]

    if duration_seconds is not None:
        parts.append(f"[duration: {duration_seconds}s]")

    if overflow_handle is not None and overflow_handle.was_truncated:
        parts.append(f"[truncated: {overflow_handle.overflow_bytes} bytes overflow]")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Next-step suggestions
# ---------------------------------------------------------------------------


def suggested_next_steps(
    status: Status,
    stderr_excerpt: Optional[str],
    was_truncated: bool,
    content_type: Optional[ContentType] = None,
) -> list[NextStepHint]:
    """Generate navigation hints based on execution context.

    This function generates context-appropriate suggestions for what
    the user/agent should do next based on the execution outcome.

    Args:
        status: Execution status
        stderr_excerpt: Error excerpt if available
        was_truncated: Whether output was truncated
        content_type: Content type if available

    Returns:
        List of NextStepHint suggestions
    """
    hints: list[NextStepHint] = []

    # Failure hints
    if status == Status.FAILURE:
        if stderr_excerpt:
            stderr_lower = stderr_excerpt.lower()
            if "not found" in stderr_lower or "command not found" in stderr_lower:
                hints.append(
                    NextStepHint(
                        hint="Try using --help or -h to see available commands and usage",
                        priority=Priority.HIGH,
                    )
                )
            elif "permission" in stderr_lower or "denied" in stderr_lower:
                hints.append(
                    NextStepHint(
                        hint="Check file permissions or try running with elevated privileges",
                        priority=Priority.HIGH,
                    )
                )
            elif "timeout" in stderr_lower:
                hints.append(
                    NextStepHint(
                        hint="Try increasing the timeout or check network connectivity",
                        priority=Priority.HIGH,
                    )
                )
            else:
                hints.append(
                    NextStepHint(
                        hint="Review the error message above and check command syntax",
                        priority=Priority.MEDIUM,
                    )
                )
        else:
            hints.append(
                NextStepHint(
                    hint="Try using --help or -h to see available commands and usage",
                    priority=Priority.MEDIUM,
                )
            )

    # Timeout hints
    if status == Status.TIMEOUT:
        hints.append(
            NextStepHint(
                hint="Consider increasing the timeout threshold or breaking the task into smaller steps",
                priority=Priority.HIGH,
            )
        )

    # Truncation hints
    if was_truncated:
        if content_type == ContentType.BINARY:
            hints.append(
                NextStepHint(
                    hint="Output was truncated. Consider writing to a file instead of streaming",
                    priority=Priority.HIGH,
                )
            )
        else:
            hints.append(
                NextStepHint(
                    hint="Output was truncated. Consider using pagination or writing to a file",
                    priority=Priority.MEDIUM,
                )
            )

    # Large binary content hints
    if content_type == ContentType.BINARY and not was_truncated:
        hints.append(
            NextStepHint(
                hint="Binary content detected. Use file-based output for reliable retrieval",
                priority=Priority.MEDIUM,
            )
        )

    return hints


# ---------------------------------------------------------------------------
# Main rendering function
# ---------------------------------------------------------------------------


def render_for_llm(
    result: ExecutionResult,
    overflow_threshold: int = 1000,
) -> LLMRenderedOutput:
    """Render an ExecutionResult for LLM consumption.

    This function converts raw execution truth into an LLM-friendly output
    with appropriate metadata, hints, and content classification.

    Args:
        result: Raw execution result
        overflow_threshold: Max characters before considering output as overflow

    Returns:
        LLMRenderedOutput suitable for LLM consumption
    """
    # Determine status
    if result.exit_code == 0:
        status = Status.SUCCESS
    elif result.exit_code == 124:
        status = Status.TIMEOUT
    else:
        status = Status.FAILURE

    # Normalize stdout to string for content field
    stdout_content = result.stdout
    if isinstance(stdout_content, bytes):
        stdout_content_bytes = stdout_content
    else:
        stdout_content_bytes = stdout_content.encode("utf-8", errors="replace")

    # Classify content type from raw bytes
    content_type = classify_content_type(stdout_content_bytes)

    # Check for overflow
    overflow_handle: Optional[OverflowHandle] = None
    content_str = stdout_content if isinstance(stdout_content, str) else stdout_content.decode("utf-8", errors="replace")

    if len(content_str) > overflow_threshold:
        overflow_bytes = len(content_str) - overflow_threshold
        overflow_handle = OverflowHandle(was_truncated=True, overflow_bytes=overflow_bytes)
        content_str = content_str[:overflow_threshold]

    # Handle binary content - provide text placeholder
    if content_type == ContentType.BINARY:
        content_str = "[binary data]"

    # For image/video/audio, also provide placeholder
    elif content_type in (ContentType.IMAGE, ContentType.VIDEO, ContentType.AUDIO):
        content_str = "[{} content, {} bytes]".format(
            content_type.value,
            len(stdout_content_bytes) if isinstance(stdout_content, bytes) else len(stdout_content),
        )

    # Capture stderr excerpt on failure
    stderr_excerpt: Optional[str] = None
    if status == Status.FAILURE and result.stderr:
        # Take first STDERR_EXCERPT_LENGTH chars of stderr as excerpt
        stderr_excerpt = result.stderr[:STDERR_EXCERPT_LENGTH] if len(result.stderr) > STDERR_EXCERPT_LENGTH else result.stderr

    # Generate next-step hints
    next_step_hints = suggested_next_steps(
        status=status,
        stderr_excerpt=stderr_excerpt,
        was_truncated=overflow_handle.was_truncated if overflow_handle else False,
        content_type=content_type,
    )

    return LLMRenderedOutput(
        content=content_str,
        status=status,
        duration_seconds=result.duration_seconds,
        overflow_handle=overflow_handle,
        stderr_excerpt=stderr_excerpt,
        next_step_hints=next_step_hints,
        content_type=content_type,
    )
