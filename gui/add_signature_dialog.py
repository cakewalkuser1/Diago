"""
Add Signature Dialog
Allows users to record or import a known fault sound,
give it a name/description/category, optionally associate
trouble codes, and save the fingerprinted signature to the database.
"""

import os
import re

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QComboBox, QFileDialog, QMessageBox, QGroupBox,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from core.audio_io import (
    AudioRecorder, load_audio_file, save_audio, STANDARD_SR,
)
from core.fingerprint import generate_fingerprint, compute_fingerprint_stats
from database.db_manager import DatabaseManager


# Valid categories for the database
CATEGORIES = [
    ("engine", "Engine"),
    ("exhaust", "Exhaust"),
    ("intake", "Intake / Vacuum"),
    ("belt", "Belt / Serpentine"),
    ("bearing", "Bearing"),
    ("accessory", "Accessory / Pulley"),
    ("drivetrain", "Drivetrain"),
    ("transmission", "Transmission"),
    ("suspension", "Suspension"),
    ("brakes", "Brakes"),
    ("electrical", "Electrical"),
    ("hvac", "HVAC / AC"),
    ("cooling", "Cooling System"),
    ("fuel", "Fuel System"),
    ("other", "Other"),
]

# OBD-II: P/B/C/U + 4 hex digits (e.g. P0300, P219A)
DTC_PATTERN = re.compile(r"^[PBCU][0-9A-Fa-f]{4}$", re.IGNORECASE)


class FingerprintThread(QThread):
    """Background thread for fingerprinting audio."""
    finished = pyqtSignal(list)  # list of Fingerprint objects
    error = pyqtSignal(str)

    def __init__(self, audio_data: np.ndarray, sr: int, parent=None):
        super().__init__(parent)
        self.audio_data = audio_data
        self.sr = sr

    def run(self):
        try:
            fps = generate_fingerprint(self.audio_data, self.sr)
            self.finished.emit(fps)
        except Exception as e:
            self.error.emit(str(e))


