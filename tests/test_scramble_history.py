"""Tests for the scramble history behind the ◀ / ▶ buttons."""

from itertools import count

from cubetrainer.scramble_history import ScrambleHistory


def make_history() -> ScrambleHistory:
    """Create a history whose generator yields "s0", "s1", ...

    Returns:
        The history, showing "s0".

    """
    counter = count()
    return ScrambleHistory(lambda: f"s{next(counter)}")


def test_starts_with_one_scramble() -> None:
    """The first scramble is generated immediately and can't go back."""
    history = make_history()

    assert history.current == "s0"
    assert not history.can_go_back


def test_next_generates_at_end_and_reuses_in_middle() -> None:
    """Next creates scrambles only at the end; otherwise it walks forward."""
    history = make_history()
    history.next()
    history.next()
    assert history.current == "s2"

    history.previous()
    history.previous()
    assert history.current == "s0"

    assert history.next() == "s1"
    assert history.next() == "s2"
    assert history.next() == "s3"
    assert history.scrambles == ["s0", "s1", "s2", "s3"]


def test_previous_stops_at_first() -> None:
    """Going back from the first scramble stays on it."""
    history = make_history()

    assert history.previous() == "s0"
    assert history.index == 0


def test_new_jumps_to_fresh_scramble_at_end() -> None:
    """After a solve, a new scramble is appended even when browsing backwards."""
    history = make_history()
    history.next()
    history.previous()

    assert history.new() == "s2"
    assert history.index == 2
    assert history.can_go_back
