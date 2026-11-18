"""Темы оформления SkayClearTux. Каждая тема — набор цветов + генератор QSS с градиентами."""
from __future__ import annotations

# Ключи: bg, sidebar, card, card2, border, text, dim, accent, accent_text,
#        hover, danger, success, board_light, board_dark
THEMES: dict[str, dict[str, str]] = {
    "Полночь": {
        "bg": "#0f1117", "sidebar": "#151925", "card": "#1a1f2e", "card2": "#232a3d",
        "border": "#2a3350", "text": "#e6ebf5", "dim": "#8b95ad", "accent": "#4fc3f7",
        "accent_text": "#06202b", "hover": "#232a3d", "danger": "#ff6b81",
        "success": "#4ade80", "board_light": "#d7dde8", "board_dark": "#5b6b8c",
    },
    "Дракула": {
        "bg": "#21222c", "sidebar": "#282a36", "card": "#282a36", "card2": "#343746",
        "border": "#44475a", "text": "#f8f8f2", "dim": "#a9abc4", "accent": "#bd93f9",
        "accent_text": "#1a1026", "hover": "#343746", "danger": "#ff5555",
        "success": "#50fa7b", "board_light": "#e9e9e9", "board_dark": "#6272a4",
    },
    "Nord": {
        "bg": "#242933", "sidebar": "#2e3440", "card": "#2e3440", "card2": "#3b4252",
        "border": "#434c5e", "text": "#eceff4", "dim": "#9aa5b5", "accent": "#88c0d0",
        "accent_text": "#10222b", "hover": "#3b4252", "danger": "#bf616a",
        "success": "#a3be8c", "board_light": "#e5e9f0", "board_dark": "#5e81ac",
    },
    "Gruvbox": {
        "bg": "#1d2021", "sidebar": "#282828", "card": "#282828", "card2": "#32302f",
        "border": "#3c3836", "text": "#ebdbb2", "dim": "#a89984", "accent": "#d79921",
        "accent_text": "#231b00", "hover": "#32302f", "danger": "#fb4934",
        "success": "#b8bb26", "board_light": "#ebdbb2", "board_dark": "#a89984",
    },
    "Роза": {
        "bg": "#191019", "sidebar": "#221524", "card": "#26182b", "card2": "#341f3a",
        "border": "#4a2c52", "text": "#f6e8f6", "dim": "#b495bd", "accent": "#ff79c6",
        "accent_text": "#2a0a1d", "hover": "#341f3a", "danger": "#ff5555",
        "success": "#69ff94", "board_light": "#efe1ef", "board_dark": "#8f5f9c",
    },
    "Океан": {
        "bg": "#0a1620", "sidebar": "#0e1f2e", "card": "#102736", "card2": "#16384d",
        "border": "#1f4d66", "text": "#e0f2ff", "dim": "#7fa6bd", "accent": "#2ec4b6",
        "accent_text": "#04241f", "hover": "#16384d", "danger": "#ef476f",
        "success": "#06d6a0", "board_light": "#dbe9f2", "board_dark": "#3d7ea6",
    },
    "Светлая": {
        "bg": "#eef1f6", "sidebar": "#ffffff", "card": "#ffffff", "card2": "#f4f6fb",
        "border": "#d7dde8", "text": "#1b2333", "dim": "#69748c", "accent": "#2f6fed",
        "accent_text": "#ffffff", "hover": "#eef2fb", "danger": "#e5484d",
        "success": "#2f9e44", "board_light": "#f0d9b5", "board_dark": "#b58863",
    },
    "Аврора": {
        "bg": "#071019", "sidebar": "#0b1624", "card": "#0f1f31", "card2": "#152a40",
        "border": "#1f3d57", "text": "#eaf6ff", "dim": "#8fb3c9", "accent": "#7c5cff",
        "accent_text": "#f4f0ff", "hover": "#17314a", "danger": "#ff5d8f",
        "success": "#3ddc97", "board_light": "#dcecff", "board_dark": "#355d86",
    },
    "Янтарь": {
        "bg": "#14110b", "sidebar": "#1b1710", "card": "#221c13", "card2": "#2d2518",
        "border": "#4a3a22", "text": "#fff3d9", "dim": "#c2a97a", "accent": "#ffb020",
        "accent_text": "#2a1c00", "hover": "#332918", "danger": "#ff6b6b",
        "success": "#7bd88f", "board_light": "#f3e2c7", "board_dark": "#8a6a3d",
    },
}

DEFAULT_THEME = "Полночь"


