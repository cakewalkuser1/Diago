"""
Main Application Window
Assembles all GUI panels into the primary application window and
coordinates the full diagnostic pipeline.
"""

import os
from datetime import datetime

import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QFileDialog, QSplitter,
    QProgressBar, QTabWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction

from database.db_manager import DatabaseManager
from core.audio_io import STANDARD_SR, save_audio
from core.feature_extraction import BehavioralContext
from core.diagnostic_engine import (
    run_diagnostic_pipeline, run_diagnostic_pipeline_auto,
    DiagnosisResult,
)

from gui.record_panel import RecordPanel
from gui.spectrogram_widget import SpectrogramWidget
from gui.trouble_code_panel import TroubleCodePanel
from gui.context_panel import ContextPanel
from gui.results_panel import ResultsPanel
from gui.chat_panel import ChatPanel
from gui.add_signature_dialog import AddSignatureDialog, BulkImportDialog


class AnalysisThread(QThread):
    """Background thread for the diagnostic pipeline (audio or text-only)."""
    analysis_complete = pyqtSignal(object)  # DiagnosisResult
    analysis_error = pyqtSignal(str)
    progress_update = pyqtSignal(str)

    def __init__(
        self,
        audio_data: np.ndarray | None,
        sr: int,
        context: BehavioralContext,
        class_hints: dict,
        user_codes: list[str],
        db_manager: DatabaseManager,
        symptom_confidence: float = 0.0,
        llm_enabled: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.audio_data = audio_data
        self.sr = sr
        self.context = context
        self.class_hints = class_hints or {}
        self.user_codes = user_codes
        self.db_manager = db_manager
        self.symptom_confidence = symptom_confidence
        self.llm_enabled = llm_enabled

    def run(self):
        """Run the diagnostic pipeline (auto-routes audio vs text-only)."""
        try:
            result = run_diagnostic_pipeline_auto(
                audio_data=self.audio_data,
                sr=self.sr,
                context=self.context,
                class_hints=self.class_hints,
                user_codes=self.user_codes,
                db_manager=self.db_manager,
                symptom_confidence=self.symptom_confidence,
                llm_enabled=self.llm_enabled,
                progress_callback=lambda msg: self.progress_update.emit(msg),
            )
            self.analysis_complete.emit(result)

        except Exception as e:
            self.analysis_error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window for Auto Audio Analyzer."""

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._analysis_thread = None
        self._current_audio = None
        self._current_sr = STANDARD_SR

        self.setWindowTitle("Auto Audio Analyzer - Automotive Diagnostics")
        self.setMinimumSize(900, 750)
        self.resize(1100, 850)

        self._setup_menubar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_menubar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        import_action = QAction("Import Audio...", self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self._on_import_from_menu)
        file_menu.addAction(import_action)

        save_audio_action = QAction("Save Audio...", self)
        save_audio_action.setShortcut("Ctrl+S")
        save_audio_action.triggered.connect(self._on_save_audio)
        file_menu.addAction(save_audio_action)

        file_menu.addSeparator()

        export_action = QAction("Export Report...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(
            lambda: self.results_panel._export_report()
        )
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        spec_action = QAction("Spectrogram", self)
        spec_action.triggered.connect(
            lambda: self._switch_view("spectrogram")
        )
        view_menu.addAction(spec_action)

        mel_action = QAction("Mel Spectrogram", self)
        mel_action.triggered.connect(
            lambda: self._switch_view("mel")
        )
        view_menu.addAction(mel_action)

        wave_action = QAction("Waveform", self)
        wave_action.triggered.connect(
            lambda: self._switch_view("waveform")
        )
        view_menu.addAction(wave_action)

        # Database menu
        db_menu = menubar.addMenu("Database")

        add_sig_action = QAction("Add Signature...", self)
        add_sig_action.setShortcut("Ctrl+N")
        add_sig_action.triggered.connect(self._open_add_signature)
        db_menu.addAction(add_sig_action)

        bulk_import_action = QAction("Bulk Import from Folder...", self)
        bulk_import_action.triggered.connect(self._open_bulk_import)
        db_menu.addAction(bulk_import_action)

        db_menu.addSeparator()

        view_sigs = QAction("View Fault Signatures", self)
        view_sigs.triggered.connect(self._show_signatures)
        db_menu.addAction(view_sigs)

        view_history = QAction("Session History", self)
        view_history.triggered.connect(self._show_history)
        db_menu.addAction(view_history)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_central_widget(self):
        """Build the main window layout using a splitter for responsiveness."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 4, 12, 4)
        main_layout.setSpacing(4)

        # ---- Fixed header: title + record controls ----
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_label = QLabel("Auto Audio Analyzer")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #89b4fa; "
            "padding: 2px 0px;"
        )
        title_row.addWidget(title_label)

        subtitle = QLabel(
            "Physics-Aware Automotive Diagnostics"
        )
        subtitle.setStyleSheet(
            "font-size: 11px; color: #a6adc8; font-style: italic; "
            "padding-top: 4px;"
        )
        title_row.addWidget(subtitle)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        self.record_panel = RecordPanel()
        header_layout.addWidget(self.record_panel)

        main_layout.addWidget(header)

        # ---- Vertical splitter: spectrogram (top) | tabs (bottom) ----
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet(
            "QSplitter::handle { background-color: #45475a; border-radius: 3px; }"
            "QSplitter::handle:hover { background-color: #89b4fa; }"
        )

        # --- Top pane: Spectrogram ---
        self.spectrogram_widget = SpectrogramWidget()
        self.main_splitter.addWidget(self.spectrogram_widget)

        # --- Bottom pane: Tabbed area ---
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setDocumentMode(True)
        self.bottom_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #45475a; border-top: none; }"
            "QTabBar::tab { background: #313244; color: #a6adc8; "
            "padding: 5px 14px; border: 1px solid #45475a; "
            "border-bottom: none; border-radius: 4px 4px 0 0; "
            "margin-right: 2px; }"
            "QTabBar::tab:selected { background: #1e1e2e; color: #89b4fa; "
            "font-weight: bold; }"
            "QTabBar::tab:hover { background: #45475a; }"
        )

        # Tab 1: Symptoms & Codes (consolidated input)
        self.bottom_tabs.addTab(
            self._build_input_tab(), "Symptoms && Codes"
        )

        # Tab 2: Diagnosis Results
        self.results_panel = ResultsPanel(self.db_manager)
        self.bottom_tabs.addTab(self.results_panel, "Results")

        # Tab 3: DiagBot Chat
        self.chat_panel = ChatPanel(db_manager=self.db_manager)
        self.bottom_tabs.addTab(self.chat_panel, "DiagBot")

        self.main_splitter.addWidget(self.bottom_tabs)

        # Splitter proportions: ~55% spectrogram, ~45% tabs
        self.main_splitter.setSizes([550, 450])
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        # Minimum heights so neither pane gets crushed
        self.main_splitter.setChildrenCollapsible(False)

        main_layout.addWidget(self.main_splitter, stretch=1)

    def _build_input_tab(self) -> QWidget:
        """Build the consolidated Symptoms & Codes input tab."""
        # Scroll area so content is accessible even in small windows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Context panel (behavioral observations)
        self.context_panel = ContextPanel()
        layout.addWidget(self.context_panel)

        # Symptom + trouble code panel
        self.trouble_code_panel = TroubleCodePanel(db_manager=self.db_manager)
        layout.addWidget(self.trouble_code_panel)

        # Analyze button row
        analyze_row = QHBoxLayout()
        analyze_row.setSpacing(8)

        self.analyze_btn = QPushButton("Diagnose")
        self.analyze_btn.setObjectName("analyzeBtn")
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setMinimumHeight(36)
        self.analyze_btn.setToolTip(
            "Run diagnosis from symptoms, codes, and/or audio.\n"
            "Audio recording is optional -- the more data you provide,\n"
            "the more accurate the diagnosis."
        )
        analyze_row.addWidget(self.analyze_btn)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding-left: 12px;"
        )
        analyze_row.addWidget(self.progress_label)
        analyze_row.addStretch()

        layout.addLayout(analyze_row)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _setup_statusbar(self):
        """Create the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # Permanent status items
        self.db_status = QLabel(
            f"DB: {os.path.basename(self.db_manager.db_path)}"
        )
        self.db_status.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.statusbar.addPermanentWidget(self.db_status)

        sigs = self.db_manager.get_all_signatures()
        self.sig_count_label = QLabel(f"Signatures: {len(sigs)}")
        self.sig_count_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.statusbar.addPermanentWidget(self.sig_count_label)

        self.statusbar.showMessage("Ready", 3000)

    def _setup_agent(self):
        """Initialize the mechanic agent for the chat panel."""
        try:
            from core.mechanic_agent import MechanicAgent
            self._mechanic_agent = MechanicAgent(
                db_manager=self.db_manager,
            )
            self.chat_panel.set_agent(self._mechanic_agent)
        except Exception:
            self._mechanic_agent = None

    def _connect_signals(self):
        """Wire up all signal connections between panels."""
        # Record panel -> spectrogram display
        self.record_panel.audio_loaded.connect(self._on_audio_loaded)
        self.record_panel.recording_update.connect(self._on_recording_update)
        self.record_panel.status_message.connect(
            lambda msg: self.statusbar.showMessage(msg, 5000)
        )

        # View mode changes
        self.record_panel.view_combo.currentTextChanged.connect(
            self._on_view_mode_changed
        )

        # Analyze button
        self.analyze_btn.clicked.connect(self._run_analysis)

        # Results panel
        self.results_panel.session_saved.connect(self._on_session_saved)

        # Initialize the mechanic agent
        self._setup_agent()

    # ---- Slots ----

    def _on_audio_loaded(self, audio_data: np.ndarray, sr: int):
        """Handle new audio data from recording or file import."""
        self._current_audio = audio_data
        self._current_sr = sr

        # Display spectrogram in the selected view mode
        mode = self.record_panel.current_view_mode
        self.spectrogram_widget.display_spectrogram(audio_data, sr, mode)

        # Enable analysis
        self._update_diagnose_button()
        self.progress_label.setText("")

    def _on_recording_update(self, buffer: np.ndarray):
        """Update waveform display during recording."""
        self.spectrogram_widget.update_waveform_realtime(buffer, STANDARD_SR)

    def _on_view_mode_changed(self, mode_text: str):
        """Switch the spectrogram display mode."""
        mode_map = {
            "Spectrogram": "spectrogram",
            "Mel Spectrogram": "mel",
            "Waveform": "waveform",
        }
        mode = mode_map.get(mode_text, "spectrogram")
        self.spectrogram_widget.switch_mode(mode)

    def _run_analysis(self):
        """Start the diagnostic pipeline (works with or without audio)."""
        # Gather inputs first to check if we have ANYTHING to diagnose
        user_codes = self.trouble_code_panel.codes
        context = self.context_panel.get_context()

        # Merge symptom-parsed context (parsed keywords override "unknown" fields)
        symptom_ctx = self.trouble_code_panel.get_merged_context()
        symptom_confidence = 0.0
        class_hints = {}
        if symptom_ctx is not None:
            context = _merge_contexts(context, symptom_ctx)

        # Get class hints and symptom confidence from the symptom parser
        parsed = self.trouble_code_panel.get_parsed_symptoms()
        if parsed is not None:
            class_hints = parsed.class_hints
            symptom_confidence = parsed.confidence

        # Check we have at least SOME data (audio OR symptoms OR codes)
        has_audio = self._current_audio is not None
        has_symptoms = bool(class_hints) or context.noise_character != "unknown"
        has_codes = bool(user_codes)
        has_any_context = any([
            context.rpm_dependency, context.speed_dependency,
            context.load_dependency, context.cold_only,
            context.occurs_at_idle, context.intermittent,
        ])

        if not has_audio and not has_symptoms and not has_codes and not has_any_context:
            QMessageBox.warning(
                self,
                "No Data",
                "Please provide symptoms, trouble codes, or audio.\n\n"
                "The more information you give, the more accurate\n"
                "the diagnosis will be.",
            )
            return

        # Disable analyze button during processing
        self.analyze_btn.setEnabled(False)
        mode_msg = (
            "Starting full audio+text pipeline..."
            if has_audio
            else "Starting symptom-based diagnosis..."
        )
        self.progress_label.setText(mode_msg)
        self.progress_label.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding-left: 12px;"
        )

        # Run pipeline in background thread
        self._analysis_thread = AnalysisThread(
            audio_data=self._current_audio,
            sr=self._current_sr,
            context=context,
            class_hints=class_hints,
            user_codes=user_codes,
            db_manager=self.db_manager,
            symptom_confidence=symptom_confidence,
            llm_enabled=False,  # LLM disabled by default
        )
        self._analysis_thread.analysis_complete.connect(
            self._on_analysis_complete
        )
        self._analysis_thread.analysis_error.connect(
            self._on_analysis_error
        )
        self._analysis_thread.progress_update.connect(
            lambda msg: self.progress_label.setText(msg)
        )
        self._analysis_thread.start()

    def _on_analysis_complete(self, result: DiagnosisResult):
        """Handle completed diagnostic pipeline."""
        self._update_diagnose_button()

        duration = (
            len(self._current_audio) / self._current_sr
            if self._current_audio is not None else 0
        )

        # Update progress label with top result
        from core.diagnostic_engine import CLASS_DISPLAY_NAMES
        top_display = CLASS_DISPLAY_NAMES.get(result.top_class, result.top_class)

        if result.is_ambiguous:
            self.progress_label.setText("Result: Ambiguous - more data needed")
            self.progress_label.setStyleSheet(
                "color: #f9e2af; font-style: italic; padding-left: 12px;"
            )
        else:
            score = result.class_scores.get(result.top_class, 0)
            self.progress_label.setText(
                f"Diagnosis: {top_display} ({score:.0%}) | "
                f"Confidence: {result.confidence.upper()}"
            )
            color = {
                "high": "#a6e3a1",
                "medium": "#f9e2af",
                "low": "#f38ba8",
            }.get(result.confidence, "#a6adc8")
            self.progress_label.setStyleSheet(
                f"color: {color}; font-style: italic; padding-left: 12px;"
            )

        # Display in results panel
        self.results_panel.display_diagnosis(
            result=result,
            user_codes=self.trouble_code_panel.codes,
            duration=duration,
        )

        # Pass results to the mechanic agent for context
        if hasattr(self, '_mechanic_agent') and self._mechanic_agent:
            self._mechanic_agent.set_diagnosis_result(result)

        if result.fingerprint_count > 0:
            self.statusbar.showMessage(
                f"Pipeline complete: {result.fingerprint_count} fingerprints, "
                f"top class: {top_display} ({result.confidence})",
                10000,
            )
        else:
            self.statusbar.showMessage(
                f"Symptom diagnosis complete: "
                f"top class: {top_display} ({result.confidence})",
                10000,
            )

    def _on_analysis_error(self, error_msg: str):
        """Handle analysis errors."""
        self._update_diagnose_button()
        self.progress_label.setText(f"Error: {error_msg}")
        self.progress_label.setStyleSheet(
            "color: #f38ba8; font-style: italic; padding-left: 12px;"
        )
        self.statusbar.showMessage(f"Analysis error: {error_msg}", 10000)

    def _update_diagnose_button(self):
        """Enable the Diagnose button (always enabled -- user can diagnose
        from symptoms, codes, audio, or any combination)."""
        self.analyze_btn.setEnabled(True)

    def _on_session_saved(self, session_id: int):
        """Handle session saved event."""
        self.statusbar.showMessage(
            f"Session #{session_id} saved", 5000
        )

    # ---- Menu Actions ----

    def _on_import_from_menu(self):
        """Trigger file import from the menu."""
        self.record_panel._import_file()

    def _on_save_audio(self):
        """Save current audio to a file."""
        if self._current_audio is None:
            QMessageBox.information(
                self, "No Audio", "No audio to save."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Audio",
            f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
            "WAV Files (*.wav);;All Files (*)",
        )

        if file_path:
            try:
                save_audio(self._current_audio, file_path, self._current_sr)
                self.statusbar.showMessage(f"Audio saved: {file_path}", 5000)
            except Exception as e:
                QMessageBox.warning(
                    self, "Save Error", f"Failed to save audio: {e}"
                )

    def _switch_view(self, mode: str):
        """Switch spectrogram view from menu."""
        mode_display = {
            "spectrogram": "Spectrogram",
            "mel": "Mel Spectrogram",
            "waveform": "Waveform",
        }
        self.record_panel.view_combo.setCurrentText(
            mode_display.get(mode, "Spectrogram")
        )

    def _open_add_signature(self):
        """Open the Add Signature dialog."""
        dialog = AddSignatureDialog(self.db_manager, self)
        dialog.signature_added.connect(self._on_signature_added)
        dialog.exec()

    def _open_bulk_import(self):
        """Open the Bulk Import dialog."""
        dialog = BulkImportDialog(self.db_manager, self)
        dialog.import_complete.connect(self._on_bulk_import_done)
        dialog.exec()

    def _on_signature_added(self, sig_id: int):
        """Handle a new signature being added."""
        self._refresh_sig_count()
        self.statusbar.showMessage(
            f"Signature #{sig_id} added to database", 5000
        )

    def _on_bulk_import_done(self, count: int):
        """Handle bulk import completion."""
        self._refresh_sig_count()
        self.statusbar.showMessage(
            f"Bulk import: {count} signatures added", 5000
        )

    def _refresh_sig_count(self):
        """Update the signature count in the status bar."""
        count = self.db_manager.get_signature_count()
        self.sig_count_label.setText(f"Signatures: {count}")

    def _show_signatures(self):
        """Show the fault signatures database."""
        sigs = self.db_manager.get_all_signatures()

        msg = "Known Fault Signatures:\n\n"
        for sig in sigs:
            codes = (
                f" [{sig.associated_codes}]"
                if sig.associated_codes else ""
            )
            msg += f"  - {sig.name}{codes}\n"
            msg += f"    Category: {sig.category.title()}\n"
            hash_count = self.db_manager.get_hash_count_by_signature(sig.id)
            msg += f"    Fingerprint hashes: {hash_count}\n\n"

        QMessageBox.information(self, "Fault Signatures", msg)

    def _show_history(self):
        """Show session history."""
        sessions = self.db_manager.get_session_history(20)

        if not sessions:
            QMessageBox.information(
                self, "Session History", "No analysis sessions found."
            )
            return

        msg = "Recent Analysis Sessions:\n\n"
        for s in sessions:
            msg += f"  Session #{s.id} - {s.timestamp}\n"
            if s.user_codes:
                msg += f"    Codes: {s.user_codes}\n"
            msg += f"    Duration: {s.duration_seconds:.1f}s\n"

            matches = self.db_manager.get_session_matches(s.id)
            if matches:
                msg += "    Matches:\n"
                for m in matches:
                    msg += (
                        f"      - {m.fault_name}: "
                        f"{m.confidence_pct:.0f}%\n"
                    )
            msg += "\n"

        QMessageBox.information(self, "Session History", msg)

    def _show_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About Auto Audio Analyzer",
            "<h2>Auto Audio Analyzer</h2>"
            "<p>Physics-Aware Automotive Diagnostics with "
            "Digital Fingerprinting</p>"
            "<p>This tool uses a multi-stage diagnostic pipeline:</p>"
            "<ol>"
            "<li>Audio preprocessing (normalize, bandpass, denoise)</li>"
            "<li>Feature extraction (spectral + temporal + behavioral)</li>"
            "<li>Mechanical class scoring with physics constraints</li>"
            "<li>Fingerprint matching against known fault database</li>"
            "</ol>"
            "<p>The constraint engine enforces physics rules that "
            "prevent impossible diagnoses.</p>"
            "<hr>"
            "<p><b>7 Mechanical Classes:</b> Bearing, Gear Mesh, "
            "Belt/Friction, Hydraulic, Electrical, Combustion, "
            "Structural Resonance</p>"
            "<p><b>Audio formats:</b> WAV, MP3, FLAC, OGG</p>",
        )

    def closeEvent(self, event):
        """Clean up on window close."""
        # Stop any running recording
        if hasattr(self.record_panel, "_recording_thread"):
            thread = self.record_panel._recording_thread
            if thread is not None and thread.isRunning():
                thread.stop()
                thread.wait(3000)

        # Stop analysis thread
        if (
            self._analysis_thread is not None
            and self._analysis_thread.isRunning()
        ):
            self._analysis_thread.wait(3000)

        # Close database
        self.db_manager.close()

        event.accept()


def _merge_contexts(
    gui_ctx: BehavioralContext,
    symptom_ctx: BehavioralContext,
) -> BehavioralContext:
    """
    Merge two BehavioralContext objects: the GUI panel's context
    (user-selected dropdowns/checkboxes) takes priority for explicitly
    set fields, and symptom-parsed context fills in 'unknown' / False gaps.

    Rules:
    - Boolean fields: OR (either source sets it)
    - String fields: GUI wins if not "unknown", else symptom wins
    """
    from dataclasses import fields as dc_fields

    merged_dict = {}
    for f in dc_fields(BehavioralContext):
        gui_val = getattr(gui_ctx, f.name)
        sym_val = getattr(symptom_ctx, f.name)

        if isinstance(gui_val, bool):
            # OR: either source saying True wins
            merged_dict[f.name] = gui_val or sym_val
        elif isinstance(gui_val, str):
            # GUI wins unless "unknown"
            if gui_val != "unknown":
                merged_dict[f.name] = gui_val
            else:
                merged_dict[f.name] = sym_val
        else:
            merged_dict[f.name] = gui_val

    return BehavioralContext(**merged_dict)
