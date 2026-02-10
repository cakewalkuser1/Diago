"""
Diagnostic Results Panel
Displays the full diagnostic pipeline output:
- Mechanical class score bars with probabilities
- Confidence indicator and ambiguity warning
- Narrative explanation (LLM or fallback)
- Fingerprint match cards (from existing DB matching)
- Session saving and report export
"""

import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QFileDialog,
    QTextEdit, QSizePolicy, QMessageBox, QProgressBar,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from database.db_manager import MatchResult, DatabaseManager
from core.diagnostic_engine import (
    DiagnosisResult, CLASS_DISPLAY_NAMES, CLASS_DESCRIPTIONS,
)
from core.llm_reasoning import generate_fallback_narrative


# ---------------------------------------------------------------------------
# Score Bar Widget
# ---------------------------------------------------------------------------

class ClassScoreBar(QFrame):
    """Horizontal bar showing a mechanical class name, probability, and bar."""

    def __init__(self, class_name: str, score: float, is_top: bool = False,
                 penalty: float = 0.0, parent=None):
        super().__init__(parent)
        self._setup_ui(class_name, score, is_top, penalty)

    def _setup_ui(self, class_name: str, score: float, is_top: bool,
                  penalty: float):
        display_name = CLASS_DISPLAY_NAMES.get(class_name, class_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(8)

        # Class name
        name_label = QLabel(display_name)
        name_label.setMinimumWidth(200)
        name_label.setMaximumWidth(200)
        style = "font-size: 12px; "
        if is_top:
            style += "font-weight: bold; color: #cdd6f4;"
        else:
            style += "color: #a6adc8;"
        name_label.setStyleSheet(style)
        layout.addWidget(name_label)

        # Progress bar
        bar = QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(int(score * 100))
        bar.setTextVisible(False)
        bar.setMaximumHeight(16)

        bar_color = self._score_color(score, is_top)
        bar.setStyleSheet(
            f"QProgressBar {{ "
            f"  background-color: #313244; "
            f"  border: 1px solid #45475a; "
            f"  border-radius: 4px; "
            f"}} "
            f"QProgressBar::chunk {{ "
            f"  background-color: {bar_color}; "
            f"  border-radius: 3px; "
            f"}}"
        )
        layout.addWidget(bar, stretch=1)

        # Percentage label
        pct_label = QLabel(f"{score:.0%}")
        pct_label.setMinimumWidth(45)
        pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        pct_color = bar_color if is_top else "#a6adc8"
        pct_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {pct_color};"
        )
        layout.addWidget(pct_label)

        # Penalty indicator
        if penalty > 0:
            pen_label = QLabel(f"(-{penalty:.1f})")
            pen_label.setStyleSheet(
                "font-size: 10px; color: #f38ba8; font-style: italic;"
            )
            pen_label.setToolTip(
                f"Physics constraint penalty of {penalty:.2f} applied"
            )
            layout.addWidget(pen_label)

    def _score_color(self, score: float, is_top: bool) -> str:
        if is_top:
            if score >= 0.6:
                return "#a6e3a1"
            elif score >= 0.4:
                return "#f9e2af"
            else:
                return "#f38ba8"
        return "#585b70"


# ---------------------------------------------------------------------------
# Fingerprint Match Card (kept from original)
# ---------------------------------------------------------------------------

class ResultCard(QFrame):
    """A single fingerprint match result card."""

    def __init__(self, result: MatchResult, rank: int, parent=None):
        super().__init__(parent)
        self.result = result
        self._setup_ui(rank)

    def _setup_ui(self, rank: int):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(self._get_card_style())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Rank
        rank_label = QLabel(f"#{rank}")
        rank_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #585b70; "
            "min-width: 28px;"
        )
        layout.addWidget(rank_label)

        # Confidence
        conf_color = self._get_confidence_color()
        conf_label = QLabel(f"{self.result.confidence_pct:.0f}%")
        conf_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {conf_color}; "
            f"min-width: 50px;"
        )
        conf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(conf_label)

        # Details
        details = QVBoxLayout()
        details.setSpacing(1)

        name_label = QLabel(self.result.fault_name)
        name_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #cdd6f4;"
        )
        details.addWidget(name_label)

        meta_parts = [f"Category: {self.result.category.title()}"]
        if self.result.trouble_codes:
            meta_parts.append(f"Codes: {self.result.trouble_codes}")
        meta_label = QLabel(" | ".join(meta_parts))
        meta_label.setStyleSheet("font-size: 10px; color: #89b4fa;")
        details.addWidget(meta_label)

        layout.addLayout(details, stretch=1)

    def _get_card_style(self) -> str:
        c = self.result.confidence_pct
        border = "#a6e3a1" if c >= 80 else "#f9e2af" if c >= 60 else "#f38ba8"
        return (
            f"background-color: #313244; border: 1px solid {border}; "
            f"border-left: 3px solid {border}; border-radius: 5px; "
            f"margin: 1px 0px;"
        )

    def _get_confidence_color(self) -> str:
        c = self.result.confidence_pct
        return "#a6e3a1" if c >= 80 else "#f9e2af" if c >= 60 else "#f38ba8"