class AddSignatureDialog(QDialog):
    """
    Dialog for adding a new fault signature to the database.
    Users can record or import audio, name the fault, choose a category,
    optionally add trouble codes, and save.
    """

    signature_added = pyqtSignal(int)  # emits the new signature ID

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._recorder = AudioRecorder(sample_rate=STANDARD_SR)
        self._audio_data: np.ndarray | None = None
        self._audio_sr: int = STANDARD_SR
        self._fingerprints = None
        self._fp_thread = None
        self._recording = False

        self.setWindowTitle("Add Fault Signature")
        self.setMinimumSize(550, 600)
        self.resize(600, 650)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- Audio Source ----
        audio_group = QGroupBox("1. Audio Source")
        audio_layout = QVBoxLayout(audio_group)

        btn_row = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setMinimumWidth(90)
        btn_row.addWidget(self.record_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(70)
        btn_row.addWidget(self.stop_btn)

        self.import_btn = QPushButton("Import File")
        self.import_btn.setMinimumWidth(100)
        btn_row.addWidget(self.import_btn)

        sep = QLabel("|")
        sep.setStyleSheet("color: #45475a; font-size: 16px;")
        btn_row.addWidget(sep)

        btn_row.addWidget(QLabel("Duration:"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["Manual", "3s", "5s", "10s", "15s", "30s"])
        self.duration_combo.setCurrentIndex(2)
        self.duration_combo.setMinimumWidth(70)
        btn_row.addWidget(self.duration_combo)

        btn_row.addStretch()
        audio_layout.addLayout(btn_row)

        self.audio_status = QLabel("No audio loaded")
        self.audio_status.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding: 4px;"
        )
        audio_layout.addWidget(self.audio_status)

        layout.addWidget(audio_group)

        # ---- Signature Details ----
        details_group = QGroupBox("2. Signature Details")
        form = QFormLayout(details_group)
        form.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "e.g., Idler Pulley Bearing - Lexus GS470"
        )
        self.name_input.setMinimumWidth(350)
        form.addRow("Name:", self.name_input)

        self.category_combo = QComboBox()
        for value, display in CATEGORIES:
            self.category_combo.addItem(display, value)
        form.addRow("Category:", self.category_combo)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Describe the sound: what it sounds like, when it occurs, "
            "what component produces it, RPM/speed conditions, etc."
        )
        self.description_input.setMaximumHeight(100)
        form.addRow("Description:", self.description_input)

        # Trouble codes (optional)
        codes_row = QHBoxLayout()
        self.codes_input = QLineEdit()
        self.codes_input.setPlaceholderText(
            "Optional: P0301, P0420  (comma-separated, or leave blank)"
        )
        codes_row.addWidget(self.codes_input)

        codes_hint = QLabel("(optional)")
        codes_hint.setStyleSheet("color: #585b70; font-size: 11px;")
        codes_row.addWidget(codes_hint)

        form.addRow("Trouble Codes:", codes_row)

        # Vehicle specificity (optional free-text, stored in description)
        self.vehicle_input = QLineEdit()
        self.vehicle_input.setPlaceholderText(
            "Optional: e.g., Lexus GS470, 2006 Honda Civic, Any"
        )
        form.addRow("Vehicle:", self.vehicle_input)

        layout.addWidget(details_group)

        # ---- Fingerprint Preview ----
        fp_group = QGroupBox("3. Fingerprint")
        fp_layout = QVBoxLayout(fp_group)

        self.fp_status = QLabel("Load audio to generate fingerprint")
        self.fp_status.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding: 4px;"
        )
        fp_layout.addWidget(self.fp_status)

        self.fp_btn = QPushButton("Generate Fingerprint")
        self.fp_btn.setEnabled(False)
        fp_layout.addWidget(self.fp_btn)

        layout.addWidget(fp_group)

        # ---- Action Buttons ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("Save Signature")
        self.save_btn.setObjectName("analyzeBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumWidth(150)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumWidth(80)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.record_btn.clicked.connect(self._start_recording)
        self.stop_btn.clicked.connect(self._stop_recording)
        self.import_btn.clicked.connect(self._import_file)
        self.fp_btn.clicked.connect(self._generate_fingerprint)
        self.save_btn.clicked.connect(self._save_signature)
        self.cancel_btn.clicked.connect(self.reject)
        self.codes_input.textChanged.connect(self._auto_uppercase_codes)

    def _auto_uppercase_codes(self, text):
        upper = text.upper()
        if upper != text:
            self.codes_input.blockSignals(True)
            self.codes_input.setText(upper)
            self.codes_input.blockSignals(False)

    # ---- Recording ----

    def _start_recording(self):
        self._recording = True
        self.record_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.import_btn.setEnabled(False)
        self.audio_status.setText("Recording...")
        self.audio_status.setStyleSheet(
            "color: #a6e3a1; font-style: italic; padding: 4px;"
        )

        self._recorder.start_recording()

        duration_text = self.duration_combo.currentText()
        if duration_text != "Manual":
            duration_ms = int(duration_text.replace("s", "")) * 1000
            QTimer.singleShot(duration_ms, self._stop_recording)

    def _stop_recording(self):
        if not self._recording:
            return
        self._recording = False

        audio = self._recorder.stop_recording()
        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.import_btn.setEnabled(True)

        if len(audio) == 0:
            self.audio_status.setText("Recording was empty")
            self.audio_status.setStyleSheet(
                "color: #f38ba8; font-style: italic; padding: 4px;"
            )
            return

        self._audio_data = audio
        self._audio_sr = STANDARD_SR
        self._fingerprints = None
        duration = len(audio) / STANDARD_SR

        self.audio_status.setText(
            f"Recorded {duration:.1f}s  ({len(audio):,} samples, {STANDARD_SR} Hz)"
        )
        self.audio_status.setStyleSheet(
            "color: #a6e3a1; font-style: italic; padding: 4px;"
        )
        self.fp_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self.fp_status.setText("Ready to fingerprint")

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Known Fault Audio",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)",
        )
        if not path:
            return

        try:
            audio, sr = load_audio_file(path)
            self._audio_data = audio
            self._audio_sr = sr
            self._fingerprints = None
            duration = len(audio) / sr
            fname = os.path.basename(path)

            self.audio_status.setText(
                f"Loaded: {fname}  ({duration:.1f}s, {sr} Hz)"
            )
            self.audio_status.setStyleSheet(
                "color: #a6e3a1; font-style: italic; padding: 4px;"
            )
            self.fp_btn.setEnabled(True)
            self.save_btn.setEnabled(False)
            self.fp_status.setText("Ready to fingerprint")

        except Exception as e:
            self.audio_status.setText(f"Error: {e}")
            self.audio_status.setStyleSheet(
                "color: #f38ba8; font-style: italic; padding: 4px;"
            )

    # ---- Fingerprinting ----

    def _generate_fingerprint(self):
        if self._audio_data is None:
            return

        self.fp_btn.setEnabled(False)
        self.fp_status.setText("Generating fingerprint...")
        self.fp_status.setStyleSheet(
            "color: #f9e2af; font-style: italic; padding: 4px;"
        )

        self._fp_thread = FingerprintThread(
            self._audio_data, self._audio_sr
        )
        self._fp_thread.finished.connect(self._on_fp_done)
        self._fp_thread.error.connect(self._on_fp_error)
        self._fp_thread.start()

    def _on_fp_done(self, fingerprints):
        self._fingerprints = fingerprints
        stats = compute_fingerprint_stats(fingerprints)

        self.fp_status.setText(
            f"Fingerprint ready: {stats['total_hashes']:,} hashes, "
            f"{stats['unique_hashes']:,} unique, "
            f"span {stats['time_span']:.1f}s"
        )
        self.fp_status.setStyleSheet(
            "color: #a6e3a1; font-style: italic; padding: 4px;"
        )
        self.fp_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def _on_fp_error(self, err):
        self.fp_status.setText(f"Error: {err}")
        self.fp_status.setStyleSheet(
            "color: #f38ba8; font-style: italic; padding: 4px;"
        )
        self.fp_btn.setEnabled(True)

    # ---- Save ----

    def _save_signature(self):
        # Validate name
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a signature name.")
            self.name_input.setFocus()
            return

        if self._fingerprints is None or len(self._fingerprints) == 0:
            QMessageBox.warning(
                self, "No Fingerprint",
                "Please generate a fingerprint before saving.",
            )
            return

        # Gather fields
        category = self.category_combo.currentData()
        description = self.description_input.toPlainText().strip()

        # Append vehicle info to description if provided
        vehicle = self.vehicle_input.text().strip()
        if vehicle:
            if description:
                description += f"\nVehicle: {vehicle}"
            else:
                description = f"Vehicle: {vehicle}"

        # Parse and validate trouble codes (optional)
        codes_text = self.codes_input.text().strip()
        codes_list = []
        if codes_text:
            for raw in codes_text.replace(";", ",").split(","):
                code = raw.strip().upper()
                if not code:
                    continue
                if not DTC_PATTERN.match(code):
                    QMessageBox.warning(
                        self, "Invalid Code",
                        f"'{raw.strip()}' is not a valid OBD-II code.\n"
                        f"Format: P/B/C/U + 4 hex digits (e.g. P0300, P219A)",
                    )
                    self.codes_input.setFocus()
                    return
                codes_list.append(code)

        associated_codes = ",".join(codes_list)

        # Save to database
        try:
            sig_id = self.db_manager.add_fault_signature(
                name=name,
                description=description,
                category=category,
                associated_codes=associated_codes,
            )

            hashes = [
                (fp.hash_value, fp.time_offset) for fp in self._fingerprints
            ]
            self.db_manager.add_signature_hashes(sig_id, hashes)

            codes_msg = (
                f"\nAssociated codes: {associated_codes}"
                if associated_codes else "\nNo trouble codes (noise-only signature)"
            )
            QMessageBox.information(
                self, "Signature Saved",
                f"Saved '{name}' as signature #{sig_id}\n"
                f"Category: {category}\n"
                f"Fingerprint hashes: {len(hashes):,}"
                f"{codes_msg}",
            )

            self.signature_added.emit(sig_id)
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save signature:\n{e}"
            )


