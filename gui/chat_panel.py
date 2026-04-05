"""
Chat Panel for ASE Mechanic Agent
A scrollable chat interface with message bubbles, typing indicator,
inline code/diagnosis references, quick-action chips, and mode toggle
between keyword-only and full agent modes.
"""

import re
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QScrollArea, QFrame, QSizePolicy, QComboBox,
    QApplication,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QThread
from PyQt6.QtGui import QFont, QTextCursor


# ---------------------------------------------------------------------------
# Agent worker thread
# ---------------------------------------------------------------------------

class AgentWorker(QThread):
    """Runs the mechanic agent chat in a background thread."""
    response_ready = pyqtSignal(str)
    tool_called = pyqtSignal(str, dict)  # tool_name, args
    error_occurred = pyqtSignal(str)

    def __init__(self, agent, message: str, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._message = message

    def run(self):
        try:
            response = self._agent.chat(
                self._message,
                on_tool_call=lambda name, args: self.tool_called.emit(name, args),
            )
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ---------------------------------------------------------------------------
# Message bubble
# ---------------------------------------------------------------------------

class MessageBubble(QFrame):
    """A single chat message bubble."""

    def __init__(
        self,
        text: str,
        is_user: bool = True,
        timestamp: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._is_user = is_user

        # Styling
        if is_user:
            bg_color = "#45475a"
            align = Qt.AlignmentFlag.AlignRight
            margin = "margin-left: 60px;"
            border_radius = "border-radius: 12px 12px 2px 12px;"
        else:
            bg_color = "#313244"
            align = Qt.AlignmentFlag.AlignLeft
            margin = "margin-right: 60px;"
            border_radius = "border-radius: 12px 12px 12px 2px;"

        self.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; "
            f"{border_radius} {margin} padding: 8px 12px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Sender label
        sender = "You" if is_user else "DiagBot (ASE Mechanic)"
        sender_label = QLabel(sender)
        sender_color = "#89b4fa" if not is_user else "#a6adc8"
        sender_label.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {sender_color}; "
            f"background: transparent; padding: 0;"
        )
        layout.addWidget(sender_label)

        # Message content (supports basic markdown-style formatting)
        content_label = QLabel(self._format_text(text))
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setStyleSheet(
            "color: #cdd6f4; background: transparent; "
            "font-size: 13px; padding: 0;"
        )
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(content_label)

        # Timestamp
        if not timestamp:
            timestamp = datetime.now().strftime("%I:%M %p")
        ts_label = QLabel(timestamp)
        ts_label.setStyleSheet(
            "font-size: 9px; color: #585b70; background: transparent; padding: 0;"
        )
        ts_label.setAlignment(align)
        layout.addWidget(ts_label)

    @staticmethod
    def _format_text(text: str) -> str:
        """Convert basic markdown to HTML for display."""
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # Inline code
        text = re.sub(r"`(.+?)`", r'<code style="background: #45475a; padding: 1px 4px; border-radius: 3px;">\1</code>', text)
        # Bullet points
        text = re.sub(r"^- ", "&#8226; ", text, flags=re.MULTILINE)
        # Newlines
        text = text.replace("\n", "<br>")
        return text


class TypingIndicator(QFrame):
    """Animated typing indicator (three dots)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #313244; border-radius: 12px; "
            "margin-right: 60px; padding: 8px 16px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._dots = []
        for _ in range(3):
            dot = QLabel(".")
            dot.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #89b4fa; "
                "background: transparent; padding: 0;"
            )
            layout.addWidget(dot)
            self._dots.append(dot)

        layout.addStretch()

        # Animation timer
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._animate)

    def start(self):
        self._tick = 0
        self._timer.start()
        self.setVisible(True)

    def stop(self):
        self._timer.stop()
        self.setVisible(False)

    def _animate(self):
        for i, dot in enumerate(self._dots):
            if i == self._tick % 3:
                dot.setStyleSheet(
                    "font-size: 20px; font-weight: bold; color: #89b4fa; "
                    "background: transparent; padding: 0;"
                )
            else:
                dot.setStyleSheet(
                    "font-size: 20px; font-weight: bold; color: #585b70; "
                    "background: transparent; padding: 0;"
                )
        self._tick += 1


# ---------------------------------------------------------------------------
# Quick-action chips
# ---------------------------------------------------------------------------

class QuickActionChip(QPushButton):
    """A pre-defined quick action the user can click."""

    action_clicked = pyqtSignal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QPushButton { background-color: #313244; color: #89b4fa; "
            "border: 1px solid #585b70; border-radius: 14px; "
            "padding: 4px 12px; font-size: 11px; min-height: 0; }"
            "QPushButton:hover { background-color: #45475a; "
            "border-color: #89b4fa; }"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: self.action_clicked.emit(text))


# ---------------------------------------------------------------------------
# Main Chat Panel
# ---------------------------------------------------------------------------

class ChatPanel(QWidget):
    """
    Full chat interface for the ASE Mechanic Agent.

    Signals:
        message_sent: Emitted when user sends a message (str).
    """
    message_sent = pyqtSignal(str)

    # Quick action suggestions
    QUICK_ACTIONS = [
        "What does this noise mean?",
        "What should I check first?",
        "Is this safe to drive?",
        "How much will this cost to fix?",
        "Any recalls for my vehicle?",
    ]

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self._db_manager = db_manager
        self._agent = None
        self._worker = None

        self._setup_ui()
        self._connect_signals()

    def set_agent(self, agent):
        """Set the mechanic agent instance."""
        self._agent = agent
        self._update_mode_status()

    def _setup_ui(self):
        """Build the chat panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # --- Header with mode toggle ---
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("DiagBot")
        title.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #89b4fa; padding: 0;"
        )
        header.addWidget(title)

        subtitle = QLabel("ASE Certified Mechanic")
        subtitle.setStyleSheet(
            "font-size: 11px; color: #a6adc8; font-style: italic; padding-top: 2px;"
        )
        header.addWidget(subtitle)

        header.addStretch()

        # Mode toggle
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Keyword Only", "Full Agent"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip(
            "Keyword Only: No LLM required, uses symptom parser\n"
            "Full Agent: Uses LLM with tool-calling (requires API key)"
        )
        self.mode_combo.setMaximumWidth(140)
        header.addWidget(QLabel("Mode:"))
        header.addWidget(self.mode_combo)

        # Status indicator
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f38ba8; font-size: 12px;")
        self.status_dot.setToolTip("Agent not configured")
        header.addWidget(self.status_dot)

        main_layout.addLayout(header)

        # --- Scrollable message area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #45475a; border-radius: 8px; "
            "background-color: #181825; }"
        )

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()  # Push messages to bottom

        self.scroll_area.setWidget(self.messages_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # --- Typing indicator ---
        self.typing_indicator = TypingIndicator()
        self.typing_indicator.setVisible(False)
        main_layout.addWidget(self.typing_indicator)

        # --- Quick actions ---
        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)
        self._quick_chips = []
        for action_text in self.QUICK_ACTIONS:
            chip = QuickActionChip(action_text)
            chip.action_clicked.connect(self._on_quick_action)
            quick_row.addWidget(chip)
            self._quick_chips.append(chip)
        quick_row.addStretch()
        main_layout.addLayout(quick_row)

        # --- Input area ---
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(
            "Ask DiagBot about your car problem..."
        )
        self.input_box.setMaximumHeight(60)
        self.input_box.setStyleSheet(
            "QTextEdit { background-color: #313244; color: #cdd6f4; "
            "border: 1px solid #585b70; border-radius: 8px; "
            "padding: 8px; font-size: 13px; }"
            "QTextEdit:focus { border-color: #89b4fa; }"
        )
        input_row.addWidget(self.input_box)

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setMinimumWidth(70)
        self.send_btn.setStyleSheet(
            "QPushButton { background-color: #89b4fa; color: #1e1e2e; "
            "border-radius: 8px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #b4d0fb; }"
            "QPushButton:disabled { background-color: #45475a; color: #585b70; }"
        )
        input_row.addWidget(self.send_btn)

        main_layout.addLayout(input_row)

        # --- Add welcome message ---
        self._add_bot_message(
            "Hey there! I'm DiagBot, your virtual ASE Certified Mechanic. "
            "I can help you diagnose car problems based on sounds, symptoms, "
            "and trouble codes.\n\n"
            "**Tell me what's going on with your vehicle**, or click one of "
            "the quick actions below to get started."
        )

    def _connect_signals(self):
        """Connect signals."""
        self.send_btn.clicked.connect(self._on_send)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

    def _on_send(self):
        """Handle send button click."""
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        self.input_box.clear()
        self._add_user_message(text)
        self._process_message(text)

    def _on_quick_action(self, action_text: str):
        """Handle quick action chip click."""
        self._add_user_message(action_text)
        self._process_message(action_text)

    def _on_mode_changed(self, mode_text: str):
        """Handle mode toggle change."""
        self._update_mode_status()

    def _process_message(self, text: str):
        """Process a user message through the appropriate mode."""
        mode = self.mode_combo.currentText()

        if mode == "Full Agent" and self._agent and self._agent.is_available:
            # Full LLM agent mode
            self.send_btn.setEnabled(False)
            self.typing_indicator.start()

            self._worker = AgentWorker(self._agent, text)
            self._worker.response_ready.connect(self._on_agent_response)
            self._worker.tool_called.connect(self._on_tool_called)
            self._worker.error_occurred.connect(self._on_agent_error)
            self._worker.start()
        else:
            # Keyword-only mode (uses symptom parser)
            self._keyword_mode_response(text)

    def _keyword_mode_response(self, text: str):
        """Generate a response using only the symptom parser (no LLM)."""
        from core.symptom_parser import parse_symptoms

        parsed = parse_symptoms(text)

        lines = []

        if parsed.matched_keywords:
            lines.append(
                f"I picked up these key details from your description: "
                f"**{', '.join(parsed.matched_keywords)}**"
            )

            if parsed.context.noise_character != "unknown":
                char_display = parsed.context.noise_character.replace("_", " ").title()
                lines.append(f"\n**Noise type:** {char_display}")

            if parsed.class_hints:
                sorted_hints = sorted(
                    parsed.class_hints.items(), key=lambda x: x[1], reverse=True
                )
                from core.diagnostic_engine import CLASS_DISPLAY_NAMES
                top = sorted_hints[0]
                display = CLASS_DISPLAY_NAMES.get(top[0], top[0])
                lines.append(f"**Most likely category:** {display}")

                if len(sorted_hints) > 1:
                    second = sorted_hints[1]
                    display2 = CLASS_DISPLAY_NAMES.get(second[0], second[0])
                    lines.append(f"**Also consider:** {display2}")

            if parsed.location_hints:
                lines.append(
                    f"**Location:** {', '.join(parsed.location_hints)}"
                )

            if parsed.suggested_codes:
                lines.append(
                    f"\n**Related trouble codes:** {', '.join(parsed.suggested_codes)}"
                )

            lines.append(
                "\n*For more detailed diagnosis, try recording the sound "
                "and running the audio analyzer, or switch to Full Agent mode.*"
            )
        else:
            lines.append(
                "I wasn't able to identify specific symptoms from your "
                "description. Could you try describing:\n"
                "- **What it sounds like** (whine, knock, rattle, squeal, etc.)\n"
                "- **When it happens** (at idle, at speed, when turning, etc.)\n"
                "- **Where it comes from** (front, rear, engine bay, etc.)"
            )

        # Check for trouble codes in the message
        code_pattern = re.compile(r"\b[PBCU][0-9A-Fa-f]{4}\b", re.IGNORECASE)
        found_codes = code_pattern.findall(text)

        if found_codes and self._db_manager:
            lines.append("\n**Trouble Code Info:**")
            try:
                from database.trouble_code_lookup import lookup_codes
                definitions = lookup_codes(found_codes, self._db_manager)
                for defn in definitions:
                    lines.append(
                        f"- **{defn.code}**: {defn.description} "
                        f"(Severity: {defn.severity})"
                    )
            except Exception:
                pass

        self._add_bot_message("\n".join(lines))

    def _on_agent_response(self, response: str):
        """Handle agent response from worker thread."""
        self.typing_indicator.stop()
        self.send_btn.setEnabled(True)
        self._add_bot_message(response)

    def _on_tool_called(self, tool_name: str, args: dict):
        """Show a subtle indicator when the agent uses a tool."""
        tool_display = {
            "lookup_trouble_code": f"Looking up code {args.get('code', '')}...",
            "search_web": f"Searching: {args.get('query', '')[:50]}...",
            "get_diagnosis_results": "Checking audio analysis results...",
            "search_knowledge_base": f"Checking knowledge base...",
        }
        display = tool_display.get(tool_name, f"Using {tool_name}...")

        # Add a subtle system message
        self._add_system_message(display)

    def _on_agent_error(self, error: str):
        """Handle agent error."""
        self.typing_indicator.stop()
        self.send_btn.setEnabled(True)
        self._add_bot_message(
            f"I encountered an issue: {error}\n\n"
            "You can try again, or switch to Keyword Only mode."
        )

    # ---- Message display helpers ----

    def _add_user_message(self, text: str):
        """Add a user message bubble."""
        bubble = MessageBubble(text, is_user=True)
        self._insert_message(bubble)

    def _add_bot_message(self, text: str):
        """Add a bot message bubble."""
        bubble = MessageBubble(text, is_user=False)
        self._insert_message(bubble)

    def _add_system_message(self, text: str):
        """Add a subtle system/status message."""
        label = QLabel(text)
        label.setStyleSheet(
            "font-size: 10px; color: #585b70; font-style: italic; "
            "padding: 2px 8px; background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._insert_message(label)

    def _insert_message(self, widget):
        """Insert a widget before the stretch at the bottom."""
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, widget)

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll the message area to the bottom."""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_mode_status(self):
        """Update the status indicator based on mode and agent availability."""
        mode = self.mode_combo.currentText()

        if mode == "Full Agent":
            if self._agent and self._agent.is_available:
                self.status_dot.setStyleSheet("color: #a6e3a1; font-size: 12px;")
                self.status_dot.setToolTip("Agent connected")
            else:
                self.status_dot.setStyleSheet("color: #f38ba8; font-size: 12px;")
                self.status_dot.setToolTip(
                    "No LLM configured. Set OPENAI_API_KEY, "
                    "ANTHROPIC_API_KEY, or configure Ollama."
                )
        else:
            self.status_dot.setStyleSheet("color: #a6e3a1; font-size: 12px;")
            self.status_dot.setToolTip("Keyword mode (no LLM required)")

    def clear_chat(self):
        """Clear all messages and reset conversation."""
        # Remove all message widgets
        while self.messages_layout.count() > 1:  # Keep the stretch
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if self._agent:
            self._agent.reset_conversation()

        # Re-add welcome message
        self._add_bot_message(
            "Chat cleared. How can I help you with your vehicle?"
        )
