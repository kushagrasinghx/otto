"""Spotlight prompt box (frosted), animated step cards, and the agent worker."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation,
    Qt, QThread, QTimer, Signal,
)
from PySide6.QtGui import (
    QColor, QKeyEvent, QPainter, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from ..agent.factory import AgentConfigError, create_agent
from ..config import update_provider
from . import styles
from .blur import enable_blur, round_corners


# --------------------------------------------------------------------------
# Worker thread: runs the agent loop off the UI thread.
# --------------------------------------------------------------------------
class AgentWorker(QThread):
    event = Signal(str, str)       # (kind, text)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, agent, instruction: str):
        super().__init__()
        self.agent = agent
        self.instruction = instruction
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            result = self.agent.run(
                self.instruction,
                emit=lambda kind, text: self.event.emit(kind, text),
                should_stop=lambda: self._stop,
            )
            self.finished_ok.emit(result or "Done.")
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
# One step = one card. Fades in + slides up via a height-grow animation.
# --------------------------------------------------------------------------
class StepCard(QWidget):
    def __init__(self, kind: str, text: str, width: int):
        super().__init__()
        self._w = width
        self._target = 0

        # A single graphics effect per widget — nesting an opacity effect over a
        # child with its own drop-shadow effect makes Qt spam "QPainter::begin:
        # A paint device can only be painted by one painter at a time".
        self.opacity = QGraphicsOpacityEffect(self)
        self.opacity.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 8)  # gap between cards
        outer.setSpacing(0)

        inner = QFrame()
        inner.setObjectName("stepCard")

        row = QHBoxLayout(inner)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        dot = QFrame()
        dot.setObjectName("dot")
        dot.setProperty("kind", kind)
        dot.setFixedSize(8, 8)

        label = QLabel(text if len(text) <= 240 else text[:240] + "…")
        label.setObjectName("stepText")
        label.setWordWrap(True)

        row.addWidget(dot, 0, Qt.AlignTop)
        dot.setContentsMargins(0, 4, 0, 0)
        row.addWidget(label, 1)
        outer.addWidget(inner)

    def measure(self) -> int:
        self.setFixedWidth(self._w)
        self.layout().activate()
        self.adjustSize()
        self._target = self.sizeHint().height()
        self.setMaximumHeight(0)
        return self._target


# --------------------------------------------------------------------------
# Status stack: bottom-right, click-through, grows upward as steps arrive.
# --------------------------------------------------------------------------
class StatusStack(QWidget):
    MAX = 6
    MARGIN = 20
    CARD_W = 372
    WIN_W = CARD_W + 16  # + vbox left/right margins

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(8, 8, 8, 8)
        self.vbox.setSpacing(0)
        self.setStyleSheet(styles.STEP_QSS)

        self._anims: list[QParallelAnimationGroup] = []
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)

    # -- public API ---------------------------------------------------------
    def start(self, prompt: str):
        self._hide.stop()
        self._clear()
        self.show()
        self.append("status", f"“{prompt}”")

    def append(self, kind: str, text: str):
        card = StepCard(kind, text, self.CARD_W)
        self.vbox.addWidget(card)
        target = card.measure()

        grow = QPropertyAnimation(card, b"maximumHeight", self)
        grow.setStartValue(0)
        grow.setEndValue(target)
        grow.setDuration(300)
        grow.setEasingCurve(QEasingCurve.OutCubic)
        grow.valueChanged.connect(lambda _: self._reposition())

        fade = QPropertyAnimation(card.opacity, b"opacity", self)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setDuration(340)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(grow)
        group.addAnimation(fade)
        group.finished.connect(lambda: self._on_anim_done(group))
        self._anims.append(group)
        group.start()

        self._trim()
        self.show()
        self.raise_()
        self._reposition()

    def finish(self, kind: str, text: str):
        self.append(kind, text)
        self._hide.start(7000)

    # -- internals ----------------------------------------------------------
    def _on_anim_done(self, group):
        if group in self._anims:
            self._anims.remove(group)
        self._reposition()

    def _clear(self):
        self._anims.clear()
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _trim(self):
        while self.vbox.count() > self.MAX:
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _content_height(self) -> int:
        m = self.vbox.contentsMargins()
        h = m.top() + m.bottom()
        for i in range(self.vbox.count()):
            w = self.vbox.itemAt(i).widget()
            if not w:
                continue
            h += min(w.maximumHeight(), w.sizeHint().height())
        return max(h, 1)

    def _reposition(self):
        h = self._content_height()
        self.resize(self.WIN_W, h)
        g = QApplication.primaryScreen().availableGeometry()
        self.move(g.right() - self.WIN_W - self.MARGIN,
                  g.bottom() - h - self.MARGIN)


# --------------------------------------------------------------------------
# Spotlight prompt window (frosted / acrylic).
# --------------------------------------------------------------------------
class SpotlightWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._agent = None
        self.worker: AgentWorker | None = None
        self.stack = StatusStack()
        self._blur_ready = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(22, 18, 22, 14)
        lay.setSpacing(14)

        # row 1: search icon + input
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(_search_icon(20))
        icon.setFixedSize(20, 26)
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

        # row 2: model-switch hint (left) + key hints (right) — plain text, no icons
        row2 = QHBoxLayout()
        self.model_hint = QLabel("Use /model to switch models")
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
        self.activateWindow()
        self.prompt.setFocus()
        self.prompt.selectAll()
        self._apply_blur()

    def _apply_blur(self):
        try:
            hwnd = int(self.winId())
            ok = enable_blur(hwnd)
            round_corners(hwnd)
            self.card.setProperty("blur", "true" if ok else "false")
            self.card.style().unpolish(self.card)
            self.card.style().polish(self.card)
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

    # -- run ----------------------------------------------------------------
    def submit(self):
        text = self.prompt.text().strip()
        if not text:
            return
        if self.worker and self.worker.isRunning():
            return
        if text.lower().startswith("/model"):
            self._handle_model_command(text)
            return
        try:
            agent = self._ensure_agent()
        except AgentConfigError as e:
            self.stack.start(text)
            self.stack.finish("error", str(e))
            self.hide()
            return
        except Exception as e:
            self.stack.start(text)
            self.stack.finish("error", f"Could not start agent: {e}")
            self.hide()
            return

        self.prompt.clear()
        self.hide()  # get out of the agent's way — it drives the real screen
        self.stack.start(text)

        self.worker = AgentWorker(agent, text)
        self.worker.event.connect(self.stack.append)
        self.worker.finished_ok.connect(lambda r: self.stack.finish("result", r))
        self.worker.failed.connect(lambda e: self.stack.finish("error", e))
        self.worker.start()

    def _handle_model_command(self, text: str):
        """Handle `/model`, `/model <provider>`, `/model <provider> <model-id>`."""
        self.prompt.clear()
        args = text.split()[1:]
        self.stack.start(text)
        if not args:
            self.stack.finish(
                "status",
                f"Current: {self.config.provider} · {self.config.model() or '—'}. "
                f"Try /model gemini, /model claude, or /model bedrock.")
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