# ---------------------------------------------------------------------------
# Main Results Panel
# ---------------------------------------------------------------------------

class ResultsPanel(QWidget):
    """
    Panel displaying complete diagnostic results.

    Signals:
        session_saved: Emitted when a session is saved.
    """
    session_saved = pyqtSignal(int)

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._current_diagnosis: DiagnosisResult | None = None
        self._current_results: list[MatchResult] = []
        self._current_codes: list[str] = []
        self._current_audio_path: str = ""
        self._current_duration: float = 0.0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header
        header_row = QHBoxLayout()
        header = QLabel("Diagnostic Results")
        header.setObjectName("sectionHeader")
        header_row.addWidget(header)
        header_row.addStretch()

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #a6adc8; font-size: 11px; font-style: italic;"
        )
        header_row.addWidget(self.stats_label)
        layout.addLayout(header_row)

        # Scrollable content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #45475a; border-radius: 6px; }"
            "QScrollBar:vertical { background: #313244; width: 8px; }"
            "QScrollBar::handle:vertical { "
            "  background: #585b70; border-radius: 4px; }"
        )

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(8, 8, 8, 8)
        self.results_layout.setSpacing(6)

        # Placeholder
        self._show_placeholder()

        self.scroll_area.setWidget(self.results_container)
        layout.addWidget(self.scroll_area)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_btn = QPushButton("Save Session")
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumWidth(120)
        btn_row.addWidget(self.save_btn)

        self.export_btn = QPushButton("Export Report")
        self.export_btn.setEnabled(False)
        self.export_btn.setMinimumWidth(120)
        btn_row.addWidget(self.export_btn)

        btn_row.addStretch()

        self.clear_btn = QPushButton("Clear Results")
        self.clear_btn.setEnabled(False)
        self.clear_btn.setMinimumWidth(110)
        btn_row.addWidget(self.clear_btn)

        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.save_btn.clicked.connect(self._save_session)
        self.export_btn.clicked.connect(self._export_report)
        self.clear_btn.clicked.connect(self.clear_results)

    # ------------------------------------------------------------------
    # Display diagnosis (NEW pipeline output)
    # ------------------------------------------------------------------

    def display_diagnosis(
        self,
        result: DiagnosisResult,
        user_codes: list[str] | None = None,
        audio_path: str = "",
        duration: float = 0.0,
    ):
        """Display the full DiagnosisResult from the pipeline."""
        self._current_diagnosis = result
        self._current_results = result.fingerprint_matches
        self._current_codes = user_codes or []
        self._current_audio_path = audio_path
        self._current_duration = duration

        self._clear_layout()

        # --- Section 1: Confidence Banner ---
        self._add_confidence_banner(result)

        # --- Section 2: Mechanical Class Scores ---
        scores_header = QLabel("Mechanical Class Scores")
        scores_header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #89b4fa; "
            "padding-top: 8px;"
        )
        self.results_layout.addWidget(scores_header)

        sorted_classes = sorted(
            result.class_scores.items(), key=lambda x: x[1], reverse=True
        )
        for cls, score in sorted_classes:
            is_top = (cls == result.top_class)
            penalty = result.penalties_applied.get(cls, 0.0)
            bar = ClassScoreBar(cls, score, is_top, penalty)
            self.results_layout.addWidget(bar)

        # --- Section 3: Narrative ---
        narrative = result.llm_narrative
        if narrative is None:
            narrative = generate_fallback_narrative(
                result.class_scores,
                result.features,
                result.penalties_applied,
                result.is_ambiguous,
            )

        narr_header = QLabel("Analysis")
        narr_header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #89b4fa; "
            "padding-top: 10px;"
        )
        self.results_layout.addWidget(narr_header)

        narr_label = QLabel(narrative)
        narr_label.setWordWrap(True)
        narr_label.setStyleSheet(
            "font-size: 12px; color: #cdd6f4; padding: 8px; "
            "background-color: #313244; border-radius: 6px;"
        )
        self.results_layout.addWidget(narr_label)

        # --- Section 4: Fingerprint Matches ---
        if result.fingerprint_matches:
            fp_header = QLabel(
                f"Fingerprint Matches ({len(result.fingerprint_matches)})"
            )
            fp_header.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #89b4fa; "
                "padding-top: 10px;"
            )
            self.results_layout.addWidget(fp_header)

            for rank, match in enumerate(result.fingerprint_matches, 1):
                card = ResultCard(match, rank)
                self.results_layout.addWidget(card)

        self.results_layout.addStretch()

        # Stats
        if result.fingerprint_count > 0:
            self.stats_label.setText(
                f"{result.fingerprint_count} fingerprints | "
                f"{len(result.fingerprint_matches)} DB matches | "
                f"Confidence: {result.confidence.upper()}"
            )
        else:
            self.stats_label.setText(
                f"Symptom-based diagnosis | "
                f"Confidence: {result.confidence.upper()}"
            )

        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save Session")
        self.export_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def _add_confidence_banner(self, result: DiagnosisResult):
        """Add a colored confidence banner at the top of results."""
        banner = QFrame()
        banner.setFrameShape(QFrame.Shape.StyledPanel)

        if result.is_ambiguous:
            banner_color = "#f38ba8"
            banner_border = "#f38ba8"
            text = "AMBIGUOUS - Additional data recommended"
            if result.fingerprint_count == 0:
                subtext = (
                    "Not enough information to make a confident diagnosis. "
                    "Try describing the noise character, when it happens, "
                    "adding trouble codes, or recording audio."
                )
            else:
                subtext = (
                    "No mechanical class scored above the confidence threshold. "
                    "Try recording under different conditions or adding "
                    "more symptom details."
                )
        else:
            top_display = CLASS_DISPLAY_NAMES.get(
                result.top_class, result.top_class
            )
            top_score = result.class_scores.get(result.top_class, 0)

            if result.confidence == "high":
                banner_color = "#a6e3a1"
                banner_border = "#a6e3a1"
            elif result.confidence == "medium":
                banner_color = "#f9e2af"
                banner_border = "#f9e2af"
            else:
                banner_color = "#f38ba8"
                banner_border = "#f38ba8"

            text = f"{top_display} - {top_score:.0%}"
            subtext = f"Confidence: {result.confidence.upper()}"

        banner.setStyleSheet(
            f"background-color: #313244; "
            f"border: 1px solid {banner_border}; "
            f"border-left: 5px solid {banner_border}; "
            f"border-radius: 6px;"
        )

        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel(text)
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {banner_color};"
        )
        banner_layout.addWidget(title)

        sub = QLabel(subtext)
        sub.setStyleSheet("font-size: 11px; color: #a6adc8;")
        sub.setWordWrap(True)
        banner_layout.addWidget(sub)

        self.results_layout.addWidget(banner)

    # ------------------------------------------------------------------
    # Legacy display_results (still usable for fingerprint-only flow)
    # ------------------------------------------------------------------

    def display_results(
        self,
        results: list[MatchResult],
        user_codes: list[str] | None = None,
        audio_path: str = "",
        duration: float = 0.0,
        fingerprint_count: int = 0,
    ):
        """Display fingerprint-only match results (legacy compatibility)."""
        self._current_results = results
        self._current_codes = user_codes or []
        self._current_audio_path = audio_path
        self._current_duration = duration
        self._current_diagnosis = None

        self._clear_layout()

        if not results:
            no_match = QLabel("No matching fault signatures found.")
            no_match.setStyleSheet(
                "color: #f9e2af; font-size: 13px; padding: 30px; "
                "font-style: italic;"
            )
            no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.addWidget(no_match)
        else:
            for rank, result in enumerate(results, 1):
                card = ResultCard(result, rank)
                self.results_layout.addWidget(card)

        self.results_layout.addStretch()

        self.stats_label.setText(
            f"{fingerprint_count} fingerprints | "
            f"{len(results)} matches found"
        )
        self.save_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Common
    # ------------------------------------------------------------------

    def clear_results(self):
        self._clear_layout()
        self._current_results = []
        self._current_diagnosis = None
        self._show_placeholder()
        self.stats_label.setText("")
        self.save_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def _show_placeholder(self):
        placeholder = QLabel("Run diagnosis to see results")
        placeholder.setStyleSheet(
            "color: #585b70; font-style: italic; font-size: 13px; "
            "padding: 40px;"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_layout.addWidget(placeholder)
        self.results_layout.addStretch()

    def _clear_layout(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _save_session(self):
        if not self._current_results and self._current_diagnosis is None:
            return

        try:
            notes = ""
            if self._current_diagnosis:
                top = CLASS_DISPLAY_NAMES.get(
                    self._current_diagnosis.top_class, ""
                )
                notes = (
                    f"Top class: {top} "
                    f"({self._current_diagnosis.confidence})"
                )

            session_id = self.db_manager.create_session(
                audio_path=self._current_audio_path,
                user_codes=",".join(self._current_codes),
                notes=notes,
                duration_seconds=self._current_duration,
            )

            for result in self._current_results:
                self.db_manager.add_session_match(
                    session_id=session_id,
                    signature_id=result.signature_id,
                    confidence=result.confidence_pct,
                )

            self.session_saved.emit(session_id)
            self.save_btn.setEnabled(False)
            self.save_btn.setText("Session Saved")

            QMessageBox.information(
                self, "Session Saved",
                f"Analysis session #{session_id} saved successfully.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error", f"Failed to save session: {str(e)}"
            )

    def _export_report(self):
        if self._current_diagnosis is None and not self._current_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostic Report",
            f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            report = self._generate_report()
            with open(file_path, "w") as f:
                f.write(report)
            QMessageBox.information(
                self, "Report Exported", f"Report saved to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Export Error", f"Failed to export report: {str(e)}"
            )

    def _generate_report(self) -> str:
        lines = [
            "=" * 65,
            "AUTOMOTIVE AUDIO DIAGNOSTIC REPORT",
            "=" * 65,
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Audio Duration: {self._current_duration:.1f}s",
        ]

        if self._current_audio_path:
            lines.append(f"Audio File: {self._current_audio_path}")
        if self._current_codes:
            lines.append(
                f"User Trouble Codes: {', '.join(self._current_codes)}"
            )

        if self._current_diagnosis:
            diag = self._current_diagnosis
            top_display = CLASS_DISPLAY_NAMES.get(diag.top_class, diag.top_class)
            top_score = diag.class_scores.get(diag.top_class, 0)

            lines.extend([
                "",
                "-" * 65,
                "DIAGNOSTIC CLASSIFICATION",
                "-" * 65,
                f"  Primary: {top_display} ({top_score:.0%})",
                f"  Confidence: {diag.confidence.upper()}",
                f"  Ambiguous: {'Yes' if diag.is_ambiguous else 'No'}",
                "",
                "  Class Scores:",
            ])

            sorted_scores = sorted(
                diag.class_scores.items(), key=lambda x: x[1], reverse=True
            )
            for cls, score in sorted_scores:
                display = CLASS_DISPLAY_NAMES.get(cls, cls)
                penalty = diag.penalties_applied.get(cls, 0.0)
                pen_str = f"  (penalty: -{penalty:.2f})" if penalty > 0 else ""
                lines.append(f"    {display}: {score:.1%}{pen_str}")

            lines.extend([
                "",
                "-" * 65,
                "EXTRACTED FEATURES",
                "-" * 65,
            ])
            for key, val in diag.features.items():
                if isinstance(val, float):
                    lines.append(f"    {key}: {val:.4f}")
                else:
                    lines.append(f"    {key}: {val}")

            # Narrative
            narrative = diag.llm_narrative
            if narrative is None:
                narrative = generate_fallback_narrative(
                    diag.class_scores, diag.features,
                    diag.penalties_applied, diag.is_ambiguous,
                )
            lines.extend([
                "",
                "-" * 65,
                "ANALYSIS NARRATIVE",
                "-" * 65,
                f"  {narrative}",
            ])

        # Fingerprint matches
        if self._current_results:
            lines.extend([
                "",
                "-" * 65,
                "FINGERPRINT MATCHES",
                "-" * 65,
            ])
            for rank, r in enumerate(self._current_results, 1):
                lines.append(
                    f"  #{rank}. {r.fault_name}: "
                    f"{r.confidence_pct:.1f}% "
                    f"[{r.category}]"
                )
                if r.trouble_codes:
                    lines.append(f"       Codes: {r.trouble_codes}")

        lines.extend([
            "",
            "-" * 65,
            "NOTES",
            "-" * 65,
            "  Generated by Auto Audio Analyzer (Physics-Aware Pipeline).",
            "  Constraint penalties enforce physics rules that prevent",
            "  impossible diagnoses regardless of score.",
            "",
            "  HIGH confidence: strong single-class match",
            "  MEDIUM confidence: likely match, verify recommended",
            "  LOW / AMBIGUOUS: additional data recommended",
            "",
            "=" * 65,
        ])

        return "\n".join(lines)
