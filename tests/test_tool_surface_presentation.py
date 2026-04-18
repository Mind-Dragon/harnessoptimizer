"""Tests for Tool Surface presentation layer (v0.8.0 Task 4).

This module tests the presentation-layer hardening module that separates
raw execution truth from LLM-facing rendering.

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

import pytest


class TestExecutionResultDataclass:
    """ExecutionResult must capture raw execution truth."""

    def test_execution_result_exists(self) -> None:
        """ExecutionResult must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        assert ExecutionResult is not None

    def test_execution_result_has_stdout(self) -> None:
        """ExecutionResult must have stdout field."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(stdout="hello world", stderr="", exit_code=0)
        assert result.stdout == "hello world"

    def test_execution_result_has_stderr(self) -> None:
        """ExecutionResult must have stderr field."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(stdout="", stderr="error message", exit_code=1)
        assert result.stderr == "error message"

    def test_execution_result_has_exit_code(self) -> None:
        """ExecutionResult must have exit_code field."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(stdout="output", stderr="", exit_code=0)
        assert result.exit_code == 0

    def test_execution_result_has_duration_seconds(self) -> None:
        """ExecutionResult must have duration_seconds field."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(
            stdout="output", stderr="", exit_code=0, duration_seconds=1.5
        )
        assert result.duration_seconds == 1.5

    def test_execution_result_duration_defaults_to_none(self) -> None:
        """ExecutionResult.duration_seconds must default to None."""
        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(stdout="output", stderr="", exit_code=0)
        assert result.duration_seconds is None

    def test_execution_result_is_frozen(self) -> None:
        """ExecutionResult must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        result = ExecutionResult(stdout="output", stderr="", exit_code=0)
        with pytest.raises(FrozenInstanceError):
            result.stdout = "modified"

    def test_execution_result_is_dataclass(self) -> None:
        """ExecutionResult must be a dataclass."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.presentation import ExecutionResult

        assert is_dataclass(ExecutionResult)


class TestContentTypeEnum:
    """ContentType must classify content for routing decisions."""

    def test_content_type_enum_exists(self) -> None:
        """ContentType must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType is not None

    def test_content_type_has_textual(self) -> None:
        """ContentType must have TEXTUAL variant for plain text."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.TEXTUAL is not None
        assert ContentType.TEXTUAL.value == "textual"

    def test_content_type_has_json(self) -> None:
        """ContentType must have JSON variant."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.JSON is not None
        assert ContentType.JSON.value == "json"

    def test_content_type_has_binary(self) -> None:
        """ContentType must have BINARY variant."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.BINARY is not None
        assert ContentType.BINARY.value == "binary"

    def test_content_type_has_image(self) -> None:
        """ContentType must have IMAGE variant."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.IMAGE is not None
        assert ContentType.IMAGE.value == "image"

    def test_content_type_has_video(self) -> None:
        """ContentType must have VIDEO variant."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.VIDEO is not None
        assert ContentType.VIDEO.value == "video"

    def test_content_type_has_audio(self) -> None:
        """ContentType must have AUDIO variant."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.AUDIO is not None
        assert ContentType.AUDIO.value == "audio"

    def test_content_type_has_application(self) -> None:
        """ContentType must have APPLICATION variant for other binary formats."""
        from hermesoptimizer.tool_surface.presentation import ContentType

        assert ContentType.APPLICATION is not None
        assert ContentType.APPLICATION.value == "application"


class TestOverflowHandle:
    """OverflowHandle must describe how to access truncated/large output."""

    def test_overflow_handle_exists(self) -> None:
        """OverflowHandle must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        assert OverflowHandle is not None

    def test_overflow_handle_has_truncated_flag(self) -> None:
        """OverflowHandle must have was_truncated field."""
        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        handle = OverflowHandle(was_truncated=True, overflow_bytes=1000)
        assert handle.was_truncated is True

    def test_overflow_handle_has_overflow_bytes(self) -> None:
        """OverflowHandle must have overflow_bytes field."""
        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        handle = OverflowHandle(was_truncated=True, overflow_bytes=1000)
        assert handle.overflow_bytes == 1000

    def test_overflow_handle_overflow_bytes_defaults_to_zero(self) -> None:
        """OverflowHandle.overflow_bytes must default to 0."""
        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        handle = OverflowHandle(was_truncated=False)
        assert handle.overflow_bytes == 0

    def test_overflow_handle_is_frozen(self) -> None:
        """OverflowHandle must be immutable."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        handle = OverflowHandle(was_truncated=True)
        with pytest.raises(FrozenInstanceError):
            handle.was_truncated = False

    def test_overflow_handle_is_dataclass(self) -> None:
        """OverflowHandle must be a dataclass."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.presentation import OverflowHandle

        assert is_dataclass(OverflowHandle)


