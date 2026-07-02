"""Spotlight prompt box (frosted) and toast-style step cards (bottom-right).

The prompt box keeps the native acrylic frost. The step cards deliberately do
NOT: native blur always fills a window's rectangular bounds, so on a small
rounded chip the square blur edge pokes out past the corners (region masks
can clip it but aren't anti-aliased — chunky corners either way). Instead each
card is a solid shadcn-toast-style surface painted manually in paintEvent with
one anti-aliased rounded rect. Entrance fade uses the native windowOpacity
property rather than QGraphicsOpacityEffect — the effect rasterizes the whole
translucent window through an offscreen buffer, which is a known source of
paint glitches (and the QPainter warning spam we hit earlier with nested
effects).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPointF,
    QPropertyAnimation, Qt, QThread, QTimer, Signal,
)
from PySide6.QtGui import (
    QColor, QKeyEvent, QKeySequence, QPainter, QPalette, QPen,
    QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from ..agent.base import split_icon
from ..agent.factory import create_agent
from ..config import load_config, update_provider
from ..resources import app_pixmap
from ..webconfig import settings_url
from . import icons, styles
from .blur import enable_blur, round_corners
from .winfocus import force_foreground

# Icon + accent color per step kind (action/thought/status/result/error).
KIND_COLOR = {
    "action": QColor(59, 130, 246),
    "thought": QColor(212, 212, 216),
    "status": QColor(161, 161, 170),
    "result": QColor(34, 197, 94),
    "error": QColor(239, 68, 68),
    "reply": QColor(228, 228, 231),   # neutral — a chat answer, not a task "done"
}


# --------------------------------------------------------------------------
# Worker thread: runs the agent loop off the UI thread.
# --------------------------------------------------------------------------
class AgentWorker(QThread):
    event = Signal(str, str)         # (kind, text) — intermediate steps
    finished_ok = Signal(str, str)   # (kind, text) — final: reply/result/status
    failed = Signal(str)

    def __init__(self, make_agent, instruction: str):
        # `make_agent` is a zero-arg callable run INSIDE this thread. Agent
        # construction pulls in the provider SDK (google.genai / anthropic),
        # whose first import alone can block for a second or two — doing it
        # here keeps the UI thread free so the status cards appear instantly
        # when the user presses Enter.
        super().__init__()
        self.make_agent = make_agent
        self.instruction = instruction
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            agent = self.make_agent()
        except Exception as e:
            self.failed.emit(str(e))
            return
        if self._stop:
            self.finished_ok.emit("status", "Stopped.")
            return
        try:
            kind, text = agent.run(
                self.instruction,
                emit=lambda kind, text: self.event.emit(kind, text),
                should_stop=lambda: self._stop,
            )
            self.finished_ok.emit(kind, text)
        except Exception as e:  # pragma: no cover
            self.failed.emit(str(e))


def _search_icon(size: int = 20, color: QColor = QColor(212, 212, 216)) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color)
    pen.setWidthF(1.7)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    r = size * 0.30
    cx, cy = size * 0.42, size * 0.42
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.drawLine(QPointF(cx + r * 0.72, cy + r * 0.72),
               QPointF(size * 0.86, size * 0.86))
    p.end()
    return pm


# --------------------------------------------------------------------------
# One step = one independent floating card, frosted to match the Spotlight box.
# --------------------------------------------------------------------------
class StepCard(QWidget):
    def __init__(self, kind: str, text: str, width: int):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_StyledBackground, True)  # let QSS paint this widget
        self.setObjectName("stepCard")
        self.setStyleSheet(styles.STEP_QSS)
        self._w = width
        self.setFixedWidth(width)
        self.setWindowOpacity(0.0)  # entrance fade animates this up to 1
        self._pos_anim: QPropertyAnimation | None = None

        icon_key, display_text = split_icon(kind, text)
        accent = KIND_COLOR.get(kind, QColor(161, 161, 170))

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 12, 14, 12)
        row.setSpacing(11)

        badge = QFrame()
        badge.setObjectName("iconBadge")
        badge.setProperty("kind", kind)
        badge.setFixedSize(26, 26)
        badge_lay = QHBoxLayout(badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(icons.icon(icon_key, 15, accent))
        badge_lay.addWidget(icon_label, 0, Qt.AlignCenter)

        label = QLabel(display_text)
        label.setObjectName("stepText")
        label.setWordWrap(True)
        self._label = label

        row.addWidget(badge, 0, Qt.AlignVCenter)
        row.addWidget(label, 1, Qt.AlignVCenter)

    def apply_blur(self):
        """Exactly the Spotlight box's frosting: acrylic backdrop + DWM rounded
        corners (the rounding is what keeps the acrylic from spilling past the
        rounded QSS fill as a square edge)."""
        try:
            hwnd = int(self.winId())
            ok = enable_blur(hwnd)
            round_corners(hwnd)
            self.setProperty("blur", "true" if ok else "false")
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception:
            pass

    # row margins/badge/spacing (must match the layout above) — used to derive
    # the exact width the wrapped text gets, so the measured height is correct.
    _M_L, _M_R, _BADGE, _SPACING = 12, 14, 26, 11

    def measure(self, max_height: int | None = None) -> int:
        """Return the card's height for its fixed width, capped to max_height.

        A word-wrapped QLabel's height depends on the width it wraps at. If we
        don't pin that width, sizeHint() can under-report the height for a long
        message — the card then gets bottom-anchored by a too-small height and
        its real (taller) content spills below the screen edge. Pinning the
        label to the exact text-column width makes heightForWidth accurate.
        """
        self.setFixedWidth(self._w)
        text_col = self._w - (self._M_L + self._M_R + self._BADGE + self._SPACING)
        self._label.setFixedWidth(text_col)
        self.ensurePolished()
        self.layout().activate()
        h = self.sizeHint().height()
        if max_height is not None and h > max_height:
            h = max_height  # never let one card be taller than the screen
        return h


# --------------------------------------------------------------------------
# Step manager: positions independent StepCard windows bottom-right, stacked
# bottom-up with a gap between them. Not a window itself — just bookkeeping.
# --------------------------------------------------------------------------
class StatusStack(QObject):
    MAX = 6
    MARGIN = 20
    GAP = 8
    CARD_W = 372

    def __init__(self):
        super().__init__()
        self.cards: list[StepCard] = []
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self._hide_all)

    # -- public API ---------------------------------------------------------
    def start(self, prompt: str):
        self._hide.stop()
        self._clear()
        self.append("status", f"“{prompt}”")

    def append(self, kind: str, text: str):
        card = StepCard(kind, text, self.CARD_W)
        # Show it first (still invisible: windowOpacity is 0 until the fade
        # starts) so Qt fully resolves stylesheet metrics and word-wrap
        # heightForWidth before we measure — measuring an unshown top-level
        # widget sometimes returned an under-resolved height, which threw off
        # the next card's stacked position as an inconsistent gap.
        card.show()
        card.apply_blur()
        # Cap a single card to the usable screen height so a huge message
        # (e.g. a long API error) can never overflow past the top or bottom.
        avail = QApplication.primaryScreen().availableGeometry().height()
        h = card.measure(max_height=avail - 2 * self.MARGIN)
        card.resize(self.CARD_W, h)

        self.cards.append(card)
        self._trim()

        targets = self._compute_targets()
        new_x, new_y = targets[card]
        card.move(new_x, new_y + 12)  # entrance offset, slides up into place

        # Native window opacity: composited by the window manager, no
        # QGraphicsOpacityEffect offscreen-buffer glitches. Never re-targeted
        # after start, so DeleteWhenStopped is safe here (no stored reference).
        fade = QPropertyAnimation(card, b"windowOpacity", self)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setDuration(220)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        for c, (tx, ty) in targets.items():
            self._animate_to(c, tx, ty)
            c.raise_()

    def finish(self, kind: str, text: str):
        self.append(kind, text)
        self._hide.start(7000)

    def dismiss_later(self, ms: int = 3000):
        """Fade the panel out soon without adding a final card."""
        self._hide.start(ms)

    # -- internals ----------------------------------------------------------
    def _animate_to(self, card: "StepCard", x: int, y: int):
        """Animate `card` to (x, y), replacing any animation already in
        flight for it. Every append() re-targets ALL cards (older ones may
        need to shift up to make room for the new one); without stopping a
        still-running previous animation first, the old one keeps overwriting
        `pos` on each tick and fights this new target — the card would settle
        at an unpredictable spot, which showed up as inconsistent gaps."""
        if card._pos_anim is not None:
            # DeletionPolicy.DeleteWhenStopped would auto-delete the C++
            # object once it finishes naturally — leaving card._pos_anim a
            # dangling reference that crashes the next .stop() call here. Keep
            # the object alive (default policy) and clean it up ourselves.
            card._pos_anim.stop()
            card._pos_anim.deleteLater()
        anim = QPropertyAnimation(card, b"pos", self)
        anim.setStartValue(card.pos())
        anim.setEndValue(QPoint(x, y))
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        card._pos_anim = anim
        anim.start()

    def _compute_targets(self) -> dict:
        g = QApplication.primaryScreen().availableGeometry()
        x = g.right() - self.CARD_W - self.MARGIN
        y = g.bottom() - self.MARGIN
        targets = {}
        for card in reversed(self.cards):  # newest at the bottom
            y -= card.height()
            targets[card] = (x, y)
            y -= self.GAP
        return targets

    def _trim(self):
        while len(self.cards) > self.MAX:
            old = self.cards.pop(0)
            if old._pos_anim is not None:
                old._pos_anim.stop()
            old.close()
            old.deleteLater()

    def _clear(self):
        for c in self.cards:
            if c._pos_anim is not None:
                c._pos_anim.stop()
            c.close()
            c.deleteLater()
        self.cards.clear()

    def _hide_all(self):
        for c in self.cards:
            fade = QPropertyAnimation(c, b"windowOpacity", self)
            fade.setStartValue(c.windowOpacity())
            fade.setEndValue(0.0)
            fade.setDuration(280)
            fade.setEasingCurve(QEasingCurve.InCubic)
            fade.finished.connect(c.hide)
            fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# --------------------------------------------------------------------------
# Spotlight prompt window — the window IS the card (one container, blurred
# and masked to its own rounded shape).
# --------------------------------------------------------------------------
class SpotlightWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._agent = None
        self.worker: AgentWorker | None = None
        self.stack = StatusStack()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_StyledBackground, True)  # let QSS paint *this* widget
        self.setObjectName("card")
        self.setFixedWidth(600)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 14)
        lay.setSpacing(14)

        # row 1: app logo + input
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        icon = QLabel()
        logo = app_pixmap(22)               # assets/main_icon.png
        icon.setPixmap(logo if not logo.isNull() else _search_icon(20))
        icon.setFixedSize(24, 26)
        icon.setAlignment(Qt.AlignVCenter)
        self.prompt = QLineEdit()
        self.prompt.setObjectName("prompt")
        self.prompt.setPlaceholderText("Tell your PC what to do…")
        self.prompt.returnPressed.connect(self.submit)
        pal = self.prompt.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(255, 255, 255, 140))
        self.prompt.setPalette(pal)
        row1.addWidget(icon)
        row1.addWidget(self.prompt)

        # separator
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)

        # row 2: command hint (left) + key hints (right) — plain text, no icons
        row2 = QHBoxLayout()
        self.model_hint = QLabel("/settings to setup models · /model to switch")
        self.model_hint.setObjectName("hint")
        key_hint = QLabel("Enter to send    Esc to hide")
        key_hint.setObjectName("hint")
        row2.addWidget(self.model_hint, 0, Qt.AlignLeft)
        row2.addStretch(1)
        row2.addWidget(key_hint, 0, Qt.AlignRight)

        lay.addLayout(row1)
        lay.addWidget(sep)
        lay.addLayout(row2)

        self.setStyleSheet(styles.SPOTLIGHT_QSS)

        # Esc hides the box. A window-scoped QShortcut fires no matter which
        # child has focus — relying on keyPressEvent alone missed it because
        # the focused QLineEdit consumes the key first.
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.WindowShortcut)
        esc.activated.connect(self.hide)

    # -- config / agent -----------------------------------------------------
    def reload_config(self, config):
        self.config = config
        self._agent = None

    def _ensure_agent(self):
        if self._agent is None:
            self._agent = create_agent(self.config)
        return self._agent

    # -- show / hide --------------------------------------------------------
    def show_centered(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        x = screen.center().x() - self.width() // 2
        y = int(screen.top() + screen.height() * 0.26)
        self.move(x, y)
        self.show()
        self.raise_()
        self._apply_blur()
        self._take_focus()
        # Re-assert once the event loop has processed the show — the first grab
        # can land before the window is fully mapped/active, in which case Qt
        # silently keeps focus on the previously-active app.
        QTimer.singleShot(60, self._take_focus)

    def _take_focus(self):
        # Steal foreground focus from the app that had it when the hotkey fired,
        # otherwise typing goes to that app and Esc/click-away don't work.
        if not self.isVisible():
            return
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.prompt.setFocus()
        self.prompt.selectAll()

    def _apply_blur(self):
        try:
            hwnd = int(self.winId())
            ok = enable_blur(hwnd)
            round_corners(hwnd)
            self.setProperty("blur", "true" if ok else "false")
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception:
            pass

    def toggle(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.stack.append("status", "Cancelling…")
            return
        if self.isVisible():
            self.hide()
        else:
            self.show_centered()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def event(self, e):
        # Click-away to dismiss: when the box loses window activation (the user
        # clicked another window/the desktop), hide it — like macOS Spotlight.
        # The status stack is a separate, non-activating window, so showing it
        # doesn't deactivate this one.
        if e.type() == QEvent.Type.WindowDeactivate and self.isVisible():
            self.hide()
        return super().event(e)

    # -- run ----------------------------------------------------------------
    def submit(self):
        text = self.prompt.text().strip()
        if not text:
            return
        if self.worker and self.worker.isRunning():
            return
        cmd = text.lower()
        if cmd in ("/settings", "/set", "/config"):
            self._open_settings()
            return
        if cmd.startswith("/model"):
            self._handle_model_command(text)
            return

        # Pick up any keys/provider just saved in the settings page without
        # needing a restart (reload is cheap; it also resets the cached agent).
        self.reload_config(load_config())

        # Instant feedback first: hide the box and show the prompt card before
        # any agent/SDK work happens. Building the agent is deferred into the
        # worker thread (see AgentWorker) — its first run imports the provider
        # SDK, which used to block right here and made Enter feel stuck.
        self.prompt.clear()
        self.hide()  # get out of the agent's way — it drives the real screen
        self.stack.start(text)

        self.worker = AgentWorker(self._ensure_agent, text)
        self.worker.event.connect(self.stack.append)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(lambda e: self.stack.finish("error", e))
        self.worker.start()

    def _on_finished(self, kind: str, text: str):
        # kind is 'reply' (conversational answer), 'result' (task done via the
        # done() tool), or 'status' (cancelled). Show whatever text there is;
        # if there's nothing to say, just let the panel fade out — no filler
        # "Done." card for a plain reply.
        if text and text.strip():
            self.stack.finish(kind, text)
        else:
            self.stack.dismiss_later()

    def _open_settings(self):
        """Open the local settings web UI (API keys) in the default browser."""
        import webbrowser
        self.prompt.clear()
        self.hide()
        try:
            webbrowser.open(settings_url())
        except Exception:
            pass

    def _handle_model_command(self, text: str):
        """Handle `/model`, `/model <provider>`, `/model <provider> <model-id>`."""
        self.prompt.clear()
        args = text.split()[1:]
        self.stack.start(text)
        if not args:
            self.stack.finish(
                "status",
                f"Current: {self.config.provider} · {self.config.model() or '—'}. "
                f"Try /model gemini or /model claude.")
            return
        provider = args[0].lower()
        model = args[1] if len(args) > 1 else None
        try:
            new_config = update_provider(provider, model)
        except ValueError as e:
            self.stack.finish("error", str(e))
            return
        self.reload_config(new_config)
        msg = f"Switched to {provider}" + (f" using {model}" if model else "")
        self.stack.finish("result", msg)
        self.hide()
