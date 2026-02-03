"""Audio processing utilities for OpenAI Realtime API compatibility.

The OpenAI Realtime API requires audio in a specific format:
- Raw PCM16 (16-bit signed integer samples, little-endian)
- Mono channel
- 24kHz sample rate
- Base64 encoded

This module provides utilities to convert WAV files to this format.
"""

import io
import logging
import struct
import wave

logger = logging.getLogger(__name__)

# OpenAI Realtime API expected format
TARGET_SAMPLE_RATE = 24000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit = 2 bytes


class AudioFormatError(Exception):
    """Exception raised when audio format conversion fails."""

    pass


def convert_wav_to_pcm16_24khz(wav_data: bytes) -> bytes:
    """Convert WAV audio data to raw PCM16 mono at 24kHz (little-endian).

    This function:
    1. Parses WAV header to extract format info
    2. Extracts raw PCM data (strips WAV header)
    3. Converts stereo to mono if needed
    4. Resamples to 24kHz if needed
    5. Ensures 16-bit sample width

    Args:
        wav_data: Raw bytes of a WAV file

    Returns:
        Raw PCM16 audio bytes (mono, 24kHz, little-endian)

    Raises:
        AudioFormatError: If the WAV file cannot be processed
    """
    try:
        with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()

            logger.info(
                "Processing WAV file for Realtime API",
                extra={
                    "channels": n_channels,
                    "sample_width_bytes": sample_width,
                    "frame_rate": frame_rate,
                    "n_frames": n_frames,
                    "duration_seconds": n_frames / frame_rate if frame_rate > 0 else 0,
                },
            )

            # Read all frames
            raw_data = wav_file.readframes(n_frames)

    except wave.Error as e:
        raise AudioFormatError(f"Invalid WAV file: {e}") from e
    except Exception as e:
        raise AudioFormatError(f"Failed to read audio file: {e}") from e

    # Convert to 16-bit if needed
    if sample_width == 1:
        # 8-bit unsigned to 16-bit signed
        raw_data = _convert_8bit_to_16bit(raw_data)
        sample_width = 2
        logger.info("Converted 8-bit to 16-bit audio", extra={})
    elif sample_width == 4:
        # 32-bit to 16-bit (truncate precision)
        raw_data = _convert_32bit_to_16bit(raw_data, n_channels)
        sample_width = 2
        logger.info("Converted 32-bit to 16-bit audio", extra={})
    elif sample_width != 2:
        raise AudioFormatError(f"Unsupported sample width: {sample_width} bytes")

    # Convert stereo to mono if needed
    if n_channels == 2:
        raw_data = _convert_stereo_to_mono(raw_data)
        n_channels = 1
        logger.info("Converted stereo to mono", extra={})
    elif n_channels != 1:
        raise AudioFormatError(f"Unsupported channel count: {n_channels}")

    # Resample to 24kHz if needed
    if frame_rate != TARGET_SAMPLE_RATE:
        logger.info(
            "Resampling audio",
            extra={
                "source_rate": frame_rate,
                "target_rate": TARGET_SAMPLE_RATE,
            },
        )
        raw_data = _resample_linear(raw_data, frame_rate, TARGET_SAMPLE_RATE)

    logger.info(
        "Audio conversion complete",
        extra={
            "output_bytes": len(raw_data),
            "output_samples": len(raw_data) // 2,
            "output_duration_seconds": round(len(raw_data) / 2 / TARGET_SAMPLE_RATE, 2),
        },
    )

    return raw_data


def _convert_8bit_to_16bit(data: bytes) -> bytes:
    """Convert 8-bit unsigned PCM to 16-bit signed PCM (little-endian)."""
    samples_8bit = struct.unpack(f"{len(data)}B", data)
    # 8-bit is unsigned (0-255), convert to signed 16-bit (-32768 to 32767)
    samples_16bit = [(s - 128) * 256 for s in samples_8bit]
    # Use little-endian format (<)
    return struct.pack(f"<{len(samples_16bit)}h", *samples_16bit)


