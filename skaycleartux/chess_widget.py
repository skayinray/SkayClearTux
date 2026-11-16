"""Шахматный экран SkayClearTux: доска, взаимодействие, бот в отдельном потоке.

Фигуры — векторный набор Cburnett (стандарт Lichess), отрендеренный в PNG.
"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QRectF, Qt, QThread,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from .chess_engine import Board, sq_name
from .resources import asset

_PIECE_CACHE: dict[tuple[str, int], QPixmap] = {}


def piece_pixmap(piece: str, size: int) -> QPixmap:
    """Кэшированная картинка фигуры нужного размера."""
    key = (piece, size)
    pm = _PIECE_CACHE.get(key)
    if pm is None:
        color = "w" if piece.isupper() else "b"
        pm = QPixmap(asset(f"pieces/{color}{piece.upper()}.png")).scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        _PIECE_CACHE[key] = pm
    return pm


class BotThread(QThread):
    done = Signal(object)

    def __init__(self, fen: str, depth: int):
        super().__init__()
        self.fen, self.depth = fen, depth

    def run(self) -> None:
        self.done.emit(Board(self.fen).best_move(self.depth))


class BoardView(QWidget):
    clicked = Signal(int)

    def __init__(self, light: str, dark: str, parent=None):
        super().__init__(parent)
        self.game = Board()
        self.light, self.dark = light, dark
        self.flipped = False
        self.selected: int | None = None
        self.targets: list[int] = []
        self.last_move: tuple[int, int] | None = None
        self.hint_move: tuple[int, int] | None = None
        self.check_sq: int | None = None
        self.interactive = True
        # настройки отображения
        self.show_coords = True
        self.show_hints = True
        self.highlight_last = True
        # анимация хода
        self._anim: dict | None = None
        self._anim_progress = 0.0
        self._anim_anim = QVariantAnimation(self)
        self._anim_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_anim.valueChanged.connect(self._on_anim)
        self._anim_anim.finished.connect(self._anim_finished)
        self.setMinimumSize(380, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _metrics(self):
        side = min(self.width(), self.height())
        return side / 8.0, (self.width() - side) / 2.0, (self.height() - side) / 2.0

    def _rect(self, i: int, sq: float, ox: float, oy: float) -> QRectF:
        r, f = i // 8, i % 8
        sr, sc = (7 - r, 7 - f) if self.flipped else (r, f)
        return QRectF(ox + sc * sq, oy + sr * sq, sq, sq)

    def _square_at(self, x: float, y: float) -> int | None:
        sq, ox, oy = self._metrics()
        sc = int((x - ox) // sq)
        sr = int((y - oy) // sq)
        if not (0 <= sc < 8 and 0 <= sr < 8):
            return None
        if self.flipped:
            sr, sc = 7 - sr, 7 - sc
        return sr * 8 + sc

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        sq, ox, oy = self._metrics()

        for i in range(64):
            rect = self._rect(i, sq, ox, oy)
            r, f = i // 8, i % 8
            base = self.light if (r + f) % 2 == 0 else self.dark
            col = QColor(base)
            if self.selected == i:
                col = col.lighter(135)
            p.fillRect(rect, col)
            if self.highlight_last and self.last_move and i in self.last_move:
                p.fillRect(rect, QColor(255, 235, 130, 80))
            if self.hint_move and i in self.hint_move:
                p.fillRect(rect, QColor(120, 200, 120, 90))
            if self.check_sq == i:
                p.fillRect(rect, QColor(255, 70, 70, 110))

        # координаты
        if self.show_coords:
            p.setPen(QColor(0, 0, 0, 110))
            fnt = QFont("DejaVu Sans")
            fnt.setPixelSize(max(9, int(sq * 0.17)))
            fnt.setBold(True)
            p.setFont(fnt)
            files = "abcdefgh"
            for k in range(8):
                sc = 7 - k if self.flipped else k
                sr = 7 if not self.flipped else 0
                p.drawText(self._rect(sr * 8 + sc, sq, ox, oy).adjusted(4, 0, 0, -3),
                           Qt.AlignLeft | Qt.AlignBottom, files[sc])
                rank = 8 - (7 - k if self.flipped else k)
                p.drawText(self._rect((7 - k) * 8, sq, ox, oy).adjusted(0, 3, -4, 0),
                           Qt.AlignRight | Qt.AlignTop, str(rank))

        # подсказки ходов
        if self.show_hints:
            for t in self.targets:
                rect = self._rect(t, sq, ox, oy)
                if self.game.sq[t]:
                    p.setPen(QPen(QColor(50, 50, 50, 160), max(2.0, sq * 0.06)))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(rect.adjusted(sq * 0.06, sq * 0.06,
                                                -sq * 0.06, -sq * 0.06))
                else:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QBrush(QColor(50, 50, 50, 120)))
                    d = sq * 0.16
                    p.drawEllipse(rect.center(), d, d)

        # фигуры
        size = int(round(sq * 0.94))
        anim_to = self._anim["to"] if self._anim else None
        for i, piece in enumerate(self.game.sq):
            if not piece or i == anim_to:
                continue
            rect = self._rect(i, sq, ox, oy)
            pm = piece_pixmap(piece, size)
            p.drawPixmap(int(rect.x() + (rect.width() - pm.width()) / 2),
                         int(rect.y() + (rect.height() - pm.height()) / 2), pm)
        # движущаяся фигура
        if self._anim:
            frm = self._rect(self._anim["frm"], sq, ox, oy).center()
            to = self._rect(self._anim["to"], sq, ox, oy).center()
            t = self._anim_progress
            cx = frm.x() + (to.x() - frm.x()) * t
            cy = frm.y() + (to.y() - frm.y()) * t
            pm = piece_pixmap(self._anim["piece"], size)
            p.drawPixmap(int(cx - pm.width() / 2), int(cy - pm.height() / 2), pm)
        p.end()

    # ------------------------------------------------------------ анимация
    def animate_move(self, frm: int, to: int, duration: int = 200) -> None:
        piece = self.game.sq[to]
        if not piece:
            return
        self._anim = {"frm": frm, "to": to, "piece": piece}
        self._anim_progress = 0.0
        self._anim_anim.stop()
        self._anim_anim.setDuration(max(60, duration))
        self._anim_anim.setStartValue(0.0)
        self._anim_anim.setEndValue(1.0)
        self._anim_anim.start()

    def stop_animation(self) -> None:
        self._anim_anim.stop()
        self._anim = None
        self._anim_progress = 0.0
        self.update()

    def _on_anim(self, value) -> None:
        self._anim_progress = float(value)
        self.update()

    def _anim_finished(self) -> None:
        self._anim = None
        self._anim_progress = 0.0
        self.update()

    def mousePressEvent(self, e) -> None:
        if not self.interactive:
            return
        i = self._square_at(e.position().x(), e.position().y())
        if i is not None:
            self.clicked.emit(i)


class PromotionDialog(QDialog):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Превращение пешки")
        self.choice = "q"
        lay = QHBoxLayout(self)
        lay.setSpacing(8)
        prefix = "w" if color == "w" else "b"
        for code in "qrbn":
            b = QPushButton()
            b.setIcon(piece_pixmap(code.upper() if prefix == "w" else code,
                                   64))
            from PySide6.QtCore import QSize
            b.setIconSize(QSize(56, 56))
            b.setFixedSize(76, 76)
            b.clicked.connect(lambda _=False, c=code: self._pick(c))
            lay.addWidget(b)

    def _pick(self, c: str) -> None:
        self.choice = c
        self.accept()


class ChessPage(QWidget):
    LEVELS = {"Новичок": 1, "Легко": 2, "Средне": 3, "Сложно": 4}
    BOT_ELO = {"Новичок": 800, "Легко": 1100, "Средне": 1500, "Сложно": 1900}

    def __init__(self, theme_colors: dict, settings, parent=None):
        super().__init__(parent)
        self.colors = theme_colors
        self.settings = settings
        self.human = "w"
        self._thread: BotThread | None = None
        self._mode = "bot"
        self._result_recorded = False
        self._last_delta = 0
        self._build()
        self.apply_settings()
        self._new_game()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        self.view = BoardView(self.colors["board_light"], self.colors["board_dark"])
        self.view.clicked.connect(self._on_click)
        root.addWidget(self.view, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        title = QLabel("Шахматы с ботом")
        title.setObjectName("H2")
        side.addWidget(title)

        side.addWidget(QLabel("Сложность"))
        self.level = QComboBox()
        self.level.addItems(self.LEVELS.keys())
        self.level.currentTextChanged.connect(self._difficulty_changed)
        side.addWidget(self.level)

        side.addWidget(QLabel("Играю за"))
        self.side_box = QComboBox()
        self.side_box.addItems(["Белые", "Чёрные"])
        self.side_box.currentTextChanged.connect(
            lambda t: self.settings.set("chess/side", t))
        side.addWidget(self.side_box)

        self.status = QLabel("")
        self.status.setObjectName("CardSub")
        self.status.setWordWrap(True)
        side.addWidget(self.status)

        elo_box = QFrame()
        elo_box.setObjectName("Card")
        el = QVBoxLayout(elo_box)
        el.setContentsMargins(14, 12, 14, 12)
        el.setSpacing(2)
        et = QLabel("Рейтинг Эло")
        et.setObjectName("CardSub")
        self.elo_value = QLabel("1200")
        self.elo_value.setObjectName("Metric")
        self.elo_bot = QLabel("")
        self.elo_bot.setObjectName("CardSub")
        self.elo_stats = QLabel("")
        self.elo_stats.setObjectName("CardSub")
        self.elo_stats.setWordWrap(True)
        el.addWidget(et)
        el.addWidget(self.elo_value)
        el.addWidget(self.elo_bot)
        el.addWidget(self.elo_stats)
        side.addWidget(elo_box)

        row = QHBoxLayout()
        self.btn_new = QPushButton("Новая партия")
        self.btn_new.clicked.connect(self._new_game)
        self.btn_undo = QPushButton("Отменить ход")
        self.btn_undo.clicked.connect(self._undo)
        row.addWidget(self.btn_new)
        row.addWidget(self.btn_undo)
        side.addLayout(row)

        row2 = QHBoxLayout()
        self.btn_hint = QPushButton("Подсказка")
        self.btn_hint.clicked.connect(self._hint)
        self.flip_btn = QPushButton("Перевернуть доску")
        self.flip_btn.clicked.connect(self._flip)
        row2.addWidget(self.btn_hint)
        row2.addWidget(self.flip_btn)
        side.addLayout(row2)

        side.addWidget(QLabel("Ходы"))
        self.moves_label = side.itemAt(side.count() - 1).widget()
        self.moves = QListWidget()
        side.addWidget(self.moves, 1)
        root.addLayout(side, 1)

    # ---------------------------------------------------------- настройки
    def apply_settings(self) -> None:
        self.level.setCurrentText(self.settings.get("chess/difficulty"))
        self.side_box.setCurrentText(self.settings.get("chess/side"))
        self.view.show_coords = self.settings.get_bool("chess/show_coords")
        self.view.show_hints = self.settings.get_bool("chess/show_hints")
        self.view.highlight_last = self.settings.get_bool("chess/highlight_last")
        show_moves = self.settings.get_bool("chess/show_move_list")
        self.moves.setVisible(show_moves)
        if self.moves_label is not None:
            self.moves_label.setVisible(show_moves)
        self.view.update()

    # ------------------------------------------------------------------ игра
    def _new_game(self) -> None:
        self.human = "w" if self.side_box.currentText() == "Белые" else "b"
        self.view.game = Board()
        self.view.flipped = self.human == "b"
        self.view.selected = None
        self.view.targets = []
        self.view.last_move = None
        self.view.hint_move = None
        self.view.check_sq = None
        self.moves.clear()
        self._result_recorded = False
        self._last_delta = 0
        self._update_status()
        self._update_elo_card()
        self.view.update()
        if self.view.game.turn != self.human:
            self._bot_move()

    def _flip(self) -> None:
        self.view.flipped = not self.view.flipped
        self.view.update()

    def _undo(self) -> None:
        g = self.view.game
        if self._thread and self._thread.isRunning():
            return
        self.view.stop_animation()
        g.undo()
        if g.turn != self.human and g.history:
            g.undo()
        if self.moves.count():
            self.moves.takeItem(self.moves.count() - 1)
        self.view.selected = None
        self.view.targets = []
        self.view.last_move = None
        self.view.hint_move = None
        self._update_status()
        self.view.update()

    def _on_click(self, i: int) -> None:
        g = self.view.game
        if g.turn != self.human or (self._thread and self._thread.isRunning()):
            return
        if self.view.selected is not None and i in self.view.targets:
            self._apply_human(self.view.selected, i)
            return
        piece = g.sq[i]
        if piece and ((piece.isupper() and self.human == "w") or
                      (piece.islower() and self.human == "b")):
            self.view.selected = i
            self.view.targets = [m[1] for m in g.moves_from(i)]
        else:
            self.view.selected = None
            self.view.targets = []
        self.view.update()

    def _apply_human(self, frm: int, to: int) -> None:
        g = self.view.game
        options = [m for m in g.moves_from(frm) if m[1] == to]
        if not options:
            return
        promo = ""
        if len(options) > 1 and any(m[2] in "qrbn" for m in options):
            if self.settings.get_bool("chess/auto_queen"):
                promo = "q"
            else:
                dlg = PromotionDialog(g.sq[frm], self)
                promo = dlg.choice if dlg.exec() else "q"
        else:
            promo = options[0][2]
        g.make_move((frm, to, promo))
        self._after_move(frm, to)
        if g.status()[0] == "play" and g.turn != self.human:
            self._bot_move()

    def _bot_move(self) -> None:
        self.status.setText("Бот думает…")
        self.view.interactive = False
        self._run_engine("bot", self.LEVELS[self.level.currentText()])

    def _hint(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        if self.view.game.turn != self.human or self.view.game.status()[0] != "play":
            return
        self.status.setText("Ищу подсказку…")
        depth = max(2, self.LEVELS[self.level.currentText()])
        self._run_engine("hint", depth)

    def _run_engine(self, mode: str, depth: int) -> None:
        self._mode = mode
        self._thread = BotThread(self.view.game.fen(), depth)
        self._thread.done.connect(self._on_engine_result)
        self._thread.start()

    def _on_engine_result(self, mv) -> None:
        if self._mode == "bot":
            self.view.interactive = True
            if mv:
                self.view.game.make_move(mv)
                self._after_move(mv[0], mv[1])
            self._update_status()
            self.view.update()
        else:
            if mv:
                self.view.hint_move = (mv[0], mv[1])
                self.status.setText(
                    f"Подсказка: {sq_name(mv[0])}–{sq_name(mv[1])}")
                self.view.update()
            else:
                self._update_status()

    def _after_move(self, frm: int, to: int) -> None:
        self.view.last_move = (frm, to)
        self.view.hint_move = None
        self.view.selected = None
        self.view.targets = []
        if self.settings.get_bool("chess/animate"):
            self.view.animate_move(frm, to, self.settings.get_int("ui/anim_ms") + 60)
        self.moves.addItem(f"{sq_name(frm)}–{sq_name(to)}")
        self.moves.scrollToBottom()
        self._update_status()
        self._check_game_over()
        self.view.update()

    def _update_status(self) -> None:
        state, text = self.view.game.status()
        if state == "play":
            who = "Белые" if self.view.game.turn == "w" else "Чёрные"
            self.status.setText(text or f"Ход: {who}")
        else:
            self.status.setText(text)
        g = self.view.game
        self.view.check_sq = g.king_sq(g.turn) if g.in_check(g.turn) else None

    # ------------------------------------------------------------------ Эло
    def _difficulty_changed(self, text: str) -> None:
        self.settings.set("chess/difficulty", text)
        self._update_elo_card()

    def _update_elo_card(self) -> None:
        elo = self.settings.get_int("chess/elo")
        best = self.settings.get_int("chess/best_elo")
        games = self.settings.get_int("chess/games")
        wins = self.settings.get_int("chess/wins")
        losses = self.settings.get_int("chess/losses")
        draws = self.settings.get_int("chess/draws")
        bot = self.BOT_ELO.get(self.level.currentText(), 1500)
        self.elo_value.setText(str(elo))
        delta = ""
        if self._last_delta:
            sign = "+" if self._last_delta > 0 else ""
            delta = f"  ({sign}{self._last_delta})"
        self.elo_bot.setText(f"Соперник: ~{bot}{delta}")
        self.elo_stats.setText(
            f"Партий: {games}   Побед: {wins}   Ничьих: {draws}   "
            f"Поражений: {losses}\nЛучший рейтинг: {best}")

    def _check_game_over(self) -> None:
        state, _text = self.view.game.status()
        if state == "play" or self._result_recorded:
            return
        self._result_recorded = True
        winner = None  # 'human' | 'bot' | None(ничья)
        if state == "checkmate":
            loser = self.view.game.turn  # сторона, которой поставлен мат
            winner = "bot" if loser == self.human else "human"
        self._record_result(winner)

    def _record_result(self, winner: str | None) -> None:
        elo = self.settings.get_int("chess/elo")
        bot = self.BOT_ELO.get(self.level.currentText(), 1500)
        expected = 1.0 / (1.0 + 10 ** ((bot - elo) / 400.0))
        actual = 1.0 if winner == "human" else (0.0 if winner == "bot" else 0.5)
        k = 32 if self.settings.get_int("chess/games") < 20 else 20
        delta = round(k * (actual - expected))
        if delta == 0 and actual != expected:
            delta = 1 if actual > expected else -1
        new_elo = max(100, min(3000, elo + delta))
        self._last_delta = new_elo - elo

        games = self.settings.get_int("chess/games") + 1
        self.settings.set("chess/elo", new_elo)
        self.settings.set("chess/games", games)
        if winner == "human":
            self.settings.set("chess/wins", self.settings.get_int("chess/wins") + 1)
            outcome = "Победа!"
        elif winner == "bot":
            self.settings.set("chess/losses", self.settings.get_int("chess/losses") + 1)
            outcome = "Поражение"
        else:
            self.settings.set("chess/draws", self.settings.get_int("chess/draws") + 1)
            outcome = "Ничья"
        best = self.settings.get_int("chess/best_elo")
        if new_elo > best:
            self.settings.set("chess/best_elo", new_elo)
        self.settings.save()

        sign = "+" if self._last_delta > 0 else ""
        self.status.setText(
            f"{outcome}  Рейтинг: {new_elo} ({sign}{self._last_delta})")
        self._update_elo_card()
