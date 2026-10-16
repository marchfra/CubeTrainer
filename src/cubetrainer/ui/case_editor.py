"""Dialog for changing a case's algorithm and image."""

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cases.catalog import Case, CaseCustomization
from cubetrainer.cases.editing import alg_problem
from cubetrainer.ui.case_images import case_pixmap

if TYPE_CHECKING:
    from collections.abc import Callable

#: Size of the preview image, in logical pixels.
PREVIEW_SIZE: int = 200

#: File types offered when uploading an image.
IMAGE_FILTER: str = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg)"

#: Shown under the algorithm while it's valid.
VALID_TEXT: str = "✓ Solves this case"


def choose_image_file(parent: QWidget) -> str | None:
    """Ask the user for an image file.

    Args:
        parent: Parent of the file dialog.

    Returns:
        The chosen file, or None if the user cancelled.

    """
    path, _ = QFileDialog.getOpenFileName(parent, "Choose an image", "", IMAGE_FILTER)
    return path or None


class CaseEditor(QDialog):
    """Edits a case's algorithm, image and image rotation, with a live preview.

    Attributes:
        preview: Shows the image as it will appear.
        alg_edit: The algorithm.
        alg_status: Says whether the algorithm solves the case.
        ok_button: Accepts the changes (disabled while the algorithm is invalid).
        choose_file: Asks for an image file; replaceable in tests.

    """

    def __init__(
        self,
        case: Case,
        customization: CaseCustomization,
        images_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        """Create the editor.

        Args:
            case: The bundled case (its algorithm is the default and the reference).
            customization: What the user has changed so far.
            images_dir: Where uploaded images are copied to.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle(f"Edit {case.name}")
        self._case: Case = case
        self._images_dir: Path = images_dir
        self._image_path: str | None = customization.image_path
        self._rotation: int = customization.rotation % 4
        self._valid_alg: str = customization.alg or case.alg
        self.choose_file: Callable[[], str | None] = lambda: choose_image_file(self)

        self.preview: QLabel = QLabel()
        self.preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        image_buttons = QHBoxLayout()
        for text, tooltip, handler in (
            ("↺ Rotate", "Rotate the image anticlockwise", lambda: self.rotate(-1)),
            ("↻ Rotate", "Rotate the image clockwise", lambda: self.rotate(1)),
            ("Upload image…", "Show your own image instead", self.upload_image),
            (
                "Use generated image",
                "Draw the image from the algorithm",
                self.clear_image,
            ),
        ):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.clicked.connect(handler)
            image_buttons.addWidget(button)

        self.alg_edit: QLineEdit = QLineEdit(customization.alg or case.alg)
        self.alg_edit.textChanged.connect(self._on_alg_changed)
        default_button = QPushButton("Default")
        default_button.setToolTip(f"Use the default algorithm: {case.alg}")
        default_button.clicked.connect(lambda: self.alg_edit.setText(case.alg))
        alg_row = QHBoxLayout()
        alg_row.addWidget(self.alg_edit, stretch=1)
        alg_row.addWidget(default_button)
        self.alg_status: QLabel = QLabel()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None  # noqa: S101 - requested just above
        self.ok_button: QPushButton = ok_button
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(image_buttons)
        layout.addWidget(QLabel("Algorithm (brackets group it into blocks):"))
        layout.addLayout(alg_row)
        layout.addWidget(self.alg_status)
        layout.addWidget(buttons)
        self._on_alg_changed(self.alg_edit.text())

    def customization(self) -> CaseCustomization:
        """Return the changes described by the dialog.

        Returns:
            The customisation; ``alg`` is None when it's the default algorithm.

        """
        alg = self.alg_edit.text().strip()
        return CaseCustomization(
            alg=None if alg == self._case.alg else alg,
            image_path=self._image_path,
            rotation=self._rotation,
        )

    def rotate(self, quarter_turns: int) -> None:
        """Rotate the image.

        Args:
            quarter_turns: Clockwise quarter turns (negative for anticlockwise).

        """
        self._rotation = (self._rotation + quarter_turns) % 4
        self._update_preview()

    def upload_image(self) -> None:
        """Ask for an image file and use a copy of it as the case image."""
        source = self.choose_file()
        if source is None:
            return
        self._images_dir.mkdir(parents=True, exist_ok=True)
        # A fresh name for every upload: the old file may still be shown elsewhere.
        target = self._images_dir / f"{uuid.uuid4().hex}{Path(source).suffix.lower()}"
        shutil.copyfile(source, target)
        self._image_path = str(target)
        self._update_preview()

    def clear_image(self) -> None:
        """Go back to the image generated from the algorithm."""
        self._image_path = None
        self._update_preview()

    def _on_alg_changed(self, text: str) -> None:
        """Check the algorithm, and redraw the preview when it's valid.

        Args:
            text: The algorithm as typed.

        """
        problem = alg_problem(self._case, text)
        self.alg_status.setText(f"✗ {problem}" if problem else VALID_TEXT)
        self.ok_button.setEnabled(problem is None)
        if problem is None:
            self._valid_alg = text.strip()
        self._update_preview()

    def _update_preview(self) -> None:
        """Show the image as it will appear, with the last valid algorithm."""
        shown = CaseCustomization(
            alg=self._valid_alg,
            image_path=self._image_path,
            rotation=self._rotation,
        ).apply_to(self._case)
        self.preview.setPixmap(case_pixmap(shown, PREVIEW_SIZE))