class TestStatusEnum:
    """Status must indicate execution outcome for footer rendering."""

    def test_status_enum_exists(self) -> None:
        """Status must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import Status

        assert Status is not None

    def test_status_has_success(self) -> None:
        """Status must have SUCCESS variant."""
        from hermesoptimizer.tool_surface.presentation import Status

        assert Status.SUCCESS is not None
        assert Status.SUCCESS.value == "success"

    def test_status_has_failure(self) -> None:
        """Status must have FAILURE variant."""
        from hermesoptimizer.tool_surface.presentation import Status

        assert Status.FAILURE is not None
        assert Status.FAILURE.value == "failure"

    def test_status_has_timeout(self) -> None:
        """Status must have TIMEOUT variant."""
        from hermesoptimizer.tool_surface.presentation import Status

        assert Status.TIMEOUT is not None
        assert Status.TIMEOUT.value == "timeout"

    def test_status_has_partial(self) -> None:
        """Status must have PARTIAL variant for partial success."""
        from hermesoptimizer.tool_surface.presentation import Status

        assert Status.PARTIAL is not None
        assert Status.PARTIAL.value == "partial"


class TestPriorityEnum:
    """Priority must be an enum for NextStepHint priority levels."""

    def test_priority_enum_exists(self) -> None:
        """Priority must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import Priority

        assert Priority is not None

    def test_priority_has_high(self) -> None:
        """Priority must have HIGH variant."""
        from hermesoptimizer.tool_surface.presentation import Priority

        assert Priority.HIGH is not None
        assert Priority.HIGH.value == "high"

    def test_priority_has_medium(self) -> None:
        """Priority must have MEDIUM variant."""
        from hermesoptimizer.tool_surface.presentation import Priority

        assert Priority.MEDIUM is not None
        assert Priority.MEDIUM.value == "medium"

    def test_priority_has_low(self) -> None:
        """Priority must have LOW variant."""
        from hermesoptimizer.tool_surface.presentation import Priority

        assert Priority.LOW is not None
        assert Priority.LOW.value == "low"


