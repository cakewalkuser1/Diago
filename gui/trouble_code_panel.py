"""
Combined Symptom + Trouble Code Panel
Provides free-text symptom input with keyword parsing, code entry with
DB-powered descriptions, parsed keyword chips, and suggested code chips.

Replaces the original TroubleCodePanel with a richer input experience.
"""

import re

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLineEdit, QLabel, QFrame, QSizePolicy, QTextEdit,
    QGroupBox, QScrollArea, QToolTip,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QCursor

from core.symptom_parser import parse_symptoms, ParsedSymptoms
from core.feature_extraction import BehavioralContext


# Regex pattern for valid OBD-II trouble codes
DTC_PATTERN = re.compile(r"^[PBCU]\d{4}$", re.IGNORECASE)


class KeywordChip(QFrame):
    """A small styled chip displaying a matched keyword."""

    removed = pyqtSignal(str)

    def __init__(self, text: str, color: str = "#89b4fa", parent=None):
        super().__init__(parent)
        self._text = text
        self.setStyleSheet(
            f"background-color: {color}; color: #1e1e2e; "
            f"border-radius: 10px; padding: 2px 4px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)

        label = QLabel(text)
        label.setStyleSheet(
            "font-size: 11px; font-weight: bold; background: transparent; "
            "color: #1e1e2e; padding: 0;"
        )
        layout.addWidget(label)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet(
            "background: rgba(0,0,0,0.2); color: #1e1e2e; "
            "border-radius: 8px; font-size: 10px; font-weight: bold; "
            "padding: 0; border: none; min-height: 0;"
        )
        close_btn.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(close_btn)

    @property
    def text(self) -> str:
        return self._text


class CodeChip(QFrame):
    """A chip for a trouble code with color coding by type."""

    clicked = pyqtSignal(str)

    def __init__(self, code: str, description: str = "", parent=None):
        super().__init__(parent)
        self._code = code
        self._description = description

        color = self._get_code_color(code)
        self.setStyleSheet(
            f"background-color: {color}; color: #1e1e2e; "
            f"border-radius: 10px; padding: 2px 8px;"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        label = QLabel(code)
        label.setStyleSheet(
            "font-size: 12px; font-weight: bold; font-family: monospace; "
            "background: transparent; color: #1e1e2e; padding: 0;"
        )
        layout.addWidget(label)

        if description:
            self.setToolTip(f"{code}: {description}")

    def mousePressEvent(self, event):
        self.clicked.emit(self._code)

    @staticmethod
    def _get_code_color(code: str) -> str:
        prefix = code[0].upper() if code else "P"
        colors = {
            "P": "#f9e2af",  # Yellow - Powertrain
            "B": "#89b4fa",  # Blue - Body
            "C": "#a6e3a1",  # Green - Chassis
            "U": "#cba6f7",  # Purple - Network
        }
        return colors.get(prefix, "#cdd6f4")

    @property
    def code(self) -> str:
        return self._code


class TroubleCodePanel(QWidget):
    """
    Combined panel for symptom text input and trouble code entry.

    Signals:
        codes_changed: Emitted when the list of codes changes.
                       Carries list[str] of current codes.
        symptoms_parsed: Emitted when symptom text is parsed.
                        Carries ParsedSymptoms object.
    """
    codes_changed = pyqtSignal(list)
    symptoms_parsed = pyqtSignal(object)  # ParsedSymptoms

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self._db_manager = db_manager
        self._codes: list[str] = []
        self._last_parsed: ParsedSymptoms | None = None
        self._parse_timer = QTimer()
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(500)  # Debounce 500ms
        self._parse_timer.timeout.connect(self._on_parse_timer)

        self._setup_ui()
        self._connect_signals()

    def set_db_manager(self, db_manager):
        """Set or update the database manager (for code lookups)."""
        self._db_manager = db_manager

    def _setup_ui(self):
        """Build the combined symptom + code panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # === Symptom Input Section ===
        symptom_header = QLabel("Describe the Problem:")
        symptom_header.setObjectName("sectionHeader")
        main_layout.addWidget(symptom_header)

        self.symptom_input = QTextEdit()
        self.symptom_input.setPlaceholderText(
            'Describe what you hear or feel, e.g.:\n'
            '"Whining noise from the front at highway speed, gets louder when turning"\n'
            '"Knocking sound at idle, worse when cold, started a few days ago"'
        )
        self.symptom_input.setMaximumHeight(80)
        self.symptom_input.setStyleSheet(
            "QTextEdit { background-color: #313244; color: #cdd6f4; "
            "border: 1px solid #585b70; border-radius: 4px; "
            "padding: 6px 10px; font-size: 13px; }"
            "QTextEdit:focus { border-color: #89b4fa; }"
        )
        main_layout.addWidget(self.symptom_input)

        # === Parsed Keywords Row ===
        self._keyword_container = QWidget()
        self._keyword_layout = _FlowLayout(self._keyword_container)
        self._keyword_layout.setContentsMargins(0, 0, 0, 0)
        self._keyword_layout.setSpacing(4)
        self._keyword_container.setVisible(False)
        main_layout.addWidget(self._keyword_container)

        # === Confidence indicator ===
        self.confidence_label = QLabel("")
        self.confidence_label.setStyleSheet(
            "font-size: 11px; color: #a6adc8; font-style: italic; padding: 0 4px;"
        )
        self.confidence_label.setVisible(False)
        main_layout.addWidget(self.confidence_label)

        # === Trouble Code Input Row ===
        code_row = QHBoxLayout()
        code_row.setSpacing(8)

        code_label = QLabel("Trouble Codes:")
        code_label.setObjectName("sectionHeader")
        code_row.addWidget(code_label)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter code (e.g., P0301)")
        self.code_input.setMaxLength(5)
        self.code_input.setMinimumWidth(160)
        self.code_input.setMaximumWidth(200)
        self.code_input.setToolTip(
            "Enter an OBD-II code: P (Powertrain), B (Body), "
            "C (Chassis), or U (Network) followed by 4 digits"
        )
        code_row.addWidget(self.code_input)

        self.add_btn = QPushButton("Add")
        self.add_btn.setMinimumWidth(60)
        code_row.addWidget(self.add_btn)

        sep = QLabel("|")
        sep.setStyleSheet("color: #45475a; font-size: 16px;")
        code_row.addWidget(sep)

        # Active codes display
        self.codes_display = QLabel("No codes entered")
        self.codes_display.setStyleSheet(
            "color: #a6adc8; font-style: italic; padding: 4px 8px;"
        )
        self.codes_display.setWordWrap(True)
        self.codes_display.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        code_row.addWidget(self.codes_display)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setMinimumWidth(80)
        self.clear_btn.setEnabled(False)
        code_row.addWidget(self.clear_btn)

        main_layout.addLayout(code_row)

        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #f38ba8; font-size: 11px;")
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        # === Suggested Codes Row ===
        self._suggested_container = QWidget()
        self._suggested_layout = _FlowLayout(self._suggested_container)
        self._suggested_layout.setContentsMargins(0, 0, 0, 0)
        self._suggested_layout.setSpacing(4)
        self._suggested_container.setVisible(False)

        suggested_wrapper = QHBoxLayout()
        suggested_wrapper.setContentsMargins(0, 0, 0, 0)
        self._suggested_label = QLabel("Suggested:")
        self._suggested_label.setStyleSheet(
            "font-size: 11px; color: #a6adc8; padding-right: 4px;"
        )
        self._suggested_label.setVisible(False)
        suggested_wrapper.addWidget(self._suggested_label)
        suggested_wrapper.addWidget(self._suggested_container)
        suggested_wrapper.addStretch()
        main_layout.addLayout(suggested_wrapper)

        # === Code description display ===
        self.code_desc_label = QLabel("")
        self.code_desc_label.setStyleSheet(
            "font-size: 11px; color: #94e2d5; padding: 2px 8px;"
        )
        self.code_desc_label.setWordWrap(True)
        self.code_desc_label.setVisible(False)
        main_layout.addWidget(self.code_desc_label)

    def _connect_signals(self):
        """Connect UI signals."""
        self.add_btn.clicked.connect(self._add_code)
        self.clear_btn.clicked.connect(self._clear_codes)
        self.code_input.returnPressed.connect(self._add_code)
        self.code_input.textChanged.connect(self._on_code_text_changed)
        self.symptom_input.textChanged.connect(self._on_symptom_text_changed)

    # ---- Symptom parsing ----

    def _on_symptom_text_changed(self):
        """Restart the debounce timer on every keystroke."""
        self._parse_timer.start()

    def _on_parse_timer(self):
        """Actually parse the symptom text after debounce."""
        text = self.symptom_input.toPlainText().strip()
        if not text:
            self._clear_keywords()
            return

        parsed = parse_symptoms(text)
        self._last_parsed = parsed
        self._display_parsed_keywords(parsed)
        self._display_suggested_codes(parsed)
        self.symptoms_parsed.emit(parsed)

    def _display_parsed_keywords(self, parsed: ParsedSymptoms):
        """Show matched keyword chips."""
        # Clear existing chips
        self._clear_layout(self._keyword_layout)

        if not parsed.matched_keywords:
            self._keyword_container.setVisible(False)
            self.confidence_label.setVisible(False)
            return

        # Color mapping for keyword types
        for kw in parsed.matched_keywords:
            color = self._keyword_color(kw)
            chip = KeywordChip(kw, color, self._keyword_container)
            self._keyword_layout.addWidget(chip)

        self._keyword_container.setVisible(True)

        # Show confidence
        conf = parsed.confidence
        if conf >= 0.7:
            color = "#a6e3a1"
            level = "Good match"
        elif conf >= 0.4:
            color = "#f9e2af"
            level = "Partial match"
        else:
            color = "#f38ba8"
            level = "Low match"

        self.confidence_label.setText(
            f"Parse confidence: {conf:.0%} ({level}) - "
            f"{len(parsed.matched_keywords)} keywords matched"
        )
        self.confidence_label.setStyleSheet(
            f"font-size: 11px; color: {color}; font-style: italic; padding: 0 4px;"
        )
        self.confidence_label.setVisible(True)

    def _display_suggested_codes(self, parsed: ParsedSymptoms):
        """Show suggested trouble code chips."""
        self._clear_layout(self._suggested_layout)

        if not parsed.suggested_codes:
            self._suggested_container.setVisible(False)
            self._suggested_label.setVisible(False)
            return

        for code in parsed.suggested_codes:
            desc = self._lookup_code_description(code)
            chip = CodeChip(code, desc, self._suggested_container)
            chip.clicked.connect(self._on_suggested_code_clicked)
            self._suggested_layout.addWidget(chip)

        self._suggested_container.setVisible(True)
        self._suggested_label.setVisible(True)

    def _on_suggested_code_clicked(self, code: str):
        """Add a suggested code to the active codes list."""
        if code.upper() not in self._codes:
            self._codes.append(code.upper())
            self._update_display()
            self.codes_changed.emit(self._codes.copy())

    def _lookup_code_description(self, code: str) -> str:
        """Look up a code description from the database."""
        if self._db_manager is None:
            return ""
        try:
            from database.trouble_code_lookup import lookup_code
            defn = lookup_code(code, self._db_manager)
            return defn.description if defn else ""
        except Exception:
            return ""

    def _keyword_color(self, keyword: str) -> str:
        """Return a color based on keyword type."""
        # Noise character keywords
        if keyword in ("whine", "squeal", "knock_tap", "rattle_buzz",
                       "hum_drone", "click_tick", "grind_scrape", "hiss"):
            return "#f9e2af"
        # Frequency
        if "frequency" in keyword:
            return "#cba6f7"
        # Location
        if keyword in ("front", "rear", "left", "right", "engine_bay",
                       "undercarriage", "exhaust", "dashboard", "wheel_area",
                       "steering", "cabin", "transmission_area",
                       "front_left", "front_right", "rear_left", "rear_right"):
            return "#94e2d5"
        # Default
        return "#89b4fa"

    def _clear_keywords(self):
        """Clear all keyword chips."""
        self._clear_layout(self._keyword_layout)
        self._keyword_container.setVisible(False)
        self.confidence_label.setVisible(False)
        self._clear_layout(self._suggested_layout)
        self._suggested_container.setVisible(False)
        self._suggested_label.setVisible(False)
        self._last_parsed = None

    # ---- Code entry (preserved from original) ----

    def _on_code_text_changed(self, text: str):
        """Auto-capitalize and show code description."""
        upper = text.upper()
        if upper != text:
            self.code_input.blockSignals(True)
            self.code_input.setText(upper)
            self.code_input.blockSignals(False)

        self.validation_label.setVisible(False)

        # Show code description as user types
        if DTC_PATTERN.match(upper):
            desc = self._lookup_code_description(upper)
            if desc:
                self.code_desc_label.setText(f"{upper}: {desc}")
                self.code_desc_label.setVisible(True)
            else:
                self.code_desc_label.setVisible(False)
        else:
            self.code_desc_label.setVisible(False)

    def _add_code(self):
        """Validate and add the entered trouble code."""
        code = self.code_input.text().strip().upper()

        if not code:
            return

        if not DTC_PATTERN.match(code):
            self.validation_label.setText(
                "Invalid format. Use: P/B/C/U + 4 digits (e.g., P0301)"
            )
            self.validation_label.setVisible(True)
            return

        if code in self._codes:
            self.validation_label.setText(f"{code} is already added.")
            self.validation_label.setVisible(True)
            return

        self._codes.append(code)
        self.code_input.clear()
        self.validation_label.setVisible(False)
        self.code_desc_label.setVisible(False)
        self._update_display()
        self.codes_changed.emit(self._codes.copy())

    def _clear_codes(self):
        """Remove all entered codes."""
        self._codes.clear()
        self._update_display()
        self.codes_changed.emit(self._codes.copy())

    def _update_display(self):
        """Update the codes display label."""
        if not self._codes:
            self.codes_display.setText("No codes entered")
            self.codes_display.setStyleSheet(
                "color: #a6adc8; font-style: italic; padding: 4px 8px;"
            )
            self.clear_btn.setEnabled(False)
        else:
            code_tags = []
            for code in self._codes:
                color = CodeChip._get_code_color(code)
                desc = self._lookup_code_description(code)
                tooltip = f" title='{desc}'" if desc else ""
                code_tags.append(
                    f'<span style="background-color: {color}; '
                    f'color: #1e1e2e; padding: 2px 8px; '
                    f'border-radius: 3px; font-weight: bold; '
                    f'font-family: monospace;"{tooltip}>{code}</span>'
                )
            self.codes_display.setText("  ".join(code_tags))
            self.codes_display.setStyleSheet("padding: 4px 8px;")
            self.clear_btn.setEnabled(True)

    # ---- Public API ----

    @property
    def codes(self) -> list[str]:
        """Get the current list of trouble codes."""
        return self._codes.copy()

    @property
    def last_parsed(self) -> ParsedSymptoms | None:
        """Get the most recent parsed symptoms result."""
        return self._last_parsed

    @property
    def symptom_text(self) -> str:
        """Get the raw symptom text."""
        return self.symptom_input.toPlainText().strip()

    def get_merged_context(self) -> BehavioralContext | None:
        """
        Get the BehavioralContext from parsed symptoms.
        Returns None if no symptoms have been parsed.
        """
        if self._last_parsed and self._last_parsed.confidence > 0:
            return self._last_parsed.context
        return None

    def get_parsed_symptoms(self) -> ParsedSymptoms | None:
        """
        Get the full ParsedSymptoms object (includes class_hints,
        confidence, location_hints, matched_keywords, etc.).

        If the user has typed text but the debounce timer hasn't fired yet,
        this forces an immediate parse.
        """
        text = self.symptom_input.toPlainText().strip()
        if text and self._last_parsed is None:
            # Force parse now
            self._last_parsed = parse_symptoms(text)
        return self._last_parsed

    def set_codes(self, codes: list[str]):
        """Set trouble codes programmatically."""
        self._codes = [
            c.strip().upper() for c in codes if DTC_PATTERN.match(c.strip())
        ]
        self._update_display()
        self.codes_changed.emit(self._codes.copy())

    def remove_code(self, code: str):
        """Remove a specific code."""
        code = code.strip().upper()
        if code in self._codes:
            self._codes.remove(code)
            self._update_display()
            self.codes_changed.emit(self._codes.copy())

    # ---- Helpers ----

    @staticmethod
    def _clear_layout(layout):
        """Remove all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


class _FlowLayout(QVBoxLayout):
    """
    Simplified flow layout that wraps widgets horizontally.
    Uses nested QHBoxLayouts to simulate flow wrapping.
    For a full flow layout you'd subclass QLayout, but this is good enough
    for our chip display needs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets: list[QWidget] = []
        self._inner_layout = QHBoxLayout()
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(4)
        super().addLayout(self._inner_layout)
        self._inner_layout.addStretch()

    def addWidget(self, widget):
        """Add a widget before the stretch."""
        self._widgets.append(widget)
        # Insert before the stretch
        self._inner_layout.insertWidget(
            self._inner_layout.count() - 1, widget
        )

    def takeAt(self, index):
        """Remove widget at index."""
        if 0 <= index < len(self._widgets):
            widget = self._widgets.pop(index)
            # Find and remove from inner layout
            for i in range(self._inner_layout.count()):
                item = self._inner_layout.itemAt(i)
                if item and item.widget() == widget:
                    return self._inner_layout.takeAt(i)
        return super().takeAt(index)

    def count(self):
        """Return number of managed widgets."""
        return len(self._widgets)
