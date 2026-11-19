"""Шахматный движок SkayClearTux: полные правила + бот (негамакс с альфа-бета).

Представление доски: список из 64 строк. Индекс 0 = a8, 63 = h1
(удобно для таблиц оценки). Белые фигуры — заглавные, чёрные — строчные.
"""
from __future__ import annotations

import random
import time


class _SearchTimeoutError(Exception):
    """Прерывание поиска по лимиту времени."""

FILES = "abcdefgh"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

PIECE_VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

# Таблицы позиционной оценки (взгляд белых, индекс 0 = a8).
PAWN_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]
KNIGHT_PST = [
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50,
]
BISHOP_PST = [
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
]
ROOK_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
]
QUEEN_PST = [
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
     0,  0,  5,  5,  5,  5,  0, -5,
   -10,  5,  5,  5,  5,  5,  0,-10,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
]
KING_PST = [
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20,
]
PST = {"P": PAWN_PST, "N": KNIGHT_PST, "B": BISHOP_PST,
       "R": ROOK_PST, "Q": QUEEN_PST, "K": KING_PST}

KNIGHT_D = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_D = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
BISHOP_D = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_D = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def color(p: str) -> str:
    return "w" if p.isupper() else "b"


def rk(i: int) -> int:
    return i // 8


def fl(i: int) -> int:
    return i % 8


def on(r: int, f: int) -> bool:
    return 0 <= r < 8 and 0 <= f < 8


def sq_name(i: int) -> str:
    return FILES[fl(i)] + str(8 - rk(i))