class TestNextStepHint:
    """NextStepHint must provide navigation guidance for large/failing output."""

    def test_next_step_hint_exists(self) -> None:
        """NextStepHint must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import NextStepHint

        assert NextStepHint is not None

    def test_next_step_hint_has_hint_text(self) -> None:
        """NextStepHint must have hint field."""
        from hermesoptimizer.tool_surface.presentation import NextStepHint

        hint = NextStepHint(hint="Try increasing the page size")
        assert hint.hint == "Try increasing the page size"

    def test_next_step_hint_has_priority(self) -> None:
        """NextStepHint must have priority field."""
        from hermesoptimizer.tool_surface.presentation import Priority, NextStepHint

        hint = NextStepHint(hint="Try something", priority=Priority.HIGH)
        assert hint.priority == Priority.HIGH

    def test_next_step_hint_priority_defaults_to_medium(self) -> None:
        """NextStepHint.priority must default to Priority.MEDIUM."""
        from hermesoptimizer.tool_surface.presentation import Priority, NextStepHint

        hint = NextStepHint(hint="Try something")
        assert hint.priority == Priority.MEDIUM

    def test_next_step_hint_is_frozen(self) -> None:
        """NextStepHint must be immutable."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.presentation import NextStepHint

        hint = NextStepHint(hint="Try something")
        with pytest.raises(FrozenInstanceError):
            hint.hint = "Modified"

    def test_next_step_hint_is_dataclass(self) -> None:
        """NextStepHint must be a dataclass."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.presentation import NextStepHint

        assert is_dataclass(NextStepHint)


class TestLLMRenderedOutput:
    """LLMRenderedOutput must wrap execution result with LLM-friendly metadata."""

    def test_llm_rendered_output_exists(self) -> None:
        """LLMRenderedOutput must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        assert LLMRenderedOutput is not None

    def test_llm_rendered_output_has_content(self) -> None:
        """LLMRenderedOutput must have content field."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="rendered output")
        assert output.content == "rendered output"

    def test_llm_rendered_output_has_status(self) -> None:
        """LLMRenderedOutput must have status field."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput, Status

        output = LLMRenderedOutput(content="output", status=Status.SUCCESS)
        assert output.status == Status.SUCCESS

    def test_llm_rendered_output_has_duration_seconds(self) -> None:
        """LLMRenderedOutput must have duration_seconds field."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output", duration_seconds=2.5)
        assert output.duration_seconds == 2.5

    def test_llm_rendered_output_duration_defaults_to_none(self) -> None:
        """LLMRenderedOutput.duration_seconds must default to None."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output")
        assert output.duration_seconds is None

    def test_llm_rendered_output_has_overflow_handle(self) -> None:
        """LLMRenderedOutput must have overflow_handle field."""
        from hermesoptimizer.tool_surface.presentation import (
            LLMRenderedOutput,
            OverflowHandle,
        )

        handle = OverflowHandle(was_truncated=True, overflow_bytes=500)
        output = LLMRenderedOutput(content="truncated...", overflow_handle=handle)
        assert output.overflow_handle is not None
        assert output.overflow_handle.was_truncated is True

    def test_llm_rendered_output_overflow_handle_defaults_to_none(self) -> None:
        """LLMRenderedOutput.overflow_handle must default to None."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output")
        assert output.overflow_handle is None

    def test_llm_rendered_output_has_stderr_excerpt(self) -> None:
        """LLMRenderedOutput must have stderr_excerpt field."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output", stderr_excerpt="error: not found")
        assert output.stderr_excerpt == "error: not found"

    def test_llm_rendered_output_stderr_excerpt_defaults_to_none(self) -> None:
        """LLMRenderedOutput.stderr_excerpt must default to None."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output")
        assert output.stderr_excerpt is None

    def test_llm_rendered_output_has_next_step_hints(self) -> None:
        """LLMRenderedOutput must have next_step_hints field."""
        from hermesoptimizer.tool_surface.presentation import (
            LLMRenderedOutput,
            NextStepHint,
        )

        hints = [NextStepHint(hint="Try --help for usage")]
        output = LLMRenderedOutput(content="output", next_step_hints=hints)
        assert output.next_step_hints is not None
        assert len(output.next_step_hints) == 1

    def test_llm_rendered_output_next_step_hints_defaults_to_empty(self) -> None:
        """LLMRenderedOutput.next_step_hints must default to empty list."""
        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output")
        assert output.next_step_hints == []

    def test_llm_rendered_output_has_content_type(self) -> None:
        """LLMRenderedOutput must have content_type field."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            LLMRenderedOutput,
        )

        output = LLMRenderedOutput(content="json data", content_type=ContentType.JSON)
        assert output.content_type == ContentType.JSON

    def test_llm_rendered_output_content_type_defaults_to_textual(self) -> None:
        """LLMRenderedOutput.content_type must default to TEXTUAL."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            LLMRenderedOutput,
        )

        output = LLMRenderedOutput(content="plain text")
        assert output.content_type == ContentType.TEXTUAL

    def test_llm_rendered_output_is_frozen(self) -> None:
        """LLMRenderedOutput must be immutable."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        output = LLMRenderedOutput(content="output")
        with pytest.raises(FrozenInstanceError):
            output.content = "modified"

    def test_llm_rendered_output_is_dataclass(self) -> None:
        """LLMRenderedOutput must be a dataclass."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.presentation import LLMRenderedOutput

        assert is_dataclass(LLMRenderedOutput)


class TestClassifyContentType:
    """classify_content_type must detect content type from bytes, not file extension."""

    def test_classify_content_type_exists(self) -> None:
        """classify_content_type must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import classify_content_type

        assert classify_content_type is not None

    def test_plain_text_returns_textual(self) -> None:
        """Plain text content must return TEXTUAL."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        content = b"Hello, this is plain text."
        result = classify_content_type(content)
        assert result == ContentType.TEXTUAL

    def test_json_returns_json(self) -> None:
        """JSON content must return JSON."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        content = b'{"key": "value"}'
        result = classify_content_type(content)
        assert result == ContentType.JSON

    def test_empty_content_returns_textual(self) -> None:
        """Empty content must return TEXTUAL."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        result = classify_content_type(b"")
        assert result == ContentType.TEXTUAL

    def test_png_image_returns_image(self) -> None:
        """PNG image content must return IMAGE."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # PNG magic bytes
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.IMAGE

    def test_jpeg_image_returns_image(self) -> None:
        """JPEG image content must return IMAGE."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # JPEG magic bytes
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.IMAGE

    def test_gif_image_returns_image(self) -> None:
        """GIF image content must return IMAGE."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # GIF magic bytes
        content = b"GIF89a" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.IMAGE

    def test_webm_video_returns_video(self) -> None:
        """WebM video content must return VIDEO."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # WebM magic bytes
        content = b"\x1aE\xdf\xa3" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.VIDEO

    def test_mp4_video_returns_video(self) -> None:
        """MP4 video content must return VIDEO."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # MP4 magic bytes (ftyp)
        content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.VIDEO

    def test_mp3_audio_returns_audio(self) -> None:
        """MP3 audio content must return AUDIO."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # MP3 magic bytes
        content = b"ID3" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.AUDIO

    def test_wav_audio_returns_audio(self) -> None:
        """WAV audio content must return AUDIO."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # WAV magic bytes (RIFF....WAVE)
        content = b"RIFF\x00\x00\x00\x00WAVE"
        result = classify_content_type(content)
        assert result == ContentType.AUDIO

    def test_pdf_binary_returns_application(self) -> None:
        """PDF content must return APPLICATION."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # PDF magic bytes
        content = b"%PDF-1.4" + b"\x00" * 100
        result = classify_content_type(content)
        assert result == ContentType.APPLICATION

    def test_unknown_binary_returns_binary(self) -> None:
        """Unknown binary content must return BINARY."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            classify_content_type,
        )

        # Random binary data with null bytes
        content = b"\x00\x01\x02\x03\x04\x05" + b"abc" + b"\xff\xfe\xfd"
        result = classify_content_type(content)
        assert result == ContentType.BINARY

    def test_classify_content_type_is_deterministic(self) -> None:
        """classify_content_type must produce identical results for same input."""
        from hermesoptimizer.tool_surface.presentation import classify_content_type

        content = b'{"key": "value"}'
        result1 = classify_content_type(content)
        result2 = classify_content_type(content)
        assert result1 == result2