def _convert_32bit_to_16bit(data: bytes, _n_channels: int) -> bytes:
    """Convert 32-bit signed PCM to 16-bit signed PCM (little-endian)."""
    n_samples = len(data) // 4
    # WAV files are little-endian
    samples_32bit = struct.unpack(f"<{n_samples}i", data)
    # Scale down from 32-bit to 16-bit range
    samples_16bit = [s >> 16 for s in samples_32bit]
    return struct.pack(f"<{n_samples}h", *samples_16bit)


def _convert_stereo_to_mono(data: bytes) -> bytes:
    """Convert stereo PCM16 to mono by averaging channels (little-endian)."""
    n_samples = len(data) // 4  # 2 bytes per sample, 2 channels
    # WAV files are little-endian
    stereo_samples = struct.unpack(f"<{n_samples * 2}h", data)

    # Average left and right channels
    mono_samples = []
    for i in range(0, len(stereo_samples), 2):
        left = stereo_samples[i]
        right = stereo_samples[i + 1]
        mono_samples.append((left + right) // 2)

    return struct.pack(f"<{len(mono_samples)}h", *mono_samples)


def _resample_linear(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample audio using linear interpolation (little-endian).

    This is a simple resampling method that works for basic audio processing.
    For production use with high quality requirements, consider using a
    proper audio library like scipy or librosa.

    Args:
        data: Raw PCM16 audio bytes (little-endian)
        src_rate: Source sample rate in Hz
        dst_rate: Destination sample rate in Hz

    Returns:
        Resampled PCM16 audio bytes (little-endian)
    """
    if src_rate == dst_rate:
        return data

    n_samples = len(data) // 2
    # Use little-endian format
    samples = struct.unpack(f"<{n_samples}h", data)

    # Calculate output length
    ratio = dst_rate / src_rate
    out_length = int(n_samples * ratio)

    if out_length == 0:
        return b""

    # Linear interpolation resampling
    resampled = []
    for i in range(out_length):
        # Find position in source
        src_pos = i / ratio
        src_idx = int(src_pos)
        frac = src_pos - src_idx

        if src_idx >= n_samples - 1:
            # At or past the end, use last sample
            resampled.append(samples[-1])
        else:
            # Linear interpolation between two samples
            s1 = samples[src_idx]
            s2 = samples[src_idx + 1]
            interpolated = int(s1 + frac * (s2 - s1))
            # Clamp to 16-bit range
            interpolated = max(-32768, min(32767, interpolated))
            resampled.append(interpolated)

    return struct.pack(f"<{len(resampled)}h", *resampled)


def detect_audio_format(data: bytes) -> str:
    """Detect the audio format from file magic bytes.

    Args:
        data: Raw bytes to check

    Returns:
        Format string: "wav", "webm", "ogg", "mp3", "flac", or "unknown"
    """
    result = "unknown"
    if len(data) >= 12:
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            result = "wav"
        elif data[:4] == b"\x1a\x45\xdf\xa3":
            result = "webm"
        elif data[:4] == b"OggS":
            result = "ogg"
        elif data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            result = "mp3"
        elif data[:4] == b"fLaC":
            result = "flac"
    return result


def is_wav_file(data: bytes) -> bool:
    """Check if the data appears to be a WAV file.

    Args:
        data: Raw bytes to check

    Returns:
        True if the data starts with WAV file magic bytes
    """
    audio_format = detect_audio_format(data)

    if audio_format == "wav":
        logger.info(
            "Detected WAV file",
            extra={
                "file_size": len(data),
                "header_preview": data[:12].hex(),
            },
        )
        return True

    # Provide helpful error for known unsupported formats
    if audio_format in ("webm", "ogg", "mp3", "flac"):
        logger.error(
            "Unsupported audio format detected",
            extra={
                "detected_format": audio_format,
                "file_size": len(data),
                "header_preview": data[:12].hex(),
                "hint": "Please convert to WAV format (mono, 16-bit PCM, preferably 24kHz)",
            },
        )
    else:
        logger.warning(
            "Unknown audio format",
            extra={
                "file_size": len(data),
                "header_preview": data[:12].hex() if len(data) >= 12 else data.hex(),
            },
        )

    return False