class BulkImportDialog(QDialog):
    """
    Dialog for bulk-importing audio files from a folder as fault signatures.

    File naming convention for auto-labeling:
        category__name__codes.wav
    Examples:
        bearing__Idler Pulley Bearing Lexus GS470__.wav
        engine__Misfire Cylinder 1__P0301.wav
        belt__Serpentine Belt Squeal__.wav

    Files not following the convention are imported with manual labeling.
    """

    import_complete = pyqtSignal(int)  # number of signatures imported

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._folder_path = ""
        self._files: list[str] = []

        self.setWindowTitle("Bulk Import Signatures")
        self.setMinimumSize(600, 450)
        self.resize(650, 500)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Instructions
        instructions = QLabel(
            "<b>Bulk Import Audio Files as Fault Signatures</b><br><br>"
            "Select a folder containing audio files (WAV, MP3, FLAC, OGG).<br>"
            "For automatic labeling, name files using this convention:<br>"
            "<code>category__Name of Fault__P0301.wav</code><br><br>"
            "Examples:<br>"
            "<code>bearing__Idler Pulley Bearing Lexus GS470__.wav</code><br>"
            "<code>engine__Misfire Cylinder 1__P0301.wav</code><br>"
            "<code>belt__Serpentine Belt Squeal__.wav</code><br><br>"
            "Leave the codes section empty (double underscore at end) "
            "for faults with no associated trouble code.<br>"
            "Files not matching this pattern will use the filename as the name."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #cdd6f4; padding: 8px;")
        layout.addWidget(instructions)

        # Folder selection
        folder_row = QHBoxLayout()
        self.folder_btn = QPushButton("Select Folder")
        self.folder_btn.setMinimumWidth(120)
        folder_row.addWidget(self.folder_btn)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding-left: 8px;"
        )
        folder_row.addWidget(self.folder_label, stretch=1)
        layout.addLayout(folder_row)

        # Default category for files without naming convention
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Default category:"))
        self.category_combo = QComboBox()
        for value, display in CATEGORIES:
            self.category_combo.addItem(display, value)
        cat_row.addWidget(self.category_combo)
        cat_row.addStretch()
        layout.addLayout(cat_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a6adc8; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.import_btn = QPushButton("Import All")
        self.import_btn.setObjectName("analyzeBtn")
        self.import_btn.setEnabled(False)
        self.import_btn.setMinimumWidth(120)
        btn_row.addWidget(self.import_btn)

        self.cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.folder_btn.clicked.connect(self._select_folder)
        self.import_btn.clicked.connect(self._run_import)
        self.cancel_btn.clicked.connect(self.reject)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder with Audio Files"
        )
        if not folder:
            return

        self._folder_path = folder

        # Find audio files
        extensions = (".wav", ".mp3", ".flac", ".ogg")
        self._files = [
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
            and f.lower().endswith(extensions)
        ]

        if not self._files:
            self.folder_label.setText(f"{folder}  (no audio files found)")
            self.import_btn.setEnabled(False)
        else:
            self.folder_label.setText(
                f"{folder}  ({len(self._files)} audio files)"
            )
            self.import_btn.setEnabled(True)

    def _parse_filename(self, filename: str) -> dict:
        """
        Parse a filename using the naming convention:
            category__name__codes.ext
        Returns dict with name, category, associated_codes.
        """
        base = os.path.splitext(filename)[0]
        parts = base.split("__")

        if len(parts) >= 2:
            category = parts[0].strip().lower()
            name = parts[1].strip()
            codes = parts[2].strip().upper() if len(parts) >= 3 else ""

            # Validate category
            valid_cats = [c[0] for c in CATEGORIES]
            if category not in valid_cats:
                category = self.category_combo.currentData()

            # Validate codes
            if codes:
                validated = []
                for c in codes.replace(";", ",").split(","):
                    c = c.strip()
                    if DTC_PATTERN.match(c):
                        validated.append(c)
                codes = ",".join(validated)

            return {
                "name": name if name else base,
                "category": category,
                "associated_codes": codes,
            }

        # Fallback: use filename as name
        return {
            "name": base.replace("_", " ").replace("-", " ").title(),
            "category": self.category_combo.currentData(),
            "associated_codes": "",
        }

    def _run_import(self):
        if not self._files:
            return

        self.import_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._files))
        self.progress_bar.setValue(0)

        imported = 0
        errors = []

        for i, filename in enumerate(self._files):
            self.status_label.setText(f"Processing: {filename}")
            self.progress_bar.setValue(i)
            # Force UI update
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            filepath = os.path.join(self._folder_path, filename)

            try:
                # Load audio
                audio, sr = load_audio_file(filepath)

                # Parse naming convention
                info = self._parse_filename(filename)

                # Generate fingerprint
                fps = generate_fingerprint(audio, sr)

                if len(fps) == 0:
                    errors.append(f"{filename}: no fingerprints generated")
                    continue

                # Save to database
                sig_id = self.db_manager.add_fault_signature(
                    name=info["name"],
                    description=f"Imported from: {filename}",
                    category=info["category"],
                    associated_codes=info["associated_codes"],
                )

                hashes = [(fp.hash_value, fp.time_offset) for fp in fps]
                self.db_manager.add_signature_hashes(sig_id, hashes)

                imported += 1

            except Exception as e:
                errors.append(f"{filename}: {e}")

        self.progress_bar.setValue(len(self._files))

        msg = f"Imported {imported} of {len(self._files)} files."
        if errors:
            msg += f"\n\n{len(errors)} errors:\n"
            for err in errors[:10]:
                msg += f"  - {err}\n"
            if len(errors) > 10:
                msg += f"  ... and {len(errors) - 10} more"

        self.status_label.setText(msg.split("\n")[0])

        QMessageBox.information(self, "Bulk Import Complete", msg)

        self.import_complete.emit(imported)
        if imported > 0:
            self.accept()
        else:
            self.import_btn.setEnabled(True)
            self.folder_btn.setEnabled(True)