class TestBuildFooter:
    """build_footer must create stable footer with status, duration, and truncation metadata."""

    def test_build_footer_exists(self) -> None:
        """build_footer must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import build_footer

        assert build_footer is not None

    def test_footer_shows_success_status(self) -> None:
        """Footer must show success when status is SUCCESS."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.SUCCESS)
        assert "success" in footer.lower()

    def test_footer_shows_failure_status(self) -> None:
        """Footer must show failure when status is FAILURE."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.FAILURE)
        assert "failure" in footer.lower()

    def test_footer_shows_duration_when_present(self) -> None:
        """Footer must show duration when duration_seconds is provided."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.SUCCESS, duration_seconds=1.5)
        assert "1.5" in footer

    def test_footer_shows_truncated_notice(self) -> None:
        """Footer must show truncation notice when was_truncated is True."""
        from hermesoptimizer.tool_surface.presentation import (
            OverflowHandle,
            Status,
            build_footer,
        )

        handle = OverflowHandle(was_truncated=True, overflow_bytes=1000)
        footer = build_footer(status=Status.SUCCESS, overflow_handle=handle)
        assert "truncated" in footer.lower()

    def test_footer_shows_overflow_bytes(self) -> None:
        """Footer must show overflow bytes when present."""
        from hermesoptimizer.tool_surface.presentation import (
            OverflowHandle,
            Status,
            build_footer,
        )

        handle = OverflowHandle(was_truncated=True, overflow_bytes=5000)
        footer = build_footer(status=Status.SUCCESS, overflow_handle=handle)
        assert "5000" in footer

    def test_footer_no_duration_when_none(self) -> None:
        """Footer must not show duration when duration_seconds is None."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.SUCCESS)
        # Duration should not appear as a number
        assert "None" not in footer

    def test_footer_timeout_status(self) -> None:
        """Footer must handle TIMEOUT status."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.TIMEOUT)
        assert "timeout" in footer.lower()

    def test_footer_partial_status(self) -> None:
        """Footer must handle PARTIAL status."""
        from hermesoptimizer.tool_surface.presentation import Status, build_footer

        footer = build_footer(status=Status.PARTIAL)
        assert "partial" in footer.lower()


