"""Tests for the generated inspection beeps (no audio is played)."""

import wave
from pathlib import Path

import pytest
from PySide6.QtCore import QMessageLogContext, QtMsgType

from cubetrainer import sound


@pytest.mark.parametrize("beeps", [1, 2])
def test_beeps_have_the_right_length(beeps: int) -> None:
    """Each beep is 0.12 s, with 0.08 s gaps between them."""
    samples = sound.beep_samples(beeps)

    seconds = beeps * sound.BEEP_SECONDS + (beeps - 1) * sound.GAP_SECONDS
    assert len(samples) == pytest.approx(seconds * sound.SAMPLE_RATE, abs=2)
    assert samples.dtype.name == "int16"
    assert 0 < abs(samples).max() <= 32_767


def test_warning_sounds_are_valid_wavs(tmp_path: Path) -> None:
    """One beep at 8 s, two at 12 s, written as 16-bit mono WAV files."""
    one = sound.warning_sound(8_000, tmp_path)
    two = sound.warning_sound(12_000, tmp_path)

    for path, beeps in ((one, 1), (two, 2)):
        with wave.open(str(path)) as wav:
            assert (wav.getnchannels(), wav.getsampwidth()) == (1, 2)
            assert wav.getframerate() == sound.SAMPLE_RATE
            assert wav.getnframes() == len(sound.beep_samples(beeps))


def test_existing_sound_is_reused(tmp_path: Path) -> None:
    """A sound file is generated once and then reused."""
    path = sound.warning_sound(8_000, tmp_path)
    path.write_bytes(b"marker")

    assert sound.warning_sound(8_000, tmp_path).read_bytes() == b"marker"


def test_noisy_audio_warning_is_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    """The per-channel device warning is hidden; other messages still show."""
    context = QMessageLogContext()
    sound._drop_noisy_messages(
        QtMsgType.QtWarningMsg,
        context,
        "audio device has unrecognized channel, index: 18 label: 19",
    )
    sound._drop_noisy_messages(QtMsgType.QtWarningMsg, context, "something else")

    assert capsys.readouterr().err == "something else\n"
