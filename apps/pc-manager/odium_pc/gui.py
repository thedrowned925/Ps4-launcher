"""Milestone 0.1 Windows review UI: read-only import + explicit approval.

This UI does not upload packages and does not create PS4-installable catalogs.
Install PySide6 separately (requirements-gui.txt).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSplitter, QStyle, QSystemTrayIcon,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from .ingest import Probe, inspect_pkg
from .store import PackageStore

STYLE = """
QWidget { background: #121316; color: #E8E8EA; font: 10pt 'Segoe UI'; }
QLabel#heading { font-size: 22pt; font-weight: 600; color: #FAFAFA; }
QLabel#subheading { color: #A3A5AB; font-size: 10pt; }
QPushButton { background: #303137; border: 1px solid #45464C;
  border-radius: 9px; padding: 9px 13px; min-height: 18px; }
QPushButton:hover { background: #414248; }
QPushButton#primary { background: #EDEEF0; color: #17181A; border: none;
  font-weight: 600; }
QPushButton#primary:hover { background: #FFFFFF; }
QLineEdit, QComboBox { background: #202125; border: 1px solid #42434A;
  border-radius: 8px; padding: 8px; selection-background-color: #676970; }
QLineEdit:focus, QComboBox:focus { border-color: #B4B5BA; }
QTableWidget { background: #191A1E; alternate-background-color: #202127;
  border: 1px solid #36373B; border-radius: 10px; gridline-color: #2A2C30;
  selection-background-color: #41434A; }
QHeaderView::section { background: #24252A; color: #C8C8CB;
  border: none; padding: 9px; }
QCheckBox { spacing: 8px; }
QSplitter::handle { background: #25262B; width: 1px; }
"""

def database_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or
                (Path.home() / ".local" / "share"))
    directory = root / "Odium" / "PS4-PC-Manager"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "review.sqlite3"


class ScanWorker(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, filenames: list[str]) -> None:
        super().__init__()
        self.filenames = filenames

    def run(self) -> None:
        try:
            for path in self.filenames:
                try:
                    self.result.emit(inspect_pkg(path))
                except (OSError, RuntimeError, ValueError) as exc:
                    self.error.emit(f"{Path(path).name}: {exc}")
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.store = PackageStore(database_path())
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.allow_quit = False
        self.setWindowTitle("Odium PC Manager — Package Review")
        self.resize(1270, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)
        heading = QLabel("ODIUM")
        heading.setObjectName("heading")
        root.addWidget(heading)
        description = QLabel("PC Manager  /  Offline package review — nothing is uploaded")
        description.setObjectName("subheading")
        root.addWidget(description)

        controls = QHBoxLayout()
        self.import_button = QPushButton("Import PKG files")
        self.import_button.setObjectName("primary")
        self.import_button.clicked.connect(self.import_files)
        controls.addWidget(self.import_button)
        export_button = QPushButton("Export draft catalog")
        export_button.clicked.connect(self.export_draft)
        controls.addWidget(export_button)
        controls.addStretch()
        root.addLayout(controls)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["File", "Type guess", "Size (GiB)", "Review state", "Game"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 130)
        self.table.itemSelectionChanged.connect(self.load_selected)
        split.addWidget(self.table)

        side = QWidget()
        details = QVBoxLayout(side)
        details.setContentsMargins(16, 0, 0, 0)
        side_heading = QLabel("Review package")
        side_heading.setObjectName("heading")
        details.addWidget(side_heading)
        self.filename = QLabel("Select a package to review")
        self.filename.setWordWrap(True)
        self.filename.setObjectName("subheading")
        details.addWidget(self.filename)

        form = QFormLayout()
        self.game_id = QLineEdit()
        self.game_id.setPlaceholderText("authorized-demo")
        form.addRow("Game ID", self.game_id)
        self.game_title = QLineEdit()
        form.addRow("Game title", self.game_title)
        self.kind = QComboBox()
        self.kind.addItems(["base", "update", "dlc", "backport"])
        form.addRow("Package type", self.kind)
        self.version = QLineEdit("1.00")
        form.addRow("Package version", self.version)
        self.firmware = QLineEdit()
        self.firmware.setPlaceholderText("Optional, e.g. 9.00")
        form.addRow("Target firmware", self.firmware)
        self.depends = QLineEdit()
        self.depends.setPlaceholderText("sha256:... IDs, comma separated")
        form.addRow("Required package IDs", self.depends)
        details.addLayout(form)
        self.rights = QCheckBox(
            "I confirm I have permission to redistribute this PKG")
        details.addWidget(self.rights)
        approval = QPushButton("Approve reviewed metadata")
        approval.setObjectName("primary")
        approval.clicked.connect(self.approve_selected)
        details.addWidget(approval)
        details.addStretch()
        split.addWidget(side)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 4)
        root.addWidget(split, stretch=1)

        self.status = QLabel("Ready. PKG files are inspected read-only.")
        self.status.setObjectName("subheading")
        root.addWidget(self.status)
        self.setCentralWidget(central)

        self.tray = QSystemTrayIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
            self)
        tray_menu = QMenu()
        show_action = QAction("Open PC Manager", self)
        show_action.triggered.connect(self.open_from_tray)
        tray_menu.addAction(show_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda reason: self.open_from_tray()
          if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.refresh()

    def refresh(self, select_path: str | None = None) -> None:
        self.table.blockSignals(True)
        rows = self.store.rows()
        self.table.setRowCount(len(rows))
        selected = -1
        for i, data in enumerate(rows):
            values = [data["filename"], data["guessed_kind"] + "?",
                      f'{data["size_bytes"] / (1024 ** 3):.3f}',
                      data["state"], data["game_title"] or "Needs review"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, data["path"])
                self.table.setItem(i, column, item)
            if data["path"] == select_path:
                selected = i
        self.table.blockSignals(False)
        if selected >= 0:
            self.table.selectRow(selected)

    def selected_data(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        path = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((r for r in self.store.rows() if r["path"] == path), None)

    def load_selected(self) -> None:
        row = self.selected_data()
        if row is None:
            return
        self.filename.setText(row["filename"] + "\nSHA-256: " + row["sha256"])
        self.game_id.setText(row["game_id"] or "")
        self.game_title.setText(row["game_title"] or "")
        self.kind.setCurrentText(row["kind"] or row["guessed_kind"])
        self.version.setText(row["version"] or "1.00")
        self.firmware.setText(row["target_firmware"] or "")
        self.depends.setText(", ".join(json.loads(row["required_package_ids"])))
        self.rights.setChecked(bool(row["rights_confirmed"]))

    def import_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PS4 PKG files", "", "PS4 Package (*.pkg)")
        if not files:
            return
        self.import_button.setEnabled(False)
        self.status.setText(f"Scanning {len(files)} file(s); UI remains responsive.")
        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(files)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.result.connect(self.on_probe)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.on_scan_finished)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.start()

    def on_probe(self, probe: Probe) -> None:
        self.store.put_probe(probe)
        self.refresh(select_path=probe.path)
        self.status.setText("Scanned: " + probe.filename + " — needs human approval.")

    def on_scan_error(self, message: str) -> None:
        self.status.setText("Scan error: " + message)

    def on_scan_finished(self) -> None:
        self.import_button.setEnabled(True)
        self.scan_thread = None
        self.scan_worker = None

    def approve_selected(self) -> None:
        row = self.selected_data()
        if row is None:
            QMessageBox.information(self, "Review", "Choose a package first.")
            return
        try:
            self.store.approve(
                row["path"], game_id=self.game_id.text().strip(),
                game_title=self.game_title.text().strip(),
                kind=self.kind.currentText(),
                version=self.version.text().strip(),
                target_firmware=self.firmware.text().strip() or None,
                required_package_ids=[
                    part.strip() for part in self.depends.text().split(",") if part.strip()],
                rights_confirmed=self.rights.isChecked())
            self.refresh(select_path=row["path"])
            self.status.setText("Metadata approved locally — NOT uploaded.")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cannot approve", str(exc))

    def export_draft(self) -> None:
        try:
            catalog = self.store.export_draft()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid dependencies", str(exc))
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save offline catalog draft", "catalog-draft.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps(
                catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Cannot save", str(exc))
            return
        self.status.setText("Draft exported — not published or installable.")

    def open_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def exit_app(self) -> None:
        if self.scan_thread is not None:
            QMessageBox.information(
                self, "Scan running", "Let the active file hash finish before exiting.")
            return
        self.allow_quit = True
        self.tray.hide()
        self.store.close()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        if self.allow_quit or not QSystemTrayIcon.isSystemTrayAvailable():
            if self.scan_thread is not None:
                event.ignore()
                self.status.setText("Scan active. Close after hashing completes.")
                return
            self.store.close()
            event.accept()
        else:
            self.hide()
            event.ignore()
            self.tray.showMessage(
                "Odium PC Manager", "Review window hidden. No uploads are active.",
                QSystemTrayIcon.MessageIcon.Information, 2500)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Odium PC Manager")
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