class TestRenderForLLM:
    """render_for_llm must convert ExecutionResult to LLMRenderedOutput."""

    def test_render_for_llm_exists(self) -> None:
        """render_for_llm must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import render_for_llm

        assert render_for_llm is not None

    def test_render_for_llm_success_case(self) -> None:
        """render_for_llm must handle successful execution."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout="hello", stderr="", exit_code=0)
        rendered = render_for_llm(result)

        assert rendered.content == "hello"
        assert rendered.status.value == "success"
        assert rendered.stderr_excerpt is None

    def test_render_for_llm_failure_case(self) -> None:
        """render_for_llm must capture stderr on failure."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout="", stderr="error: not found", exit_code=1)
        rendered = render_for_llm(result)

        assert rendered.content == ""
        assert rendered.status.value == "failure"
        assert rendered.stderr_excerpt is not None
        assert "not found" in rendered.stderr_excerpt

    def test_render_for_llm_with_duration(self) -> None:
        """render_for_llm must pass through duration."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(
            stdout="output", stderr="", exit_code=0, duration_seconds=2.5
        )
        rendered = render_for_llm(result)

        assert rendered.duration_seconds == 2.5

    def test_render_for_llm_json_content(self) -> None:
        """render_for_llm must detect JSON content."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout='{"key": "value"}', stderr="", exit_code=0)
        rendered = render_for_llm(result)

        assert rendered.content_type == ContentType.JSON

    def test_render_for_llm_binary_content(self) -> None:
        """render_for_llm must detect binary content."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            ExecutionResult,
            render_for_llm,
        )

        # PNG magic bytes
        result = ExecutionResult(
            stdout=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
            stderr="",
            exit_code=0,
        )
        rendered = render_for_llm(result)

        assert rendered.content_type == ContentType.IMAGE

    def test_render_for_llm_with_overflow_threshold(self) -> None:
        """render_for_llm must handle overflow when content exceeds threshold."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        # Content larger than default threshold of 1000 chars
        long_output = "x" * 2000
        result = ExecutionResult(stdout=long_output, stderr="", exit_code=0)
        rendered = render_for_llm(result, overflow_threshold=1000)

        assert rendered.overflow_handle is not None
        assert rendered.overflow_handle.was_truncated is True
        assert rendered.overflow_handle.overflow_bytes == len(long_output) - 1000

    def test_render_for_llm_no_overflow_when_under_threshold(self) -> None:
        """render_for_llm must not set overflow when under threshold."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout="short output", stderr="", exit_code=0)
        rendered = render_for_llm(result, overflow_threshold=1000)

        assert rendered.overflow_handle is None

    def test_render_for_llm_adds_next_step_hints_on_failure(self) -> None:
        """render_for_llm must add next-step hints when execution fails."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout="", stderr="command not found", exit_code=127)
        rendered = render_for_llm(result)

        assert len(rendered.next_step_hints) > 0

    def test_render_for_llm_adds_next_step_hints_on_large_output(self) -> None:
        """render_for_llm must add next-step hints when output is large."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        long_output = "x" * 2000
        result = ExecutionResult(stdout=long_output, stderr="", exit_code=0)
        rendered = render_for_llm(result, overflow_threshold=1000)

        assert len(rendered.next_step_hints) > 0

    def test_render_for_llm_no_hints_on_small_success(self) -> None:
        """render_for_llm must not add hints on small successful output."""
        from hermesoptimizer.tool_surface.presentation import (
            ExecutionResult,
            render_for_llm,
        )

        result = ExecutionResult(stdout="ok", stderr="", exit_code=0)
        rendered = render_for_llm(result)

        assert rendered.next_step_hints == []

    def test_render_for_llm_strips_binary_for_text_fallback(self) -> None:
        """render_for_llm must provide text placeholder for binary content."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            ExecutionResult,
            render_for_llm,
        )

        # Binary content that is not image/video/audio
        result = ExecutionResult(stdout=b"\x00\x01\x02\x03", stderr="", exit_code=0)
        rendered = render_for_llm(result)

        # Should classify as binary
        assert rendered.content_type == ContentType.BINARY
        # Content should indicate binary content
        assert "[binary data]" in rendered.content


class TestSuggestedNextSteps:
    """suggested_next_steps must generate navigation hints based on context."""

    def test_suggested_next_steps_exists(self) -> None:
        """suggested_next_steps must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import suggested_next_steps

        assert suggested_next_steps is not None

    def test_suggested_next_steps_for_not_found_error(self) -> None:
        """suggested_next_steps must suggest help for not-found errors."""
        from hermesoptimizer.tool_surface.presentation import Status, suggested_next_steps

        hints = suggested_next_steps(
            status=Status.FAILURE,
            stderr_excerpt="command not found",
            was_truncated=False,
        )

        assert len(hints) > 0
        hint_texts = [h.hint.lower() for h in hints]
        assert any("help" in h or "usage" in h for h in hint_texts)

    def test_suggested_next_steps_for_timeout(self) -> None:
        """suggested_next_steps must suggest timeout handling."""
        from hermesoptimizer.tool_surface.presentation import Status, suggested_next_steps

        hints = suggested_next_steps(
            status=Status.TIMEOUT,
            stderr_excerpt="",
            was_truncated=False,
        )

        assert len(hints) > 0
        hint_texts = [h.hint.lower() for h in hints]
        assert any("timeout" in h or "increase" in h for h in hint_texts)

    def test_suggested_next_steps_for_truncated_output(self) -> None:
        """suggested_next_steps must suggest handling truncated output."""
        from hermesoptimizer.tool_surface.presentation import Status, suggested_next_steps

        hints = suggested_next_steps(
            status=Status.SUCCESS,
            stderr_excerpt="",
            was_truncated=True,
        )

        assert len(hints) > 0
        hint_texts = [h.hint.lower() for h in hints]
        assert any("truncat" in h or "overflow" in h for h in hint_texts)

    def test_suggested_next_steps_for_large_binary(self) -> None:
        """suggested_next_steps must suggest binary handling for large binary content."""
        from hermesoptimizer.tool_surface.presentation import ContentType, Status, suggested_next_steps

        hints = suggested_next_steps(
            status=Status.SUCCESS,
            stderr_excerpt="",
            was_truncated=True,
            content_type=ContentType.BINARY,
        )

        assert len(hints) > 0
        hint_texts = [h.hint.lower() for h in hints]
        assert any("binary" in h or "file" in h for h in hint_texts)

    def test_suggested_next_steps_returns_list(self) -> None:
        """suggested_next_steps must return a list of NextStepHint."""
        from hermesoptimizer.tool_surface.presentation import NextStepHint, Status, suggested_next_steps

        hints = suggested_next_steps(
            status=Status.FAILURE,
            stderr_excerpt="error",
            was_truncated=False,
        )

        assert isinstance(hints, list)
        for hint in hints:
            assert isinstance(hint, NextStepHint)

    def test_suggested_next_steps_deterministic(self) -> None:
        """suggested_next_steps must be deterministic."""
        from hermesoptimizer.tool_surface.presentation import Status, suggested_next_steps

        hints1 = suggested_next_steps(
            status=Status.FAILURE,
            stderr_excerpt="command not found",
            was_truncated=False,
        )
        hints2 = suggested_next_steps(
            status=Status.FAILURE,
            stderr_excerpt="command not found",
            was_truncated=False,
        )

        assert hints1 == hints2


