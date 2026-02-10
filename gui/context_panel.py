"""
Behavioral Context Panel (v2 -- Expanded)
Structured form for user-observed noise characteristics.
Feeds into the BehavioralContext dataclass for the diagnostic engine.

Layout:
  Row 1: Dependency checkboxes (RPM, speed, load, cold, idle, localized)
  Row 2: Noise character dropdown + perceived frequency dropdown + intermittent
  Row 3: Issue duration + vehicle type + mileage range
  Row 4: Recent maintenance
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel,
    QGroupBox, QComboBox, QFormLayout, QGridLayout,
)
from PyQt6.QtCore import pyqtSignal

from core.feature_extraction import BehavioralContext


class ContextPanel(QWidget):
    """
    Panel with checkboxes and dropdowns for behavioral noise context.
    """

    context_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        group = QGroupBox("Noise Behavior && Vehicle Context")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(12, 8, 12, 8)
        group_layout.setSpacing(6)

        # --- Row 1: Dependency checkboxes ---
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        self.rpm_cb = QCheckBox("RPM dependent")
        self.rpm_cb.setToolTip(
            "Noise changes pitch or volume with engine RPM"
        )
        row1.addWidget(self.rpm_cb)

        self.speed_cb = QCheckBox("Speed dependent")
        self.speed_cb.setToolTip(
            "Noise changes with vehicle speed (not engine RPM)"
        )
        row1.addWidget(self.speed_cb)

        self.load_cb = QCheckBox("Load dependent")
        self.load_cb.setToolTip(
            "Noise changes under acceleration, braking, or steering load"
        )
        row1.addWidget(self.load_cb)

        self.cold_cb = QCheckBox("Cold start only")
        self.cold_cb.setToolTip(
            "Noise only occurs at cold start and goes away when warmed up"
        )
        row1.addWidget(self.cold_cb)

        self.idle_cb = QCheckBox("Occurs at idle")
        self.idle_cb.setToolTip(
            "Noise is present when the engine is idling"
        )
        row1.addWidget(self.idle_cb)

        self.localized_cb = QCheckBox("Localized source")
        self.localized_cb.setToolTip(
            "You can point to a specific physical area where the noise comes from"
        )
        row1.addWidget(self.localized_cb)

        row1.addStretch()
        group_layout.addLayout(row1)

        # --- Row 2: Noise character + frequency + intermittent ---
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        row2.addWidget(QLabel("Noise type:"))
        self.character_combo = QComboBox()
        self.character_combo.addItems([
            "Unknown",
            "Whine",
            "Squeal",
            "Knock / Tap",
            "Rattle / Buzz",
            "Hum / Drone",
            "Click / Tick",
            "Grind / Scrape",
            "Hiss",
        ])
        self.character_combo.setToolTip(
            "Best description of the noise character"
        )
        self.character_combo.setMinimumWidth(130)
        row2.addWidget(self.character_combo)

        row2.addWidget(QLabel("Pitch:"))
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems([
            "Unknown", "Low (rumble)", "Mid (tone)", "High (screech)",
        ])
        self.frequency_combo.setToolTip("Perceived frequency range")
        self.frequency_combo.setMinimumWidth(120)
        row2.addWidget(self.frequency_combo)

        self.intermittent_cb = QCheckBox("Comes && goes")
        self.intermittent_cb.setToolTip(
            "Noise is intermittent rather than constant"
        )
        row2.addWidget(self.intermittent_cb)

        row2.addStretch()
        group_layout.addLayout(row2)

        # --- Row 3: Duration + vehicle type + mileage + maintenance ---
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        row3.addWidget(QLabel("How long:"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems([
            "Unknown", "Just started", "Days", "Weeks", "Months",
        ])
        self.duration_combo.setToolTip("How long the noise has been present")
        self.duration_combo.setMinimumWidth(100)
        row3.addWidget(self.duration_combo)

        row3.addWidget(QLabel("Vehicle:"))
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItems([
            "Unknown", "Sedan", "SUV / Truck", "Sports car",
            "Diesel", "Hybrid / EV",
        ])
        self.vehicle_combo.setToolTip("Vehicle type")
        self.vehicle_combo.setMinimumWidth(100)
        row3.addWidget(self.vehicle_combo)

        row3.addWidget(QLabel("Mileage:"))
        self.mileage_combo = QComboBox()
        self.mileage_combo.addItems([
            "Unknown", "Under 50k", "50k - 100k",
            "100k - 150k", "Over 150k",
        ])
        self.mileage_combo.setToolTip("Approximate vehicle mileage")
        self.mileage_combo.setMinimumWidth(100)
        row3.addWidget(self.mileage_combo)

        row3.addWidget(QLabel("Recent work:"))
        self.maintenance_combo = QComboBox()
        self.maintenance_combo.addItems([
            "Unknown", "None", "Oil change", "Belt replacement",
            "Brake work", "Suspension work",
        ])
        self.maintenance_combo.setToolTip(
            "Most recent maintenance that may be related"
        )
        self.maintenance_combo.setMinimumWidth(120)
        row3.addWidget(self.maintenance_combo)

        row3.addStretch()
        group_layout.addLayout(row3)

        outer.addWidget(group)

    def _connect_signals(self):
        # Checkboxes
        for cb in [
            self.rpm_cb, self.speed_cb, self.load_cb,
            self.cold_cb, self.idle_cb, self.localized_cb,
            self.intermittent_cb,
        ]:
            cb.toggled.connect(lambda _: self.context_changed.emit())

        # Combos
        for combo in [
            self.character_combo, self.frequency_combo,
            self.duration_combo, self.vehicle_combo,
            self.mileage_combo, self.maintenance_combo,
        ]:
            combo.currentIndexChanged.connect(
                lambda _: self.context_changed.emit()
            )

    # ------------------------------------------------------------------
    # Mapping helpers: display text <-> BehavioralContext string values
    # ------------------------------------------------------------------

    _CHARACTER_MAP = {
        "Unknown": "unknown",
        "Whine": "whine",
        "Squeal": "squeal",
        "Knock / Tap": "knock_tap",
        "Rattle / Buzz": "rattle_buzz",
        "Hum / Drone": "hum_drone",
        "Click / Tick": "click_tick",
        "Grind / Scrape": "grind_scrape",
        "Hiss": "hiss",
    }

    _FREQUENCY_MAP = {
        "Unknown": "unknown",
        "Low (rumble)": "low",
        "Mid (tone)": "mid",
        "High (screech)": "high",
    }

    _DURATION_MAP = {
        "Unknown": "unknown",
        "Just started": "just_started",
        "Days": "days",
        "Weeks": "weeks",
        "Months": "months",
    }

    _VEHICLE_MAP = {
        "Unknown": "unknown",
        "Sedan": "sedan",
        "SUV / Truck": "suv_truck",
        "Sports car": "sports",
        "Diesel": "diesel",
        "Hybrid / EV": "hybrid_ev",
    }

    _MILEAGE_MAP = {
        "Unknown": "unknown",
        "Under 50k": "under_50k",
        "50k - 100k": "50k_100k",
        "100k - 150k": "100k_150k",
        "Over 150k": "over_150k",
    }

    _MAINTENANCE_MAP = {
        "Unknown": "unknown",
        "None": "none",
        "Oil change": "oil_change",
        "Belt replacement": "belt_replacement",
        "Brake work": "brake_work",
        "Suspension work": "suspension_work",
    }

    def get_context(self) -> BehavioralContext:
        """Return the current behavioral context from all form controls."""
        return BehavioralContext(
            rpm_dependency=self.rpm_cb.isChecked(),
            speed_dependency=self.speed_cb.isChecked(),
            load_dependency=self.load_cb.isChecked(),
            cold_only=self.cold_cb.isChecked(),
            occurs_at_idle=self.idle_cb.isChecked(),
            mechanical_localization=self.localized_cb.isChecked(),
            noise_character=self._CHARACTER_MAP.get(
                self.character_combo.currentText(), "unknown"
            ),
            perceived_frequency=self._FREQUENCY_MAP.get(
                self.frequency_combo.currentText(), "unknown"
            ),
            intermittent=self.intermittent_cb.isChecked(),
            issue_duration=self._DURATION_MAP.get(
                self.duration_combo.currentText(), "unknown"
            ),
            vehicle_type=self._VEHICLE_MAP.get(
                self.vehicle_combo.currentText(), "unknown"
            ),
            mileage_range=self._MILEAGE_MAP.get(
                self.mileage_combo.currentText(), "unknown"
            ),
            recent_maintenance=self._MAINTENANCE_MAP.get(
                self.maintenance_combo.currentText(), "unknown"
            ),
        )

    def set_context(self, ctx: BehavioralContext):
        """Set all form controls from a BehavioralContext."""
        self.rpm_cb.setChecked(ctx.rpm_dependency)
        self.speed_cb.setChecked(ctx.speed_dependency)
        self.load_cb.setChecked(ctx.load_dependency)
        self.cold_cb.setChecked(ctx.cold_only)
        self.idle_cb.setChecked(ctx.occurs_at_idle)
        self.localized_cb.setChecked(ctx.mechanical_localization)
        self.intermittent_cb.setChecked(ctx.intermittent)

        # Reverse-lookup for combos
        for display, value in self._CHARACTER_MAP.items():
            if value == ctx.noise_character:
                self.character_combo.setCurrentText(display)
                break

        for display, value in self._FREQUENCY_MAP.items():
            if value == ctx.perceived_frequency:
                self.frequency_combo.setCurrentText(display)
                break

        for display, value in self._DURATION_MAP.items():
            if value == ctx.issue_duration:
                self.duration_combo.setCurrentText(display)
                break

        for display, value in self._VEHICLE_MAP.items():
            if value == ctx.vehicle_type:
                self.vehicle_combo.setCurrentText(display)
                break

        for display, value in self._MILEAGE_MAP.items():
            if value == ctx.mileage_range:
                self.mileage_combo.setCurrentText(display)
                break

        for display, value in self._MAINTENANCE_MAP.items():
            if value == ctx.recent_maintenance:
                self.maintenance_combo.setCurrentText(display)
                break

    def reset(self):
        """Reset all controls to defaults."""
        for cb in [
            self.rpm_cb, self.speed_cb, self.load_cb,
            self.cold_cb, self.idle_cb, self.localized_cb,
            self.intermittent_cb,
        ]:
            cb.setChecked(False)

        for combo in [
            self.character_combo, self.frequency_combo,
            self.duration_combo, self.vehicle_combo,
            self.mileage_combo, self.maintenance_combo,
        ]:
            combo.setCurrentIndex(0)
