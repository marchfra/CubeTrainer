"""Inspection beeps: generated WAV files played with Qt multimedia.

The tones are synthesised once with numpy and written as WAV files to a cache
directory, so the app ships no audio assets.
"""

import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QMessageLogContext, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtMultimedia import QSoundEffect

from cubetrainer.inspection import WARNINGS_MS

SAMPLE_RATE: int = 44_100
BEEP_HZ: float = 1_046.5  # C6: clear without being shrill
BEEP_SECONDS: float = 0.12
GAP_SECONDS: float = 0.08

#: Number of beeps for each warning: one at 8 s, two at 12 s.
BEEPS_PER_WARNING: dict[int, int] = dict(zip(WARNINGS_MS, (1, 2), strict=True))

#: Where the generated WAV files are kept.
SOUNDS_DIR: Path = Path(tempfile.gettempdir()) / "cubetrainer-sounds"

#: Start of a Qt warning printed for every channel of some multi-channel audio
#: devices; harmless, and dozens of lines long.
_NOISY_MESSAGE: str = "audio device has unrecognized channel"


def beep_samples(beeps: int) -> np.ndarray:
    """Synthesise ``beeps`` short tones separated by short gaps.

    Args:
        beeps: Number of tones (1 or more).

    Returns:
        16-bit mono samples.

    """
    t = np.arange(int(SAMPLE_RATE * BEEP_SECONDS)) / SAMPLE_RATE
    # A quick fade in and out avoids clicks at the edges.
    envelope = np.minimum(1.0, np.minimum(t, BEEP_SECONDS - t) / 0.01)
    tone = 0.5 * np.sin(2 * np.pi * BEEP_HZ * t) * envelope
    gap = np.zeros(int(SAMPLE_RATE * GAP_SECONDS))
    parts: list[np.ndarray] = []
    for index in range(beeps):
        if index:
            parts.append(gap)
        parts.append(tone)
    return (np.concatenate(parts) * 32_767).astype(np.int16)


def write_wav(path: Path, samples: np.ndarray) -> Path:
    """Write 16-bit mono samples to a WAV file.

    Args:
        path: The file to write.
        samples: The samples.

    Returns:
        The path.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())
    return path


def warning_sound(warning_ms: int, directory: Path = SOUNDS_DIR) -> Path:
    """Return the WAV file for a warning, generating it if needed.

    Args:
        warning_ms: The warning (8000 or 12000).
        directory: Where the files are kept.

    Returns:
        The WAV file.

    """
    beeps = BEEPS_PER_WARNING[warning_ms]
    path = directory / f"beep{beeps}.wav"
    if not path.exists():
        write_wav(path, beep_samples(beeps))
    return path


def _drop_noisy_messages(
    message_type: QtMsgType,
    context: QMessageLogContext,
    message: str,
) -> None:
    """Print Qt messages to stderr, except the known noisy audio-device warning.

    Args:
        message_type: The message's severity (unused: everything kept is printed).
        context: Where the message comes from (unused).
        message: The text.

    """
    del message_type, context
    if not message.startswith(_NOISY_MESSAGE):
        print(message, file=sys.stderr)  # what Qt itself would do


def quiet_audio_warnings() -> None:
    """Hide the harmless per-channel warnings some audio devices cause."""
    qInstallMessageHandler(_drop_noisy_messages)


class InspectionAudio:
    """Plays the 8 s and 12 s inspection warnings.

    Sound effects are created on first use, so nothing touches the audio device
    until a warning is actually played.
    """

    def __init__(self, directory: Path = SOUNDS_DIR) -> None:
        """Prepare (lazily) the warning sounds.

        Args:
            directory: Where the WAV files are kept.

        """
        self._directory: Path = directory
        self._effects: dict[int, QSoundEffect] = {}

    def play(self, warning_ms: int) -> None:
        """Play the sound of a warning.

        Args:
            warning_ms: The warning (8000 or 12000).

        """
        effect = self._effects.get(warning_ms)
        if effect is None:
            effect = QSoundEffect()
            effect.setSource(
                QUrl.fromLocalFile(str(warning_sound(warning_ms, self._directory))),
            )
            self._effects[warning_ms] = effect
        effect.play()