class TestStderrExcerptLength:
    """STDERR_EXCERPT_LENGTH must be a named module constant for stderr excerpt limits."""

    def test_stderr_excerpt_length_constant_exists(self) -> None:
        """STDERR_EXCERPT_LENGTH must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import STDERR_EXCERPT_LENGTH

        assert STDERR_EXCERPT_LENGTH is not None

    def test_stderr_excerpt_length_equals_500(self) -> None:
        """STDERR_EXCERPT_LENGTH must equal 500."""
        from hermesoptimizer.tool_surface.presentation import STDERR_EXCERPT_LENGTH

        assert STDERR_EXCERPT_LENGTH == 500


class TestPresentationModuleExports:
    """Presentation module must export all public types and functions."""

    def test_all_required_types_exported(self) -> None:
        """All required types must be importable from tool_surface.presentation."""
        from hermesoptimizer.tool_surface.presentation import (
            ContentType,
            ExecutionResult,
            LLMRenderedOutput,
            NextStepHint,
            OverflowHandle,
            Priority,
            STDERR_EXCERPT_LENGTH,
            Status,
            build_footer,
            classify_content_type,
            render_for_llm,
            suggested_next_steps,
        )

        # All should be non-None
        assert ContentType is not None
        assert ExecutionResult is not None
        assert LLMRenderedOutput is not None
        assert NextStepHint is not None
        assert OverflowHandle is not None
        assert Priority is not None
        assert STDERR_EXCERPT_LENGTH is not None
        assert Status is not None
        assert build_footer is not None
        assert classify_content_type is not None
        assert render_for_llm is not None
        assert suggested_next_steps is not None
