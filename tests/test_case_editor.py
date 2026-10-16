"""Tests for customising cases: algorithm checks, storage, images and the editor."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QTransform
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import (
    CaseCustomization,
    CaseStatus,
    customize,
    load_case_set,
)
from cubetrainer.cases.editing import alg_problem
from cubetrainer.db import Database
from cubetrainer.ui.case_editor import VALID_TEXT, CaseEditor
from cubetrainer.ui.case_images import RENDER_SCALE, case_pixmap

PLL = load_case_set("pll")
T_CASE = next(c for c in PLL.cases if c.id == "T")
SUNE = next(c for c in load_case_set("oll").cases if c.id == "27")


@pytest.mark.parametrize(
    "alg",
    [
        T_CASE.alg,
        "R U R' U' R' F R2 U' R' U' R U R' F'",  # without brackets
        "U R U R' U' R' F R2 U' R' U' R U R' F' U2",  # extra U turns
        "y R U R' U' R' F R2 U' R' U' R U R' F' y'",  # from another side
    ],
)
def test_algs_solving_the_case_are_accepted(alg: str) -> None:
    """Any algorithm for the same case is fine, whatever the U turns or rotations."""
    assert alg_problem(T_CASE, alg) is None


@pytest.mark.parametrize(
    ("alg", "problem"),
    [
        ("", "Enter an algorithm"),
        ("R Q", "Not valid notation"),
        ("R U R'", "Doesn't solve T"),
        ("M2 U M U2 M' U M2", "Doesn't solve T"),  # a different PLL
    ],
)
def test_wrong_algs_are_explained(alg: str, problem: str) -> None:
    """Empty, invalid or wrong algorithms are rejected with a reason."""
    message = alg_problem(T_CASE, alg)

    assert message is not None
    assert message.startswith(problem)


def test_oll_alg_check_ignores_permutation() -> None:
    """An OLL algorithm may leave any PLL: Sune with a different finish is fine."""
    assert (
        alg_problem(SUNE, "R U R' U R U2 R' U R U R' U' R' F R2 U' R' U' R U R' F'")
        is None
    )


def test_customize_replaces_alg_image_and_rotation() -> None:
    """Customised cases carry the user's choices; the others are untouched."""
    custom = CaseCustomization(alg="R U R' U' R' F R2 U' R' U' R U R' F'", rotation=5)

    customized = customize(PLL, {"T": custom})

    t = next(c for c in customized.cases if c.id == "T")
    assert (t.alg, t.rotation, t.image_path) == (custom.alg, 1, None)
    assert customized.cases[0] == PLL.cases[0]
    assert CaseCustomization().apply_to(T_CASE).alg == T_CASE.alg


def test_customizations_are_stored_without_touching_status(tmp_path: Path) -> None:
    """Customisations survive a reopen and keep the case's learning status."""
    db = Database(tmp_path / "app.db")
    db.set_case_status("pll", "T", CaseStatus.LEARNING)
    custom = CaseCustomization(alg="x", image_path="/a.png", rotation=2)
    db.save_case_customization("pll", "T", custom)
    db.save_case_customization("pll", "Ua", CaseCustomization(rotation=1))
    db.close()

    reopened = Database(tmp_path / "app.db")
    assert reopened.load_case_customizations("pll") == {
        "T": custom,
        "Ua": CaseCustomization(rotation=1),
    }
    assert reopened.load_case_statuses("pll")["T"] is CaseStatus.LEARNING
    assert reopened.load_case_statuses("pll")["Ua"] is CaseStatus.UNLEARNED

    reopened.save_case_customization("pll", "T", CaseCustomization())
    assert "T" not in reopened.load_case_customizations("pll")
    assert reopened.images_dir == tmp_path / "images"
    reopened.close()


def solid_png(path: Path, colour: str) -> Path:
    """Write a small single-colour PNG.

    Args:
        path: Where to write it.
        colour: Its colour, e.g. ``"#ff0000"``.

    Returns:
        The path.

    """
    image = QImage(40, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor(colour))
    assert image.save(str(path))
    return path