# --------------------------------------------------------------------------- #
def _clamp(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def shade(hex_color: str, factor: float) -> str:
    """factor > 1 — светлее, < 1 — темнее."""
    r, g, b = _rgb(hex_color)
    if factor >= 1:
        r = r + (255 - r) * (factor - 1)
        g = g + (255 - g) * (factor - 1)
        b = b + (255 - b) * (factor - 1)
    else:
        r, g, b = r * factor, g * factor, b * factor
    return f"#{_clamp(r):02x}{_clamp(g):02x}{_clamp(b):02x}"


def mix(a: str, b: str, t: float) -> str:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return (f"#{_clamp(ra + (rb - ra) * t):02x}"
            f"{_clamp(ga + (gb - ga) * t):02x}"
            f"{_clamp(ba + (bb - ba) * t):02x}")



def build_qss(c: dict[str, str]) -> str:
    bg_top = shade(c["bg"], 1.12)
    bg_bot = shade(c["bg"], 0.88)
    side_top = shade(c["sidebar"], 1.08)
    side_bot = shade(c["sidebar"], 0.88)
    card_top = shade(c["card"], 1.08)
    card_bot = shade(c["card"], 0.93)
    acc_top = shade(c["accent"], 1.22)
    acc_bot = shade(c["accent"], 0.82)
    hover_bg = mix(c["hover"], c["accent"], 0.10)
    dark = c["accent_text"]
    border_soft = mix(c["border"], c["accent"], 0.12)
    return f"""
* {{
    font-family: "Inter", "Noto Sans", "Ad Sans", "DejaVu Sans", sans-serif;
    outline: none;
}}
QWidget {{
    color: {c['text']};
    font-size: 14px;
}}
QMainWindow, QDialog {{ background-color: {c['bg']}; }}
#Root {{
    background: qlineargradient(x1:0, y1:0, x2:0.35, y2:1,
        stop:0 {bg_top}, stop:0.45 {c['bg']}, stop:1 {bg_bot});
}}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

/* --- боковая панель --- */
#Sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0.2, y2:1,
        stop:0 {side_top}, stop:1 {side_bot});
    border-right: 1px solid {border_soft};
}}
#BrandTitle {{ font-size: 20px; font-weight: 800; color: {c['text']}; letter-spacing: 0.2px; }}
#BrandSub {{ font-size: 11px; color: {c['dim']}; }}
QPushButton#NavSection {{
    text-align: left;
    background: transparent;
    border: none;
    font-size: 10px; font-weight: 800; color: {c['dim']};
    letter-spacing: 1.6px; padding: 12px 6px 4px 6px;
}}
QPushButton#NavSection:hover {{ color: {c['accent']}; }}

QPushButton#Help {{
    background: {c['card2']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 0px;
    font-weight: 800;
    color: {c['accent']};
}}
QPushButton#Help:hover {{ border-color: {c['accent']}; background: {hover_bg}; }}

QPushButton#Nav {{
    text-align: left;
    padding: 10px 14px;
    border: 1px solid transparent;
    border-left: 3px solid transparent;
    border-radius: 12px;
    color: {c['dim']};
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#Nav:hover {{
    background-color: {hover_bg};
    color: {c['text']};
    border-color: {mix(c['border'], c['accent'], 0.18)};
}}
QPushButton#Nav:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {mix(c['accent'], c['card'], 0.18)}, stop:1 {mix(c['accent'], c['card2'], 0.32)});
    color: {c['text']};
    border: 1px solid {mix(c['accent'], c['border'], 0.35)};
    border-left: 3px solid {c['accent']};
    font-weight: 700;
}}

/* --- карточки --- */
#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1,
        stop:0 {card_top}, stop:1 {card_bot});
    border: 1px solid {mix(c['border'], c['accent'], 0.08)};
    border-top-color: {mix(c['border'], c['text'], 0.06)};
    border-radius: 18px;
}}
#Hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {mix(c['accent'], c['card'], 0.22)}, stop:0.55 {card_top}, stop:1 {card_bot});
    border: 1px solid {mix(c['accent'], c['border'], 0.30)};
    border-radius: 22px;
}}
#CardTitle {{ font-size: 15px; font-weight: 700; color: {c['text']}; }}
#CardSub {{ font-size: 12px; color: {c['dim']}; }}
#H1 {{ font-size: 28px; font-weight: 800; color: {c['text']}; }}
#H2 {{ font-size: 19px; font-weight: 700; color: {c['text']}; }}
#Dim {{ color: {c['dim']}; }}
#Metric {{ font-size: 30px; font-weight: 800; color: {c['accent']}; }}
#HeroMetric {{ font-size: 34px; font-weight: 900; color: {c['accent']}; }}
#MetricLabel {{ font-size: 12px; color: {c['dim']}; }}
#Badge {{
    background: {mix(c['accent'], c['card2'], 0.18)};
    color: {c['text']};
    border: 1px solid {mix(c['accent'], c['border'], 0.35)};
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 700;
    font-size: 12px;
}}
#Bar {{ border-radius: 2px; }}

/* --- кнопки --- */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {shade(c['card2'], 1.10)}, stop:1 {c['card2']});
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {hover_bg};
    border-color: {mix(c['accent'], c['border'], 0.55)};
}}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['dim']}; border-color: {c['border']}; background: {shade(c['card2'], 0.98)}; }}
QPushButton#Accent {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {acc_top}, stop:1 {acc_bot});
    color: {dark};
    border: 1px solid {mix(c['accent'], c['border'], 0.2)};
    font-weight: 700;
}}
QPushButton#Accent:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {shade(c['accent'], 1.28)}, stop:1 {shade(c['accent'], 0.92)});
}}
QPushButton#Danger {{
    background: {mix(c['danger'], c['card'], 0.12)};
    color: {c['danger']};
    border: 1px solid {mix(c['danger'], c['border'], 0.45)};
}}
QPushButton#Danger:hover {{ background: {mix(c['danger'], c['card'], 0.20)}; }}

/* --- поля, комбо, чекбоксы --- */
QComboBox, QLineEdit, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {shade(c['card2'], 0.98)};
    border: 1px solid {c['border']};
    border-radius: 11px;
    padding: 7px 12px;
    color: {c['text']};
}}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover,
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {mix(c['accent'], c['border'], 0.6)};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent']};
    selection-color: {dark};
    padding: 4px;
}}
QCheckBox {{ spacing: 9px; color: {c['text']}; }}
QCheckBox::indicator {{
    width: 20px; height: 20px; border-radius: 7px;
    border: 1px solid {c['border']}; background-color: {c['card2']};
}}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {acc_top}, stop:1 {acc_bot});
    border-color: {c['accent']};
}}

/* --- прогресс --- */
QProgressBar {{
    background-color: {shade(c['card2'], 0.92)};
    border: 1px solid {c['border']};
    border-radius: 8px; height: 16px; text-align: center;
    color: {c['text']}; font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {acc_bot}, stop:0.5 {c['accent']}, stop:1 {acc_top});
    border-radius: 7px;
}}

/* --- таблицы --- */
QTableWidget {{
    background-color: {c['card']};
    alternate-background-color: {shade(c['card'], 0.96)};
    border: 1px solid {c['border']};
    border-radius: 14px;
    gridline-color: {shade(c['border'], 0.85)};
    selection-background-color: {mix(c['accent'], c['card'], 0.35)};
    selection-color: {c['text']};
}}
QHeaderView::section {{
    background-color: {shade(c['card'], 1.08)};
    color: {c['dim']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 8px 10px;
    font-weight: 700;
}}

/* --- прокрутка --- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {mix(c['border'], c['accent'], 0.15)};
    border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {mix(c['accent'], c['border'], 0.45)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {mix(c['border'], c['accent'], 0.15)};
    border-radius: 5px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {mix(c['accent'], c['border'], 0.45)}; }}

QToolTip {{
    background-color: {c['card']};
    color: {c['text']};
    border: 1px solid {mix(c['accent'], c['border'], 0.35)};
    padding: 6px 8px;
    border-radius: 8px;
}}
QListWidget {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 4px;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 8px; }}
QListWidget::item:selected {{
    background-color: {mix(c['accent'], c['card'], 0.30)};
    color: {c['text']};
}}

/* --- вкладки --- */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 14px;
    background: {c['card']};
    top: -1px;
}}
QTabBar::tab {{
    background: {c['card2']};
    color: {c['dim']};
    border: 1px solid {c['border']};
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 8px 18px;
    margin-right: 3px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {c['card']};
    color: {c['accent']};
    border-color: {mix(c['accent'], c['border'], 0.35)};
}}
QTabBar::tab:hover {{ color: {c['text']}; }}

/* --- баннер обновления --- */
#Banner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {mix(c['accent'], c['card'], 0.28)}, stop:1 {c['card']});
    border-bottom: 1px solid {mix(c['accent'], c['border'], 0.3)};
}}
#BannerText {{ font-size: 13px; font-weight: 600; color: {c['text']}; }}

/* --- палитра команд (Ctrl+K) --- */
#Palette {{ background-color: {c['bg']}; }}
#PaletteList {{
    background-color: {c['card']};
    border: 1px solid {mix(c['accent'], c['border'], 0.3)};
    border-radius: 14px;
    padding: 6px;
    font-size: 14px;
}}
#PaletteList::item {{ padding: 9px 12px; border-radius: 8px; color: {c['text']}; }}
#PaletteList::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {mix(c['accent'], c['card'], 0.25)}, stop:1 {mix(c['accent'], c['card2'], 0.35)});
    color: {c['text']};
    border: 1px solid {mix(c['accent'], c['border'], 0.35)};
}}

/* --- меню трея и контекстные меню --- */
QMenu {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 8px; color: {c['text']}; }}
QMenu::item:selected {{
    background-color: {mix(c['accent'], c['card'], 0.30)};
    color: {c['text']};
}}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}
"""
