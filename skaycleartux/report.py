"""Генерация сводного отчёта о системе (HTML/текст)."""
from __future__ import annotations

import html
import platform
import time
from pathlib import Path

from . import __version__
from . import cleaner
from . import system_tools as st
from .backends import common


def _esc(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def compute_health(metrics: dict | None = None) -> dict:
    """Лёгкая оценка «здоровья» системы по текущим метрикам.

    Возвращает {"score": int, "level": str, "color": str, "tips": [str]}.
    Не выполняет тяжёлых операций (без проверки обновлений/SMART).
    Можно передать уже собранные метрики, чтобы избежать повторного опроса.
    """
    score = 100
    tips: list[str] = []
    metrics = metrics or {}

    try:
        mem = metrics.get("memory")
        total_m, used_m = mem if mem is not None else st.memory_info()
        if total_m > 0:
            mem_pct = used_m / total_m * 100
            if mem_pct >= 92:
                score -= 20
                tips.append(f"Память почти заполнена ({mem_pct:.0f}%). Закройте лишние приложения.")
            elif mem_pct >= 80:
                score -= 10
                tips.append(f"Высокая нагрузка на память ({mem_pct:.0f}%).")
    except Exception:  # noqa: BLE001
        pass

    try:
        disk = metrics.get("disk")
        _total_b, free_b, used_pct = disk if disk is not None else st.disk_usage()
        if used_pct >= 95:
            score -= 30
            tips.append(f"На диске критически мало места (занято {used_pct}%). Освободите место.")
        elif used_pct >= 90:
            score -= 20
            tips.append(f"Диск почти заполнен (занято {used_pct}%). Рекомендуется очистка.")
        elif used_pct >= 80:
            score -= 10
            tips.append(f"Диск заполнен на {used_pct}%.")
        else:
            tips.append(f"Свободно на диске: {cleaner.human(free_b)}.")
    except Exception:  # noqa: BLE001
        pass

    try:
        sensors = metrics.get("sensors")
        temps, _fans = sensors if sensors is not None else st.sensors_info()
        if temps:
            tmax = max(t for _n, t in temps)
            if tmax >= 90:
                score -= 20
                tips.append(f"Очень высокая температура ЦП ({tmax:.0f} °C). Проверьте охлаждение.")
            elif tmax >= 80:
                score -= 10
                tips.append(f"Повышенная температура ЦП ({tmax:.0f} °C).")
    except Exception:  # noqa: BLE001
        pass

    try:
        bat = metrics.get("battery", ...)
        if bat is ...:
            bat = st.battery_info()
        if bat:
            cap = bat.get("capacity")
            try:
                cap_val = int(str(cap).replace("%", "").strip())
            except Exception:  # noqa: BLE001
                cap_val = None
            status = str(bat.get("status", "")).lower()
            if cap_val is not None and cap_val <= 15 and "charg" not in status and "заряд" not in status:
                score -= 10
                tips.append(f"Низкий заряд батареи ({cap_val}%). Подключите питание.")
    except Exception:  # noqa: BLE001
        pass

    try:
        cpu = metrics.get("cpu")
        if cpu is None:
            cpu = st.cpu_percent()
        if cpu >= 95:
            score -= 10
            tips.append(f"ЦП загружен на {cpu:.0f}% прямо сейчас.")
    except Exception:  # noqa: BLE001
        pass

    score = max(0, min(100, score))
    if score >= 85:
        level, color = "Отлично", "#4ade80"
    elif score >= 70:
        level, color = "Хорошо", "#a3e635"
    elif score >= 50:
        level, color = "Есть замечания", "#f5c542"
    else:
        level, color = "Требует внимания", "#ff6b81"

    if not tips:
        tips.append("Критичных проблем по основным метрикам не обнаружено.")
    return {"score": score, "level": level, "color": color, "tips": tips}


def build_report_text() -> str:
    """Текстовый отчёт (быстрый, без сетевых проверок)."""
    lines: list[str] = []
    lines.append(f"SkayClearTux {__version__} — отчёт о системе")
    lines.append(f"Дата: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append(f"ОС: {st.os_pretty_name()}")
    lines.append(f"Ядро: {platform.release()}")
    lines.append(f"Хост: {platform.node()}")
    lines.append(f"Процессор: {st.cpu_model()} ({common.cpu_count()} потоков)")
    lines.append(f"Время работы: {st.uptime()}")
    try:
        total_m, used_m = st.memory_info()
        if total_m > 0:
            lines.append(f"Память: {used_m:.1f} / {total_m:.1f} ГБ ({used_m/total_m*100:.0f}%)")
    except Exception:  # noqa: BLE001
        pass
    try:
        total_b, free_b, pct = st.disk_usage()
        lines.append(f"Диск: занято {pct}%, свободно {cleaner.human(free_b)} из {cleaner.human(total_b)}")
    except Exception:  # noqa: BLE001
        pass
    try:
        temps, fans = st.sensors_info()
        if temps:
            lines.append("Температуры: " + ", ".join(f"{n} {t:.0f}°C" for n, t in temps[:8]))
        if fans:
            lines.append("Вентиляторы: " + ", ".join(f"{n} {v}" for n, v in fans[:6]))
    except Exception:  # noqa: BLE001
        pass
    try:
        bat = st.battery_info()
        if bat:
            lines.append(f"Батарея: {bat.get('capacity', '—')}% ({bat.get('status', '')})")
    except Exception:  # noqa: BLE001
        pass

    health = compute_health()
    lines.append("")
    lines.append(f"Здоровье системы: {health['score']}/100 — {health['level']}")
    for tip in health["tips"]:
        lines.append(f" - {tip}")

    lines.append("")
    lines.append("Диагностика")
    lines.append("-" * 60)
    try:
        for name, text in st.diagnostics():
            lines.append(f"[{name}]")
            lines.append((text or "—").strip())
            lines.append("")
    except Exception as e:  # noqa: BLE001
        lines.append(f"Не удалось собрать диагностику: {e}")

    return "\n".join(lines)


def build_report_html() -> str:
    """HTML-отчёт о системе (удобно открыть и отправить)."""
    health = compute_health()
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    def row(label: str, value: str) -> None:
        rows.append(f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>")

    row("SkayClearTux", __version__)
    row("Дата", now)
    row("ОС", st.os_pretty_name())
    row("Ядро", platform.release())
    row("Хост", platform.node())
    row("Архитектура", platform.machine() or "—")
    row("Процессор", f"{st.cpu_model()} ({common.cpu_count()} потоков)")
    row("Время работы", st.uptime())
    try:
        total_m, used_m = st.memory_info()
        if total_m > 0:
            row("Память", f"{used_m:.1f} / {total_m:.1f} ГБ ({used_m/total_m*100:.0f}%)")
    except Exception:  # noqa: BLE001
        pass
    try:
        total_b, free_b, pct = st.disk_usage()
        row("Диск", f"занято {pct}%, свободно {cleaner.human(free_b)} из {cleaner.human(total_b)}")
    except Exception:  # noqa: BLE001
        pass
    try:
        temps, fans = st.sensors_info()
        if temps:
            row("Температуры", ", ".join(f"{n} {t:.0f}°C" for n, t in temps[:10]))
        if fans:
            row("Вентиляторы", ", ".join(f"{n} {v}" for n, v in fans[:8]))
    except Exception:  # noqa: BLE001
        pass
    try:
        bat = st.battery_info()
        if bat:
            row("Батарея", f"{bat.get('capacity', '—')}% ({bat.get('status', '')})")
    except Exception:  # noqa: BLE001
        pass

    tips_html = "".join(f"<li>{_esc(t)}</li>" for t in health["tips"])

    diag_sections = []
    try:
        for name, text in st.diagnostics():
            diag_sections.append(
                f"<section><h3>{_esc(name)}</h3><pre>{_esc((text or '—').strip())}</pre></section>"
            )
    except Exception as e:  # noqa: BLE001
        diag_sections.append(f"<p>Не удалось собрать диагностику: {_esc(e)}</p>")

    hw_sections = []
    try:
        for name, text in st.hardware_sections():
            body = (text or "—").strip()
            if len(body) > 6000:
                body = body[:6000] + "\n…"
            hw_sections.append(
                f"<section><h3>{_esc(name)}</h3><pre>{_esc(body)}</pre></section>"
            )
    except Exception:  # noqa: BLE001
        pass

    net_html = ""
    try:
        info = st.network_info()
        net_parts = [f"Хост: {info.get('hostname', '—')}"]
        if info.get("route"):
            net_parts.append(f"Маршрут: {info['route']}")
        if info.get("dns"):
            net_parts.append("DNS: " + ", ".join(info.get("dns", [])[:6]))
        for iface in info.get("interfaces", [])[:12]:
            addrs = ", ".join(iface.get("addrs", [])[:4]) or "—"
            net_parts.append(f"{iface.get('name','?')}: {addrs} ({iface.get('state','')})")
        net_html = "<pre>" + _esc("\n".join(net_parts)) + "</pre>"
    except Exception:  # noqa: BLE001
        net_html = "<p>—</p>"

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Отчёт SkayClearTux — {_esc(now)}</title>
<style>
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #111827; background: #f8fafc; }}
 h1 {{ margin: 0 0 4px; }} .sub {{ color: #475569; margin-bottom: 20px; }}
 .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px 18px; margin: 14px 0; }}
 .score {{ font-size: 28px; font-weight: 800; color: {health['color']}; }}
 table {{ border-collapse: collapse; width: 100%; }} th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #eef2f7; vertical-align: top; }}
 th {{ width: 220px; color: #334155; }}
 pre {{ white-space: pre-wrap; word-break: break-word; background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; font-size: 12px; }}
 h2 {{ margin-top: 28px; }} h3 {{ margin: 0 0 8px; }}
 ul {{ margin: 8px 0 0 20px; }}
</style>
</head>
<body>
<h1>SkayClearTux — отчёт о системе</h1>
<div class="sub">Сгенерировано: {_esc(now)}</div>
<div class="card">
  <div class="score">Здоровье: {health['score']}/100 — {_esc(health['level'])}</div>
  <ul>{tips_html}</ul>
</div>
<div class="card">
  <h2>Обзор</h2>
  <table>{''.join(rows)}</table>
</div>
<h2>Сеть</h2>
<div class="card">{net_html}</div>
<h2>Диагностика</h2>
{''.join(diag_sections) or '<p>—</p>'}
<h2>Оборудование</h2>
{''.join(hw_sections) or '<p>—</p>'}
</body>
</html>
"""


def default_report_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = Path.home() / "Documents"
    if not base.exists():
        base = Path.home()
    return base / f"skaycleartux-report-{stamp}.html"