def test_uploaded_image_replaces_the_generated_one(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """A case with an image file shows that file, fitted in the square."""
    del qtbot  # only needed for the Qt application
    path = solid_png(tmp_path / "red.png", "#ff0000")
    case = CaseCustomization(image_path=str(path)).apply_to(T_CASE)

    image = case_pixmap(case, 50).toImage()

    assert image.pixelColor(50, 50).name() == "#ff0000"  # centre (100 px at scale 2)
    assert image.pixelColor(50, 2).alpha() == 0  # letterboxed: 40x20 in a square


def test_unreadable_image_falls_back_to_generated(qtbot: QtBot, tmp_path: Path) -> None:
    """A missing or broken file shows the generated image instead."""
    del qtbot
    case = CaseCustomization(image_path=str(tmp_path / "missing.png")).apply_to(T_CASE)

    assert case_pixmap(case, 50).toImage() == case_pixmap(T_CASE, 50).toImage()


def test_rotation_turns_the_image(qtbot: QtBot) -> None:
    """A rotated case shows its image turned by quarter turns."""
    del qtbot
    rotated = CaseCustomization(rotation=1).apply_to(T_CASE)
    expected = case_pixmap(T_CASE, 50).toImage().transformed(QTransform().rotate(90))

    assert case_pixmap(rotated, 50).toImage() == expected
    assert case_pixmap(rotated, 50).devicePixelRatio() == RENDER_SCALE


def make_editor(
    qtbot: QtBot,
    tmp_path: Path,
    customization: CaseCustomization | None = None,
) -> CaseEditor:
    """Create and show an editor for the T perm.

    Args:
        qtbot: pytest-qt helper.
        tmp_path: Directory for uploaded images.
        customization: What the user changed so far.

    Returns:
        The editor.

    """
    editor = CaseEditor(
        T_CASE,
        customization or CaseCustomization(),
        tmp_path / "images",
    )
    qtbot.addWidget(editor)
    editor.show()
    return editor


def test_editor_checks_the_alg_as_you_type(qtbot: QtBot, tmp_path: Path) -> None:
    """OK is only enabled while the algorithm solves the case."""
    editor = make_editor(qtbot, tmp_path)
    assert editor.alg_status.text() == VALID_TEXT
    assert editor.ok_button.isEnabled()

    editor.alg_edit.setText("R U R'")
    assert editor.alg_status.text() == "✗ Doesn't solve T"
    assert not editor.ok_button.isEnabled()

    editor.alg_edit.setText("y R U R' U' R' F R2 U' R' U' R U R' F'")
    assert editor.ok_button.isEnabled()
    assert editor.customization().alg == "y R U R' U' R' F R2 U' R' U' R U R' F'"


def test_default_alg_is_stored_as_none(qtbot: QtBot, tmp_path: Path) -> None:
    """Going back to the default algorithm clears the custom one."""
    own = CaseCustomization(alg="U R U R' U' R' F R2 U' R' U' R U R' F'")
    editor = make_editor(qtbot, tmp_path, own)

    buttons = {b.text(): b for b in editor.findChildren(type(editor.ok_button))}
    qtbot.mouseClick(buttons["Default"], Qt.MouseButton.LeftButton)

    assert editor.alg_edit.text() == T_CASE.alg
    assert editor.customization().alg is None


def test_rotation_wraps_around(qtbot: QtBot, tmp_path: Path) -> None:
    """Rotating changes the preview and wraps at four quarter turns."""
    editor = make_editor(qtbot, tmp_path)
    before = editor.preview.pixmap().toImage()

    editor.rotate(1)
    assert editor.customization().rotation == 1
    assert editor.preview.pixmap().toImage() != before
    editor.rotate(-2)
    assert editor.customization().rotation == 3


def test_upload_copies_the_file_and_clear_removes_it(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """Uploading copies the image into the images folder; clearing forgets it."""
    source = solid_png(tmp_path / "mine.PNG", "#00ff00")
    editor = make_editor(qtbot, tmp_path)
    editor.choose_file = lambda: str(source)

    editor.upload_image()

    stored = editor.customization().image_path
    assert stored is not None
    assert Path(stored).parent == tmp_path / "images"
    assert Path(stored).suffix == ".png"
    assert Path(stored).read_bytes() == source.read_bytes()

    editor.clear_image()
    assert editor.customization().image_path is None


def test_cancelled_upload_changes_nothing(qtbot: QtBot, tmp_path: Path) -> None:
    """Cancelling the file picker keeps the current image."""
    editor = make_editor(qtbot, tmp_path)
    editor.choose_file = lambda: None

    editor.upload_image()

    assert editor.customization().image_path is None