class Board:
    def __init__(self, fen: str = START_FEN):
        self.sq: list[str] = [""] * 64
        self.turn = "w"
        self.castling: set[str] = set()
        self.ep: int | None = None
        self.halfmove = 0
        self.fullmove = 1
        self.history: list[dict] = []
        self._set_fen(fen)

    # ------------------------------------------------------------------ FEN
    def _set_fen(self, fen: str) -> None:
        parts = fen.split()
        rows = parts[0].split("/")
        self.sq = [""] * 64
        for r, row in enumerate(rows):
            f = 0
            for ch in row:
                if ch.isdigit():
                    f += int(ch)
                else:
                    self.sq[r * 8 + f] = ch
                    f += 1
        self.turn = parts[1] if len(parts) > 1 else "w"
        self.castling = set(parts[2]) if len(parts) > 2 and parts[2] != "-" else set()
        self.ep = None
        if len(parts) > 3 and parts[3] != "-":
            self.ep = FILES.index(parts[3][0]) + (8 - int(parts[3][1])) * 8
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove = int(parts[5]) if len(parts) > 5 else 1
        self.history = []

    def fen(self) -> str:
        rows = []
        for r in range(8):
            empty = 0
            row = ""
            for f in range(8):
                p = self.sq[r * 8 + f]
                if not p:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += p
            if empty:
                row += str(empty)
            rows.append(row)
        ep = sq_name(self.ep) if self.ep is not None else "-"
        cast = "".join(c for c in "KQkq" if c in self.castling) or "-"
        return f"{'/'.join(rows)} {self.turn} {cast} {ep} {self.halfmove} {self.fullmove}"

    # --------------------------------------------------------------- атака
    def king_sq(self, c: str) -> int:
        target = "K" if c == "w" else "k"
        try:
            return self.sq.index(target)
        except ValueError:
            # повреждённое состояние — не даём движку упасть
            return -1

    def attacked(self, square: int, by: str) -> bool:
        if square < 0 or square > 63:
            return False
        r0, f0 = rk(square), fl(square)
        # пешки
        dr = 1 if by == "w" else -1  # пешка бьёт "вверх" (dr=-1 в индексах белых)
        # белые пешки атакуют с меньшего ранга (больший индекс) — атакуют вверх
        for df in (-1, 1):
            r, f = r0 + (1 if by == "w" else -1), f0 + df
            if on(r, f):
                p = self.sq[r * 8 + f]
                if p == ("P" if by == "w" else "p"):
                    return True
        # кони
        for dr, df in KNIGHT_D:
            r, f = r0 + dr, f0 + df
            if on(r, f) and self.sq[r * 8 + f] == ("N" if by == "w" else "n"):
                return True
        # король
        for dr, df in KING_D:
            r, f = r0 + dr, f0 + df
            if on(r, f) and self.sq[r * 8 + f] == ("K" if by == "w" else "k"):
                return True
        # слон/ферзь
        for dr, df in BISHOP_D:
            r, f = r0 + dr, f0 + df
            while on(r, f):
                p = self.sq[r * 8 + f]
                if p:
                    if color(p) == by and p.upper() in ("B", "Q"):
                        return True
                    break
                r, f = r + dr, f + df
        # ладья/ферзь
        for dr, df in ROOK_D:
            r, f = r0 + dr, f0 + df
            while on(r, f):
                p = self.sq[r * 8 + f]
                if p:
                    if color(p) == by and p.upper() in ("R", "Q"):
                        return True
                    break
                r, f = r + dr, f + df
        return False

    def in_check(self, c: str) -> bool:
        k = self.king_sq(c)
        if k < 0:
            return False
        return self.attacked(k, "b" if c == "w" else "w")

    # --------------------------------------------------------------- ходы
    def _add_pawn(self, i: int, moves: list) -> None:
        c = self.turn
        r, f = rk(i), fl(i)
        dr = -1 if c == "w" else 1
        start_rank = 6 if c == "w" else 1
        promo_rank = 0 if c == "w" else 7
        # вперёд
        r1 = r + dr
        if on(r1, f) and not self.sq[r1 * 8 + f]:
            if r1 == promo_rank:
                for pr in "qrbn":
                    moves.append((i, r1 * 8 + f, pr))
            else:
                moves.append((i, r1 * 8 + f, ""))
                r2 = r + 2 * dr
                if r == start_rank and not self.sq[r2 * 8 + f]:
                    moves.append((i, r2 * 8 + f, ""))
        # взятия
        for df in (-1, 1):
            rr, ff = r + dr, f + df
            if not on(rr, ff):
                continue
            t = rr * 8 + ff
            tp = self.sq[t]
            if tp and color(tp) != c:
                if rr == promo_rank:
                    for pr in "qrbn":
                        moves.append((i, t, pr))
                else:
                    moves.append((i, t, ""))
            elif not tp and self.ep == t:
                moves.append((i, t, "ep"))

    def _add_sliding(self, i: int, dirs, moves: list) -> None:
        c = self.turn
        r0, f0 = rk(i), fl(i)
        for dr, df in dirs:
            r, f = r0 + dr, f0 + df
            while on(r, f):
                t = r * 8 + f
                tp = self.sq[t]
                if not tp:
                    moves.append((i, t, ""))
                else:
                    if color(tp) != c:
                        moves.append((i, t, ""))
                    break
                r, f = r + dr, f + df

    def _add_step(self, i: int, dirs, moves: list) -> None:
        c = self.turn
        r0, f0 = rk(i), fl(i)
        for dr, df in dirs:
            r, f = r0 + dr, f0 + df
            if on(r, f):
                t = r * 8 + f
                tp = self.sq[t]
                if not tp or color(tp) != c:
                    moves.append((i, t, ""))

    def _add_castling(self, moves: list) -> None:
        c = self.turn
        if c == "w" and self.sq[60] == "K" and not self.attacked(60, "b"):
            if "K" in self.castling and not self.sq[61] and not self.sq[62] \
                    and not self.attacked(61, "b") and not self.attacked(62, "b"):
                moves.append((60, 62, "castle"))
            if "Q" in self.castling and not self.sq[59] and not self.sq[58] \
                    and not self.sq[57] and not self.attacked(59, "b") \
                    and not self.attacked(58, "b"):
                moves.append((60, 58, "castle"))
        elif c == "b" and self.sq[4] == "k" and not self.attacked(4, "w"):
            if "k" in self.castling and not self.sq[5] and not self.sq[6] \
                    and not self.attacked(5, "w") and not self.attacked(6, "w"):
                moves.append((4, 6, "castle"))
            if "q" in self.castling and not self.sq[3] and not self.sq[2] \
                    and not self.sq[1] and not self.attacked(3, "w") \
                    and not self.attacked(2, "w"):
                moves.append((4, 2, "castle"))

    def pseudo_moves(self) -> list[tuple[int, int, str]]:
        moves: list[tuple[int, int, str]] = []
        for i, p in enumerate(self.sq):
            if not p or color(p) != self.turn:
                continue
            u = p.upper()
            if u == "P":
                self._add_pawn(i, moves)
            elif u == "N":
                self._add_step(i, KNIGHT_D, moves)
            elif u == "B":
                self._add_sliding(i, BISHOP_D, moves)
            elif u == "R":
                self._add_sliding(i, ROOK_D, moves)
            elif u == "Q":
                self._add_sliding(i, BISHOP_D + ROOK_D, moves)
            elif u == "K":
                self._add_step(i, KING_D, moves)
        self._add_castling(moves)
        return moves

    def legal_moves(self) -> list[tuple[int, int, str]]:
        res = []
        mover = self.turn
        for m in self.pseudo_moves():
            self.make_move(m)
            if not self.in_check(mover):
                res.append(m)
            self.undo()
        return res

    def moves_from(self, i: int) -> list[tuple[int, int, str]]:
        return [m for m in self.legal_moves() if m[0] == i]

    # ------------------------------------------------------------ ход/откат
    def make_move(self, m: tuple[int, int, str]) -> None:
        frm, to, promo = m
        undo = {
            "move": m,
            "captured": self.sq[to],
            "castling": set(self.castling),
            "ep": self.ep,
            "halfmove": self.halfmove,
            "fullmove": self.fullmove,
            "turn": self.turn,
        }
        p = self.sq[frm]
        c = color(p)
        self.sq[frm] = ""
        # взятие на проходе
        if promo == "ep":
            cap_sq = to + (8 if c == "w" else -8)
            undo["captured"] = self.sq[cap_sq]
            undo["ep_cap_sq"] = cap_sq
            self.sq[cap_sq] = ""
        # рокировка
        if promo == "castle":
            if to == 62:
                self.sq[61], self.sq[63] = self.sq[63], ""
            elif to == 58:
                self.sq[59], self.sq[56] = self.sq[56], ""
            elif to == 6:
                self.sq[5], self.sq[7] = self.sq[7], ""
            elif to == 2:
                self.sq[3], self.sq[0] = self.sq[0], ""
        # установка фигуры (с превращением)
        if promo in ("q", "r", "b", "n"):
            self.sq[to] = promo.upper() if c == "w" else promo
        else:
            self.sq[to] = p
        # обновление прав рокировки
        if p.upper() == "K":
            self.castling -= {"K", "Q"} if c == "w" else {"k", "q"}
        if p.upper() == "R":
            if frm == 63:
                self.castling.discard("K")
            elif frm == 56:
                self.castling.discard("Q")
            elif frm == 7:
                self.castling.discard("k")
            elif frm == 0:
                self.castling.discard("q")
        if to == 63:
            self.castling.discard("K")
        elif to == 56:
            self.castling.discard("Q")
        elif to == 7:
            self.castling.discard("k")
        elif to == 0:
            self.castling.discard("q")
        # en passant цель
        self.ep = None
        if p.upper() == "P" and abs(rk(to) - rk(frm)) == 2:
            self.ep = (frm + to) // 2
        # счётчики
        if p.upper() == "P" or undo["captured"]:
            self.halfmove = 0
        else:
            self.halfmove += 1
        if c == "b":
            self.fullmove += 1
        self.turn = "b" if c == "w" else "w"
        self.history.append(undo)

    def undo(self) -> None:
        if not self.history:
            return
        u = self.history.pop()
        frm, to, promo = u["move"]
        c = u["turn"]
        # вернуть фигуру
        if promo in ("q", "r", "b", "n"):
            self.sq[frm] = "P" if c == "w" else "p"
        else:
            self.sq[frm] = self.sq[to]
        self.sq[to] = ""
        # вернуть рокировку
        if promo == "castle":
            if to == 62:
                self.sq[63], self.sq[61] = self.sq[61], ""
            elif to == 58:
                self.sq[56], self.sq[59] = self.sq[59], ""
            elif to == 6:
                self.sq[7], self.sq[5] = self.sq[5], ""
            elif to == 2:
                self.sq[0], self.sq[3] = self.sq[3], ""
        # вернуть взятое
        if "ep_cap_sq" in u:
            self.sq[u["ep_cap_sq"]] = u["captured"]
        elif u["captured"]:
            self.sq[to] = u["captured"]
        self.castling = u["castling"]
        self.ep = u["ep"]
        self.halfmove = u["halfmove"]
        self.fullmove = u["fullmove"]
        self.turn = u["turn"]

    # ------------------------------------------------------------- статус
    def status(self) -> tuple[str, str]:
        """('play'|'checkmate'|'stalemate'|'draw', текст)."""
        try:
            moves = self.legal_moves()
        except Exception:  # noqa: BLE001
            return "draw", "Ошибка позиции"
        if not moves:
            if self.in_check(self.turn):
                winner = "Чёрные" if self.turn == "w" else "Белые"
                return "checkmate", f"Мат! Победа: {winner}"
            return "stalemate", "Пат — ничья"
        if self.halfmove >= 100:
            return "draw", "Ничья по правилу 50 ходов"
        if self._insufficient():
            return "draw", "Ничья: недостаточно материала"
        return "play", ("Шах!" if self.in_check(self.turn) else "")

    def _insufficient(self) -> bool:
        pieces = [p.upper() for p in self.sq if p]
        if any(p in ("P", "R", "Q") for p in pieces):
            return False
        minors = [p for p in pieces if p in ("N", "B")]
        return len(minors) <= 1

    # -------------------------------------------------------------- оценка
    def evaluate(self) -> int:
        """Оценка в сантипешках, положительно — в пользу белых."""
        score = 0
        for i, p in enumerate(self.sq):
            if not p:
                continue
            u = p.upper()
            val = PIECE_VALUE[u] + PST[u][i]
            if p.isupper():
                score += val
            else:
                score -= PIECE_VALUE[u] + PST[u][i ^ 56]
        return score

    def _move_order_key(self, m: tuple[int, int, str]) -> int:
        """Эвристика для сортировки ходов (чем больше — тем раньше)."""
        frm, to, promo = m
        score = 0
        victim = self.sq[to]
        if promo == "ep":
            victim = "p"
        if victim:
            attacker = self.sq[frm]
            v = PIECE_VALUE.get(victim.upper(), 0)
            a = PIECE_VALUE.get(attacker.upper(), 100) if attacker else 100
            score += 10 * v - a  # MVV-LVA
        if promo in ("q", "r", "b", "n"):
            score += PIECE_VALUE.get(promo.upper(), 0)
        elif promo == "castle":
            score += 50
        # небольшой бонус за продвижение пешки
        p = self.sq[frm]
        if p and p.upper() == "P":
            r_to = rk(to)
            score += (6 - r_to) if p.isupper() else r_to
        return -score  # sort ascending

    def _ordered_moves(self) -> list[tuple[int, int, str]]:
        moves = self.legal_moves()
        moves.sort(key=self._move_order_key)
        return moves

    def negamax(self, depth: int, alpha: int, beta: int,
                deadline: float | None = None, nodes: list[int] | None = None) -> int:
        if deadline is not None and nodes is not None:
            nodes[0] += 1
            if (nodes[0] & 2047) == 0 and time.monotonic() >= deadline:
                raise _SearchTimeoutError()
        moves = self.legal_moves()
        if not moves:
            if self.in_check(self.turn):
                return -100000 - depth
            return 0
        if depth == 0:
            s = self.evaluate()
            return s if self.turn == "w" else -s
        moves.sort(key=self._move_order_key)
        best = -10**9
        for m in moves:
            self.make_move(m)
            val = -self.negamax(depth - 1, -beta, -alpha, deadline, nodes)
            self.undo()
            if val > best:
                best = val
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    def search_best(self, depth: int = 2,
                    time_limit: float | None = None) -> tuple[tuple[int, int, str] | None, int]:
        """Возвращает (лучший_ход, оценка) с точки зрения стороны, чей ход."""
        moves = self._ordered_moves()
        if not moves:
            if self.in_check(self.turn):
                return None, -100000
            return None, 0
        # на малой глубине добавим чуть разнообразия
        if depth <= 1 and len(moves) > 1:
            random.shuffle(moves[: min(4, len(moves))])
            mv = moves[0]
            self.make_move(mv)
            try:
                val = -self.negamax(0, -10**9, 10**9)
            finally:
                self.undo()
            return mv, val

        deadline = (time.monotonic() + max(0.05, float(time_limit))
                    ) if time_limit is not None else None
        nodes = [0]
        best_move: tuple[int, int, str] = moves[0]
        best_val = -10**9

        def _root(d: int):
            local_best = moves[0]
            local_val = -10**9
            alpha, beta = -10**9, 10**9
            ordered = self._ordered_moves()
            for m in ordered:
                self.make_move(m)
                try:
                    val = -self.negamax(d - 1, -beta, -alpha, deadline, nodes)
                except _SearchTimeoutError:
                    self.undo()
                    raise
                self.undo()
                if val > local_val:
                    local_val = val
                    local_best = m
                if val > alpha:
                    alpha = val
            return local_val, local_best

        # итеративное углубление: возвращаем лучший ход из последней завершённой глубины
        for d in range(1, max(1, depth) + 1):
            if deadline is not None and time.monotonic() >= deadline and d > 1:
                break
            try:
                val, mv = _root(d)
                best_val, best_move = val, mv
            except _SearchTimeoutError:
                break
            # найден мат — дальше искать бессмысленно
            if best_val >= 90000:
                break
        return best_move, best_val

    def best_move(self, depth: int = 2,
                  time_limit: float | None = None) -> tuple[int, int, str] | None:
        mv, _score = self.search_best(depth, time_limit)
        return mv

    def analyze_move(self, move: tuple[int, int, str], depth: int = 2,
                     time_limit: float | None = None) -> dict:
        """Оценивает качество хода для стороны, делающей ход в текущей позиции."""
        mover = self.turn
        # оценка позиции до хода (для отображения/эвристик)
        try:
            eval_before = self.evaluate()
            eval_before = eval_before if mover == "w" else -eval_before
        except Exception:  # noqa: BLE001
            eval_before = 0
        best_mv, best_score = self.search_best(depth, time_limit)
        if best_mv is None:
            return {"label": "", "loss": 0, "best": None}
        self.make_move(move)
        try:
            reply_mv, reply_score = self.search_best(max(1, depth - 0), time_limit)
            # reply_score с точки зрения стороны, которая теперь ходит (оппонент)
            played_score = -reply_score
            if reply_mv is None:
                st, _txt = self.status()
                if st == "checkmate":
                    played_score = 100000
                elif st in ("stalemate", "draw"):
                    played_score = 0
        finally:
            self.undo()
        loss = max(0, int(best_score - played_score))
        same = (move[0] == best_mv[0] and move[1] == best_mv[1] and
                (move[2] == best_mv[2] or move[2] in "qrbn" and best_mv[2] in "qrbn"))
        # эвристика "блестящего": лучший ход с форсированным матом или резким выигрышем
        brilliant = False
        if same and best_score >= 90000:
            brilliant = True
        elif same and played_score - eval_before >= 350 and eval_before <= 120 and best_score >= 150:
            brilliant = True
        if brilliant:
            label = "Блестящий ход"
        elif same or loss <= 20:
            label = "Лучший ход" if same else "Отличный ход"
        elif loss <= 60:
            label = "Хороший ход"
        elif loss <= 140:
            label = "Неточность"
        elif loss <= 320:
            label = "Ошибка"
        else:
            label = "Зевок"
        return {
            "label": label,
            "loss": loss,
            "best": best_mv,
            "best_score": int(best_score),
            "played_score": int(played_score),
        }
