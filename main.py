"""Bokbut_it (복붙잇) - Smart Work Widget (Modern Minimal White & Skyblue iOS Style)."""

from __future__ import annotations

import ctypes
from datetime import datetime
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
import uuid
import webbrowser
import winreg
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageTk
import pystray

from shortcut_engine import AVAILABLE_TAGS, extract_input_fields, render_template
from storage import load_data, save_data

# Modern Minimal White & Skyblue (Apple iOS Style) Palette
BG_MAIN = "#FFFFFF"
BG_HEADER = "#F8FAFC"
BG_SEGMENT_TRACK = "#F3F4F6"
BG_SEGMENT_ACTIVE = "#FFFFFF"
BG_CARD = "#FFFFFF"
BG_CARD_HOVER = "#F9FAFB"
BG_CARD_ACTIVE = "#EBF3FE"
BG_CARD_EXPANDED = "#F9FAFB"
BG_INPUT = "#FFFFFF"
BG_CHIP = "#F3F4F6"
BG_SUBTLE = "#F3F4F6"
BG_TOAST = "#1F2937"

BORDER_WINDOW = "#E5E7EB"
BORDER_CARD = "#E5E7EB"
BORDER_CARD_ACTIVE = "#D3E3FD"
ACCENT_BLUE = "#0066FF"
ACCENT_BLUE_HOVER = "#0052CC"
SCROLL_THUMB = "#D1D5DB"

TEXT_PRIMARY = "#222222"
TEXT_SECONDARY = "#6B7280"
TEXT_SUCCESS = "#0066FF"
TEXT_DANGER = "#DC2626"
TEXT_TOAST = "#FFFFFF"

ALPHA_LEVELS = (0.93, 0.78, 1.0)
ALPHA_DEFAULT = 0.93

FONT_FAMILY = "맑은 고딕"
DEFAULT_WIDTH = 360
DEFAULT_HEIGHT = 540
MIN_WIDTH = 300
MIN_HEIGHT = 380
SHADE_HEIGHT = 38

RUN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "Bokbut_it"
APP_VERSION = "v1.0"
SUPPORT_URL = "https://buymeacoffee.com/devom"

SINGLE_INSTANCE_MUTEX = "Local\\Bokbut_it_SingleInstance_Mutex"
WAKEUP_EVENT_NAME = "Local\\Bokbut_it_Wakeup_Event"


class SingleInstanceGuard:
    """Prevent duplicate app instances and wake up the existing window on relaunch."""

    def __init__(self) -> None:
        self._kernel32 = ctypes.windll.kernel32
        self._mutex_handle: int | None = None
        self._event_handle: int | None = None
        self._stopped = False

    def acquire(self) -> bool:
        """Return True if this is the primary instance, or signal existing one and return False."""
        mutex = self._kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
        last_err = self._kernel32.GetLastError()
        if last_err == 183:  # ERROR_ALREADY_EXISTS
            if mutex:
                self._kernel32.CloseHandle(mutex)
            ev = self._kernel32.OpenEventW(0x0002, False, WAKEUP_EVENT_NAME)
            if ev:
                self._kernel32.SetEvent(ev)
                self._kernel32.CloseHandle(ev)
            return False

        self._mutex_handle = mutex
        self._event_handle = self._kernel32.CreateEventW(None, False, False, WAKEUP_EVENT_NAME)
        return True

    def start_listener(self, on_wakeup: Callable[[], None]) -> None:
        """Listen on a daemon thread for wakeup signals from secondary launches."""
        if not self._event_handle:
            return

        def _wait_loop() -> None:
            while not self._stopped:
                res = self._kernel32.WaitForSingleObject(self._event_handle, 500)
                if self._stopped:
                    break
                if res == 0:  # WAIT_OBJECT_0
                    on_wakeup()

        threading.Thread(target=_wait_loop, daemon=True).start()

    def release(self) -> None:
        self._stopped = True
        if self._event_handle:
            self._kernel32.SetEvent(self._event_handle)
            self._kernel32.CloseHandle(self._event_handle)
            self._event_handle = None
        if self._mutex_handle:
            self._kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None

FRIENDLY_TAG_LABELS: dict[str, str] = {
    "{오늘날짜}": "📅 오늘날짜",
    "{오늘날짜_간략}": "📅 간략날짜",
    "{현재시간}": "🕒 현재시간",
    "{요일}": "📆 요일",
    "{클립보드}": "📋 클립보드",
    "{클립보드_숫자만}": "🔢 숫자만",
    "{입력:항목명}": "✏️ 실행시 입력",
}


def _draw_rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    fill: str,
    outline: str = "",
    width: int = 1,
) -> int:
    """Draw a smooth rounded rectangle on a tk.Canvas."""
    r = min(radius, max(0.0, (x2 - x1) / 2), max(0.0, (y2 - y1) / 2))
    points = [
        x1 + r, y1,
        x1 + r, y1,
        x2 - r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(
        points,
        smooth=True,
        splinesteps=12,
        fill=fill,
        outline=outline,
        width=width if outline else 0,
    )


def _get_tag_tooltip_text(tag: str) -> str:
    """Return a user-friendly live preview tooltip for each shortcut tag."""
    now = datetime.now()
    weekdays = ("월", "화", "수", "목", "금", "토", "일")
    previews: dict[str, str] = {
        "{오늘날짜}": f"이 양식으로 들어가요 → {now.strftime('%Y-%m-%d')} (YYYY-MM-DD)",
        "{오늘날짜_간략}": f"이 양식으로 들어가요 → {now.strftime('%y.%m.%d')} (YY.MM.DD)",
        "{현재시간}": f"이 양식으로 들어가요 → {now.strftime('%H:%M')} (24시간제)",
        "{요일}": f"이 양식으로 들어가요 → {weekdays[now.weekday()]} (한글 요일)",
        "{클립보드}": "복사해 둔 텍스트가 그대로 들어가요",
        "{클립보드_숫자만}": "복사한 값에서 숫자만 추출해요 (예: 01012345678)",
        "{입력:항목명}": "실행할 때 직접 값을 입력하는 팝업이 떠요",
    }
    return previews.get(tag, tag)


class HoverTooltip:
    """Lightweight themed speech-bubble tooltip shown on widget hover."""

    def __init__(self, widget: tk.Widget, text_fn: Callable[[], str]) -> None:
        self._widget = widget
        self._text_fn = text_fn
        self._tip_win: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._schedule_show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress-1>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule_show(self, _event: tk.Event[Any]) -> None:
        self._cancel_timer()
        self._after_id = self._widget.after(180, self._show)

    def _cancel_timer(self) -> None:
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if not self._widget.winfo_exists():
            return
        self._destroy_tip()

        tip = tk.Toplevel(self._widget)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=BG_TOAST, padx=1, pady=1)

        tk.Label(
            tip,
            text=self._text_fn(),
            bg=BG_TOAST,
            fg=TEXT_TOAST,
            font=(FONT_FAMILY, 8),
            padx=8,
            pady=4,
        ).pack()

        tip.update_idletasks()
        wx = self._widget.winfo_rootx()
        wy = self._widget.winfo_rooty()
        th = tip.winfo_reqheight()

        x = wx
        y = wy - th - 6 if wy - th - 6 > 0 else wy + self._widget.winfo_height() + 6
        tip.geometry(f"+{x}+{y}")
        tip.deiconify()
        tip.lift()
        self._tip_win = tip

    def _destroy_tip(self) -> None:
        if self._tip_win is not None:
            try:
                self._tip_win.destroy()
            except tk.TclError:
                pass
            self._tip_win = None

    def _hide(self, _event: tk.Event[Any] | None = None) -> None:
        self._cancel_timer()
        self._destroy_tip()


def _enable_windows_dpi_awareness() -> None:
    """Improve font crispness on Windows high-DPI displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _resolve_font_family(root: tk.Tk) -> str:
    """Use Pretendard if installed, otherwise fall back to 맑은 고딕."""
    try:
        if "Pretendard" in tkfont.families(root):
            return "Pretendard"
    except Exception:
        pass
    return "맑은 고딕"


def _get_resource_path(relative_path: str) -> Path:
    """Resolve bundled resource path for both dev and PyInstaller --onefile builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def create_tray_icon_image() -> Image.Image:
    """Load assets/Bokbut_it.ico at native resolution or fall back to generated icon."""
    ico_path = _get_resource_path("assets/Bokbut_it.ico")
    if ico_path.exists():
        try:
            with Image.open(ico_path) as ico_img:
                return ico_img.convert("RGBA")
        except Exception:
            pass

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded white card with cool-gray border
    draw.rounded_rectangle([4, 4, 59, 59], radius=14, fill="#FFFFFF", outline="#D1D5DB", width=2)
    # Soft skyblue header pill
    draw.rounded_rectangle([12, 14, 51, 28], radius=6, fill="#EBF3FE")
    # Royal blue accent dot & lines
    draw.ellipse([16, 18, 22, 24], fill="#0066FF")
    draw.line([(27, 21), (45, 21)], fill="#0066FF", width=3)
    draw.line([(14, 37), (49, 37)], fill="#222222", width=3)
    draw.line([(14, 46), (38, 46)], fill="#6B7280", width=3)
    return img


def _get_autostart_command() -> str:
    """Return the Windows Run registry command for the current script or exe."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def _is_autostart_enabled() -> bool:
    """Check whether Bokbut_it is registered in Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
    except OSError:
        return False


def _set_autostart(enabled: bool) -> bool:
    """Register or remove Bokbut_it from HKCU Run startup registry."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, _get_autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def _apply_taskbar_style(root: tk.Tk) -> None:
    """Ensure overrideredirect(True) window appears in the Windows taskbar when visible."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        gwl_exstyle = -20
        ws_ex_appwindow = 0x00040000
        ws_ex_toolwindow = 0x00000080
        style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
        new_style = (style & ~ws_ex_toolwindow) | ws_ex_appwindow
        if style != new_style:
            ctypes.windll.user32.SetWindowLongW(hwnd, gwl_exstyle, new_style)
            root.withdraw()
            root.after(10, root.deiconify)
    except Exception:
        pass


class RoundedPrimaryButton(tk.Canvas):
    """Full-width iOS-style rounded primary blue button."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        height: int = 42,
        bg_parent: str = BG_MAIN,
    ) -> None:
        super().__init__(
            parent,
            height=height,
            bg=bg_parent,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._hovered = False
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e: tk.Event[Any]) -> None:
        self._hovered = True
        self._redraw()

    def _on_leave(self, _e: tk.Event[Any]) -> None:
        self._hovered = False
        self._redraw()

    def _on_click(self, _e: tk.Event[Any]) -> None:
        self._command()

    def _redraw(self) -> None:
        self.delete("all")
        w = max(40, self.winfo_width())
        h = max(24, self.winfo_height())
        fill = ACCENT_BLUE_HOVER if self._hovered else ACCENT_BLUE
        _draw_rounded_rect(self, 1, 1, w - 2, h - 2, radius=12, fill=fill)
        self.create_text(
            w // 2,
            h // 2,
            text=self._text,
            fill="#FFFFFF",
            font=(FONT_FAMILY, 10, "bold"),
        )


class SegmentControl(tk.Canvas):
    """iOS-style segmented control for 3-tab navigation."""

    def __init__(
        self,
        parent: tk.Widget,
        items: list[tuple[str, str]],
        on_select: Callable[[str], None],
        bg_parent: str = BG_MAIN,
    ) -> None:
        super().__init__(
            parent,
            height=36,
            bg=bg_parent,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._items = items
        self._on_select = on_select
        self._active_key = items[0][0]
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_click)

    def set_active(self, key: str) -> None:
        self._active_key = key
        self._redraw()

    def _on_click(self, event: tk.Event[Any]) -> None:
        w = max(1, self.winfo_width())
        seg_w = w / len(self._items)
        idx = min(len(self._items) - 1, max(0, int(event.x // seg_w)))
        key = self._items[idx][0]
        self._on_select(key)

    def _redraw(self) -> None:
        self.delete("all")
        w = max(120, self.winfo_width())
        h = max(28, self.winfo_height())
        _draw_rounded_rect(self, 1, 1, w - 2, h - 2, radius=10, fill=BG_SEGMENT_TRACK)

        pad = 3
        seg_w = (w - pad * 2) / len(self._items)
        for idx, (key, label) in enumerate(self._items):
            x1 = pad + idx * seg_w
            x2 = x1 + seg_w
            is_active = key == self._active_key
            if is_active:
                _draw_rounded_rect(
                    self,
                    x1 + 1,
                    pad + 1,
                    x2 - 1,
                    h - pad - 1,
                    radius=8,
                    fill=BG_SEGMENT_ACTIVE,
                    outline=BORDER_CARD,
                    width=1,
                )
            self.create_text(
                (x1 + x2) / 2,
                h / 2,
                text=label,
                fill=ACCENT_BLUE if is_active else TEXT_SECONDARY,
                font=(FONT_FAMILY, 9, "bold" if is_active else "normal"),
            )


class PillItemCard(tk.Canvas):
    """Minimalist iOS-style rounded pill card with click-to-copy/open and feedback."""

    HEIGHT = 46

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        is_expanded: bool,
        on_copy: Callable[[], None],
        on_toggle: Callable[[], None],
        kind: str = "text",
        on_drag_start: Callable[[PillItemCard, int], None] | None = None,
        on_drag_move: Callable[[int], None] | None = None,
        on_drag_end: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            height=self.HEIGHT,
            bg=BG_MAIN,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._title = title
        self._is_expanded = is_expanded
        self._kind = kind
        self._on_copy = on_copy
        self._on_toggle = on_toggle
        self._on_drag_start = on_drag_start
        self._on_drag_move = on_drag_move
        self._on_drag_end = on_drag_end
        self._hovered = False
        self._copied = False
        self._reset_after_id: str | None = None
        self._long_press_id: str | None = None
        self._press_x = 0
        self._press_y_root = 0
        self._dragging = False

        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_or_right)
        self.bind("<Button-3>", self._on_double_or_right)

    def _on_enter(self, _e: tk.Event[Any]) -> None:
        self._hovered = True
        self._redraw()

    def _on_leave(self, _e: tk.Event[Any]) -> None:
        self._hovered = False
        self._redraw()

    def _cancel_long_press(self) -> None:
        if self._long_press_id is not None:
            try:
                self.after_cancel(self._long_press_id)
            except tk.TclError:
                pass
            self._long_press_id = None

    def _on_press(self, event: tk.Event[Any]) -> None:
        self._press_x = event.x
        self._press_y_root = event.y_root
        self._dragging = False
        self._cancel_long_press()
        if self._on_drag_start is not None and event.x > 34:
            self._long_press_id = self.after(260, self._activate_long_press)

    def _activate_long_press(self) -> None:
        self._long_press_id = None
        if not self.winfo_exists():
            return
        self._dragging = True
        self.configure(cursor="fleur")
        self._redraw()
        if self._on_drag_start is not None:
            self._on_drag_start(self, self._press_y_root)

    def _on_drag_motion(self, event: tk.Event[Any]) -> None:
        if self._dragging:
            if self._on_drag_move is not None:
                self._on_drag_move(event.y_root)
            return
        # If user moves mouse significantly before 260ms, cancel long-press
        if abs(event.y_root - self._press_y_root) > 8:
            self._cancel_long_press()

    def _on_release(self, _event: tk.Event[Any]) -> None:
        self._cancel_long_press()
        self.configure(cursor="hand2")
        if self._dragging:
            self._dragging = False
            self._redraw()
            if self._on_drag_end is not None:
                self._on_drag_end()
            return
        if self._press_x <= 34:
            self._on_toggle()
        else:
            self._on_copy()

    def _on_double_or_right(self, _e: tk.Event[Any]) -> str:
        self._on_toggle()
        return "break"

    def trigger_copied_feedback(self) -> None:
        """Turn card soft skyblue with royal blue checkmark for ~0.9s."""
        if self._reset_after_id is not None:
            self.after_cancel(self._reset_after_id)
        self._copied = True
        self._redraw()
        self._reset_after_id = self.after(900, self._reset_copied)

    def _reset_copied(self) -> None:
        self._reset_after_id = None
        if not self.winfo_exists():
            return
        self._copied = False
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w = max(120, self.winfo_width())
        h = self.HEIGHT

        if self._dragging:
            fill = BG_CARD_ACTIVE
            outline = ACCENT_BLUE
            outline_w = 2
        elif self._copied:
            fill = BG_CARD_ACTIVE
            outline = BORDER_CARD_ACTIVE
            outline_w = 1
        elif self._hovered:
            fill = BG_CARD_HOVER
            outline = BORDER_CARD
            outline_w = 1
        else:
            fill = BG_CARD
            outline = BORDER_CARD
            outline_w = 1

        _draw_rounded_rect(
            self, 1, 1, w - 2, h - 2, radius=12, fill=fill, outline=outline, width=outline_w
        )

        # Crisp vector expand/collapse chevron on the left
        cy = h / 2
        if self._is_expanded:
            self.create_oval(9, cy - 10, 29, cy + 10, fill=BG_CARD_ACTIVE, outline="")
            self.create_line(
                14, cy - 2,
                19, cy + 3,
                24, cy - 2,
                fill=ACCENT_BLUE,
                width=2,
                capstyle="round",
                joinstyle="round",
            )
        else:
            self.create_oval(9, cy - 10, 29, cy + 10, fill=BG_SUBTLE, outline="")
            self.create_line(
                17, cy - 5,
                22, cy,
                17, cy + 5,
                fill=TEXT_SECONDARY,
                width=2,
                capstyle="round",
                joinstyle="round",
            )

        # Title text (truncated if too long)
        max_chars = max(10, int((w - 76) / 11))
        display_title = (
            self._title if len(self._title) <= max_chars else self._title[: max_chars - 1] + "…"
        )
        self.create_text(
            36,
            h / 2,
            text=display_title,
            anchor="w",
            fill=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10),
        )

        # Right icon: checkmark when active, subtle link arrow when idle link card
        if self._copied:
            self.create_text(
                w - 18,
                h / 2,
                text="↗" if self._kind == "link" else "✓",
                fill=ACCENT_BLUE,
                font=(FONT_FAMILY, 11, "bold"),
            )
        elif self._kind == "link":
            self.create_text(
                w - 18,
                h / 2,
                text="↗",
                fill=TEXT_SECONDARY,
                font=(FONT_FAMILY, 10, "bold"),
            )


class MinimalScrollIndicator(tk.Canvas):
    """Hidden-by-default minimal 4px scroll indicator for smooth wheel scrolling."""

    def __init__(
        self,
        parent: tk.Widget,
        bg: str = BG_MAIN,
        thumb_color: str = SCROLL_THUMB,
        on_scroll_to: Callable[[float], None] | None = None,
        on_step: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent, width=6, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._thumb_color = thumb_color
        self._on_scroll_to = on_scroll_to
        self._on_step = on_step
        self._first = 0.0
        self._last = 1.0
        self._thumb_top = 0
        self._thumb_bottom = 0
        self._dragging = False
        self._drag_offset = 0
        self._hold_y = 0
        self._repeat_id: str | None = None

        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_fraction(self, first: str | float, last: str | float) -> None:
        self._first = float(first)
        self._last = float(last)
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        if self._first <= 0.0 and self._last >= 1.0:
            self._thumb_top = 0
            self._thumb_bottom = 0
            return
        h = self.winfo_height()
        if h <= 4:
            return
        top = max(2, int(self._first * h))
        bottom = min(h - 2, max(top + 18, int(self._last * h)))
        self._thumb_top = top
        self._thumb_bottom = bottom
        self.create_rectangle(2, top, 5, bottom, fill=self._thumb_color, outline="")

    def _on_press(self, event: tk.Event[Any]) -> None:
        if self._first <= 0.0 and self._last >= 1.0:
            return
        if self._thumb_top <= event.y <= self._thumb_bottom:
            self._dragging = True
            self._drag_offset = event.y - self._thumb_top
        else:
            self._dragging = False
            self._hold_y = event.y
            self._step_toward_hold()
            self._schedule_repeat(delay=160)

    def _on_drag(self, event: tk.Event[Any]) -> None:
        if not self._dragging or self._on_scroll_to is None:
            self._hold_y = event.y
            return
        h = max(1, self.winfo_height())
        new_top = max(0, min(h - (self._thumb_bottom - self._thumb_top), event.y - self._drag_offset))
        self._on_scroll_to(new_top / h)

    def _on_release(self, _event: tk.Event[Any]) -> None:
        self._dragging = False
        if self._repeat_id is not None:
            self.after_cancel(self._repeat_id)
            self._repeat_id = None

    def _step_toward_hold(self) -> bool:
        if self._on_step is None:
            return False
        if self._hold_y < self._thumb_top:
            self._on_step(-2)
            return True
        if self._hold_y > self._thumb_bottom:
            self._on_step(2)
            return True
        return False

    def _schedule_repeat(self, delay: int = 45) -> None:
        if self._repeat_id is not None:
            self.after_cancel(self._repeat_id)
        self._repeat_id = self.after(delay, self._on_repeat_tick)

    def _on_repeat_tick(self) -> None:
        self._repeat_id = None
        if self._step_toward_hold():
            self._schedule_repeat(delay=45)


class ScrollableFrame(tk.Frame):
    """Vertically scrollable container using mouse wheel without native scrollbars."""

    def __init__(
        self,
        parent: tk.Widget,
        bg: str = BG_MAIN,
        on_width_change: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent, bg=bg)
        self._on_width_change = on_width_change
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.indicator = MinimalScrollIndicator(
            self,
            bg=bg,
            on_scroll_to=self.canvas.yview_moveto,
            on_step=lambda units: self.canvas.yview_scroll(units, "units"),
        )
        self.inner = tk.Frame(self.canvas, bg=bg)

        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.indicator.set_fraction)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.indicator.pack(side="right", fill="y", padx=(2, 0))

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_inner_configure(self, _event: tk.Event[Any]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[Any]) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)
        if self._on_width_change is not None:
            self._on_width_change(event.width)

    def _on_mousewheel(self, event: tk.Event[Any]) -> None:
        if self.inner.winfo_height() <= self.canvas.winfo_height():
            return
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def _bind_mousewheel(self, _event: tk.Event[Any]) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event[Any]) -> None:
        self.canvas.unbind_all("<MouseWheel>")


class StyledModal(tk.Toplevel):
    """Frameless, iOS-style modal dialog centered over the main widget."""

    def __init__(self, parent: tk.Tk, title: str, width: int = 320) -> None:
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=BORDER_WINDOW, padx=1, pady=1)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.98)
        self.bind("<Escape>", lambda _e: self.destroy())

        self._container = tk.Frame(self, bg=BG_MAIN)
        self._container.pack(fill="both", expand=True)

        header = tk.Frame(self._container, bg=BG_HEADER, height=34)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=title,
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            padx=12,
        ).pack(side="left", fill="y")

        tk.Button(
            header,
            text="✕",
            bg=BG_HEADER,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            command=self.destroy,
            padx=10,
        ).pack(side="right", fill="y")

        tk.Frame(self._container, bg=BORDER_WINDOW, height=1).pack(fill="x")

        self.body = tk.Frame(self._container, bg=BG_MAIN, padx=16, pady=14)
        self.body.pack(fill="both", expand=True)

        self._target_width = width

    def center_on_parent(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        req_h = self.winfo_reqheight()
        if parent.state() == "withdrawn":
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(0, (sw - self._target_width) // 2)
            y = max(0, (sh - req_h) // 2)
        else:
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + max(0, (pw - self._target_width) // 2)
            y = py + max(0, (ph - req_h) // 2)
        self.geometry(f"{self._target_width}x{req_h}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()


class BokbutWidgetApp:
    """Main application controller for Bokbut_it."""

    def __init__(
        self,
        root: tk.Tk,
        instance_guard: SingleInstanceGuard | None = None,
    ) -> None:
        global FONT_FAMILY
        self.root = root
        self._instance_guard = instance_guard
        FONT_FAMILY = _resolve_font_family(root)
        self.data = load_data()
        self.active_tab = "copy"

        self._shaded = False
        self._expanded_height = int(
            self.data.get("window_size", {}).get("height", DEFAULT_HEIGHT)
        )

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = DEFAULT_WIDTH
        self._resize_start_h = DEFAULT_HEIGHT
        self._copy_toast_after_id: str | None = None
        self._shortcut_toast_after_id: str | None = None
        self._active_modal: StyledModal | None = None
        self._copy_wrap_labels: list[tk.Label] = []
        self._shortcut_wrap_labels: list[tk.Label] = []

        self._configure_window()
        self._build_header()
        self._build_tab_bar()
        self._build_resize_footer()
        self._build_content_area()
        self._build_edge_resize_handles()
        self._switch_tab("copy")
        self._setup_tray_icon()
        if self._instance_guard is not None:
            self._instance_guard.start_listener(lambda: self.root.after(0, self._restore_from_tray))
        self.root.after(20, lambda: _apply_taskbar_style(self.root))

    # ------------------------------------------------------------------
    # Window Setup, Dragging, Resizing & Shade Mode
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        self.root.overrideredirect(True)
        self.root.title("복붙잇 (Bokbut_it)")
        self.root.configure(bg=BORDER_WINDOW, padx=1, pady=1)
        self.root.attributes("-topmost", bool(self.data.get("topmost", True)))
        self.root.attributes("-alpha", float(self.data.get("alpha", ALPHA_DEFAULT)))

        ico_path = _get_resource_path("assets/Bokbut_it.ico")
        self._tray_pil_image = create_tray_icon_image()
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except Exception:
                self._tk_icon = ImageTk.PhotoImage(self._tray_pil_image)
                self.root.iconphoto(True, self._tk_icon)
        else:
            self._tk_icon = ImageTk.PhotoImage(self._tray_pil_image)
            self.root.iconphoto(True, self._tk_icon)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        size = self.data.get("window_size", {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT})
        w = max(MIN_WIDTH, min(int(size.get("width", DEFAULT_WIDTH)), screen_w))
        h = max(MIN_HEIGHT, min(int(size.get("height", DEFAULT_HEIGHT)), screen_h))
        self._expanded_height = h

        pos = self.data.get("window_pos", {"x": 100, "y": 100})
        x = max(0, min(int(pos.get("x", 100)), max(0, screen_w - w)))
        y = max(0, min(int(pos.get("y", 100)), max(0, screen_h - h)))

        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.outer_frame = tk.Frame(self.root, bg=BG_MAIN)
        self.outer_frame.pack(fill="both", expand=True)

    def _build_header(self) -> None:
        self.header = tk.Frame(self.outer_frame, bg=BG_HEADER, height=36)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        self.title_label = tk.Label(
            self.header,
            text="복붙잇",
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            cursor="fleur",
        )
        self.title_label.pack(side="left", fill="y")

        for widget in (self.header, self.title_label):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._on_move)
            widget.bind("<ButtonRelease-1>", self._end_move)

        close_btn = tk.Button(
            self.header,
            text="✕",
            bg=BG_HEADER,
            fg=TEXT_SECONDARY,
            activebackground="#FEE2E2",
            activeforeground=TEXT_DANGER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            width=3,
            cursor="hand2",
            command=self._on_close,
        )
        close_btn.pack(side="right", fill="y")

        self.shade_btn = tk.Button(
            self.header,
            text="▲",
            bg=BG_HEADER,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 8, "bold"),
            width=3,
            cursor="hand2",
            command=self._toggle_shade,
        )
        self.shade_btn.pack(side="right", fill="y", padx=(0, 1))

        self.min_btn = tk.Button(
            self.header,
            text="—",
            bg=BG_HEADER,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            width=3,
            cursor="hand2",
            command=self._minimize_to_taskbar,
        )
        self.min_btn.pack(side="right", fill="y", padx=(0, 1))

        self.pin_btn = tk.Button(
            self.header,
            text="📌",
            bd=0,
            font=(FONT_FAMILY, 9),
            width=3,
            cursor="hand2",
            command=self._toggle_topmost,
        )
        self.pin_btn.pack(side="right", fill="y", padx=(0, 1))
        self._refresh_pin_style()

        self.alpha_btn = tk.Button(
            self.header,
            text="💧",
            bd=0,
            font=(FONT_FAMILY, 9),
            width=3,
            cursor="hand2",
            command=self._toggle_alpha,
        )
        self.alpha_btn.pack(side="right", fill="y", padx=(0, 1))
        self._refresh_alpha_style()

        self.header_divider = tk.Frame(self.outer_frame, bg=BORDER_WINDOW, height=1)
        self.header_divider.pack(fill="x")

    def _build_resize_footer(self) -> None:
        self.resize_footer = tk.Frame(self.outer_frame, bg=BG_MAIN, height=14)
        self.resize_footer.pack(fill="x", side="bottom")
        self.resize_footer.pack_propagate(False)

        grip = tk.Label(
            self.resize_footer,
            text="◢",
            bg=BG_MAIN,
            fg="#D1D5DB",
            font=(FONT_FAMILY, 8),
            cursor="size_nw_se",
            padx=6,
        )
        grip.pack(side="right", fill="y")
        grip.bind("<ButtonPress-1>", lambda e: self._start_resize(e, "se"))
        grip.bind("<B1-Motion>", self._on_resize)
        grip.bind("<ButtonRelease-1>", self._end_resize)

    def _build_edge_resize_handles(self) -> None:
        """Add thin edge and corner handles so the window can be resized from all 4 sides."""
        t = 4
        c = 8
        specs: list[tuple[str, str, dict[str, Any]]] = [
            ("n", "size_ns", {"relx": 0.0, "rely": 0.0, "relwidth": 1.0, "height": t}),
            ("s", "size_ns", {"relx": 0.0, "rely": 1.0, "y": -t, "relwidth": 1.0, "height": t}),
            ("w", "size_we", {"relx": 0.0, "rely": 0.0, "width": t, "relheight": 1.0}),
            ("e", "size_we", {"relx": 1.0, "x": -t, "rely": 0.0, "width": t, "relheight": 1.0}),
            ("nw", "size_nw_se", {"relx": 0.0, "rely": 0.0, "width": c, "height": c}),
            ("ne", "size_ne_sw", {"relx": 1.0, "x": -c, "rely": 0.0, "width": c, "height": c}),
            ("sw", "size_ne_sw", {"relx": 0.0, "rely": 1.0, "y": -c, "width": c, "height": c}),
            ("se", "size_nw_se", {"relx": 1.0, "x": -c, "rely": 1.0, "y": -c, "width": c, "height": c}),
        ]
        for direction, cursor_name, place_kw in specs:
            handle = tk.Frame(self.root, bg=BORDER_WINDOW, cursor=cursor_name)
            handle.place(**place_kw)
            handle.lift()
            handle.bind("<ButtonPress-1>", lambda e, d=direction: self._start_resize(e, d))
            handle.bind("<B1-Motion>", self._on_resize)
            handle.bind("<ButtonRelease-1>", self._end_resize)

    def _minimize_to_taskbar(self) -> None:
        """Minimize the frameless window to the Windows taskbar."""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, 6)
        except Exception:
            pass

    def _toggle_shade(self) -> None:
        w = self.root.winfo_width()
        x = self.root.winfo_x()
        y = self.root.winfo_y()

        if not self._shaded:
            self._expanded_height = max(MIN_HEIGHT, self.root.winfo_height())
            self._shaded = True
            self.tab_bar_container.pack_forget()
            self.content_area.pack_forget()
            self.resize_footer.pack_forget()
            self.shade_btn.configure(text="▼")
            self.root.geometry(f"{w}x{SHADE_HEIGHT}+{x}+{y}")
        else:
            self._shaded = False
            self.tab_bar_container.pack(fill="x", padx=12, pady=(10, 6))
            self.resize_footer.pack(fill="x", side="bottom")
            self.content_area.pack(fill="both", expand=True)
            self.shade_btn.configure(text="▲")
            self.root.geometry(f"{w}x{self._expanded_height}+{x}+{y}")

    def _start_move(self, event: tk.Event[Any]) -> None:
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()

    def _on_move(self, event: tk.Event[Any]) -> None:
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _end_move(self, _event: tk.Event[Any]) -> None:
        self.data["window_pos"] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        save_data(self.data)

    def _start_resize(self, event: tk.Event[Any], direction: str = "se") -> None:
        self._resize_dir = direction
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_wx = self.root.winfo_x()
        self._resize_start_wy = self.root.winfo_y()
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _on_resize(self, event: tk.Event[Any]) -> None:
        d = getattr(self, "_resize_dir", "se")
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y

        new_x = self._resize_start_wx
        new_y = self._resize_start_wy
        new_w = self._resize_start_w
        new_h = self._resize_start_h

        if "e" in d:
            new_w = max(MIN_WIDTH, self._resize_start_w + dx)
        if "w" in d:
            max_dx = self._resize_start_w - MIN_WIDTH
            clamped_dx = min(dx, max_dx)
            new_w = self._resize_start_w - clamped_dx
            new_x = self._resize_start_wx + clamped_dx

        if not self._shaded:
            if "s" in d:
                new_h = max(MIN_HEIGHT, self._resize_start_h + dy)
            if "n" in d:
                max_dy = self._resize_start_h - MIN_HEIGHT
                clamped_dy = min(dy, max_dy)
                new_h = self._resize_start_h - clamped_dy
                new_y = self._resize_start_wy + clamped_dy

        self.root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

    def _end_resize(self, _event: tk.Event[Any]) -> None:
        if not self._shaded:
            self._expanded_height = self.root.winfo_height()
        self.data["window_pos"] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        self.data["window_size"] = {
            "width": self.root.winfo_width(),
            "height": self._expanded_height,
        }
        save_data(self.data)

    def _toggle_topmost(self) -> None:
        new_state = not bool(self.data.get("topmost", True))
        self.data["topmost"] = new_state
        self.root.attributes("-topmost", new_state)
        self._refresh_pin_style()
        save_data(self.data)

    def _refresh_pin_style(self) -> None:
        is_pinned = bool(self.data.get("topmost", True))
        self.pin_btn.configure(
            bg=BG_CARD_ACTIVE if is_pinned else BG_HEADER,
            fg=ACCENT_BLUE if is_pinned else TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
        )

    def _toggle_alpha(self) -> None:
        current = round(float(self.data.get("alpha", ALPHA_DEFAULT)), 2)
        try:
            idx = ALPHA_LEVELS.index(current)
            new_alpha = ALPHA_LEVELS[(idx + 1) % len(ALPHA_LEVELS)]
        except ValueError:
            new_alpha = ALPHA_DEFAULT
        self.data["alpha"] = new_alpha
        self.root.attributes("-alpha", new_alpha)
        self._refresh_alpha_style()
        save_data(self.data)

    def _refresh_alpha_style(self) -> None:
        current = round(float(self.data.get("alpha", ALPHA_DEFAULT)), 2)
        if current >= 0.99:
            bg, fg = BG_HEADER, TEXT_SECONDARY
        elif current >= 0.85:
            bg, fg = BG_SUBTLE, TEXT_PRIMARY
        else:
            bg, fg = BG_CARD_ACTIVE, ACCENT_BLUE
        self.alpha_btn.configure(bg=bg, fg=fg, activebackground=BG_SUBTLE)

    def _save_current_state(self) -> None:
        self.data["window_pos"] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        self.data["window_size"] = {
            "width": self.root.winfo_width(),
            "height": self._expanded_height if self._shaded else self.root.winfo_height(),
        }
        if hasattr(self, "memo_text"):
            self.data["memo"] = self.memo_text.get("1.0", "end-1c")
        save_data(self.data)

    def _on_close(self) -> None:
        """Hide window to system tray and taskbar instead of exiting."""
        self._save_current_state()
        self.root.withdraw()

    def _setup_tray_icon(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                "📌 복붙잇 열기",
                lambda _icon, _item: self.root.after(0, self._restore_from_tray),
                default=True,
            ),
            pystray.MenuItem(
                "⚙️ 설정",
                lambda _icon, _item: self.root.after(0, self._open_settings_modal),
            ),
            pystray.MenuItem(
                "👩‍💻 개발자 정보",
                lambda _icon, _item: self.root.after(0, self._open_about_modal),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌ 완전 종료",
                lambda _icon, _item: self.root.after(0, self._quit_app),
            ),
        )
        self.tray_icon = pystray.Icon(
            "Bokbut_it",
            self._tray_pil_image,
            "복붙잇 (Bokbut_it)",
            menu,
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _restore_from_tray(self) -> None:
        self.root.deiconify()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)
        except Exception:
            pass
        _apply_taskbar_style(self.root)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        if not bool(self.data.get("topmost", True)):
            self.root.after(50, lambda: self.root.attributes("-topmost", False))

    def _quit_app(self) -> None:
        self._save_current_state()
        if self._instance_guard is not None:
            self._instance_guard.release()
        if hasattr(self, "tray_icon") and self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    def _open_settings_modal(self) -> None:
        modal = self._create_modal("⚙️ 설정", width=300)

        autostart_var = tk.BooleanVar(value=_is_autostart_enabled())
        topmost_var = tk.BooleanVar(value=bool(self.data.get("topmost", True)))
        alpha_var = tk.DoubleVar(value=round(float(self.data.get("alpha", ALPHA_DEFAULT)), 2))

        tk.Checkbutton(
            modal.body,
            text="Windows 시작 시 자동 실행",
            variable=autostart_var,
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            activebackground=BG_MAIN,
            selectcolor=BG_CARD,
            font=(FONT_FAMILY, 9),
            anchor="w",
            cursor="hand2",
        ).pack(fill="x", pady=(0, 6))

        tk.Checkbutton(
            modal.body,
            text="항상 위 고정 (Topmost)",
            variable=topmost_var,
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            activebackground=BG_MAIN,
            selectcolor=BG_CARD,
            font=(FONT_FAMILY, 9),
            anchor="w",
            cursor="hand2",
        ).pack(fill="x", pady=(0, 10))

        tk.Label(
            modal.body,
            text="기본 창 투명도",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        alpha_row = tk.Frame(modal.body, bg=BG_MAIN)
        alpha_row.pack(fill="x", pady=(0, 14))
        for val, label in ((1.0, "100%"), (0.93, "93%"), (0.78, "78%")):
            tk.Radiobutton(
                alpha_row,
                text=label,
                variable=alpha_var,
                value=val,
                bg=BG_MAIN,
                fg=TEXT_PRIMARY,
                activebackground=BG_MAIN,
                selectcolor=BG_CARD,
                font=(FONT_FAMILY, 9),
                cursor="hand2",
            ).pack(side="left", padx=(0, 10))

        def apply_settings() -> None:
            _set_autostart(autostart_var.get())
            new_topmost = bool(topmost_var.get())
            new_alpha = round(float(alpha_var.get()), 2)
            self.data["topmost"] = new_topmost
            self.data["alpha"] = new_alpha
            self.root.attributes("-topmost", new_topmost)
            self.root.attributes("-alpha", new_alpha)
            self._refresh_pin_style()
            self._refresh_alpha_style()
            save_data(self.data)
            modal.destroy()

        RoundedPrimaryButton(
            modal.body,
            text="저장",
            command=apply_settings,
            height=38,
        ).pack(fill="x")

        modal.center_on_parent(self.root)

    def _open_about_modal(self) -> None:
        modal = self._create_modal("👩‍💻 개발자 정보", width=300)

        tk.Label(
            modal.body,
            text=f"복붙잇 Bokbut_it {APP_VERSION}",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        tk.Label(
            modal.body,
            text="개발자: 노새봄",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        tk.Label(
            modal.body,
            text="후원하기 (Buy Me a Coffee)",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        link_lbl = tk.Label(
            modal.body,
            text=SUPPORT_URL,
            bg=BG_MAIN,
            fg=ACCENT_BLUE,
            font=(FONT_FAMILY, 9, "underline"),
            anchor="w",
            cursor="hand2",
        )
        link_lbl.pack(fill="x", pady=(0, 14))
        link_lbl.bind("<Button-1>", lambda _e: webbrowser.open(SUPPORT_URL))

        RoundedPrimaryButton(
            modal.body,
            text="닫기",
            command=modal.destroy,
            height=38,
        ).pack(fill="x")

        modal.center_on_parent(self.root)

    # ------------------------------------------------------------------
    # Tab Navigation (iOS Segmented Control)
    # ------------------------------------------------------------------
    def _build_tab_bar(self) -> None:
        self.tab_bar_container = tk.Frame(self.outer_frame, bg=BG_MAIN)
        self.tab_bar_container.pack(fill="x", padx=12, pady=(10, 6))

        self.segment_control = SegmentControl(
            self.tab_bar_container,
            items=[
                ("copy", "복사용"),
                ("memo", "메모용"),
                ("shortcut", "단축어"),
            ],
            on_select=self._switch_tab,
        )
        self.segment_control.pack(fill="x")

    def _build_content_area(self) -> None:
        self.content_area = tk.Frame(self.outer_frame, bg=BG_MAIN)
        self.content_area.pack(fill="both", expand=True)

        self.tabs: dict[str, tk.Frame] = {
            "copy": self._build_copy_tab(),
            "memo": self._build_memo_tab(),
            "shortcut": self._build_shortcut_tab(),
        }

    def _switch_tab(self, tab_key: str) -> None:
        self.active_tab = tab_key
        for key, frame in self.tabs.items():
            if key == tab_key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self.segment_control.set_active(tab_key)

    # ------------------------------------------------------------------
    # Clipboard & Modal Helpers
    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _read_clipboard(self) -> str:
        try:
            return str(self.root.clipboard_get())
        except tk.TclError:
            return ""

    def _create_modal(self, title: str, width: int = 320) -> StyledModal:
        if self._active_modal is not None and self._active_modal.winfo_exists():
            self._active_modal.destroy()
        modal = StyledModal(self.root, title, width=width)
        self._active_modal = modal
        return modal

    # ------------------------------------------------------------------
    # Tab 1: [복사용]
    # ------------------------------------------------------------------
    def _build_copy_tab(self) -> tk.Frame:
        frame = tk.Frame(self.content_area, bg=BG_MAIN)

        self._copy_search_visible = False
        self._copy_search_query = ""

        top_bar = tk.Frame(frame, bg=BG_MAIN)
        top_bar.pack(fill="x", padx=12, pady=(0, 4))

        self.copy_toast = tk.Label(
            top_bar,
            text="카드를 클릭하면 바로 복사 · 우클릭 시 내용 보기",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            font=(FONT_FAMILY, 8),
            anchor="w",
            padx=2,
            pady=2,
        )
        self.copy_toast.pack(side="left", fill="x", expand=True)

        self.copy_search_btn = tk.Button(
            top_bar,
            text="검색",
            bg=BG_SUBTLE,
            fg=TEXT_PRIMARY,
            activebackground=BG_CARD_ACTIVE,
            activeforeground=ACCENT_BLUE,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            padx=10,
            pady=3,
            command=self._toggle_copy_search,
        )
        self.copy_search_btn.pack(side="right")

        self.copy_search_bar = tk.Frame(
            frame,
            bg=BG_SEGMENT_TRACK,
            highlightbackground=BORDER_CARD,
            highlightthickness=1,
            padx=10,
            pady=6,
        )

        self.copy_search_entry = tk.Entry(
            self.copy_search_bar,
            bg=BG_SEGMENT_TRACK,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10),
            bd=0,
            highlightthickness=0,
        )
        self.copy_search_entry.pack(side="left", fill="x", expand=True)
        self.copy_search_entry.bind("<KeyRelease>", self._on_copy_search_change)
        self.copy_search_entry.bind("<Escape>", lambda _e: self._close_copy_search())

        tk.Button(
            self.copy_search_bar,
            text="✕",
            bg=BG_SEGMENT_TRACK,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD_ACTIVE,
            bd=0,
            font=(FONT_FAMILY, 8, "bold"),
            cursor="hand2",
            padx=4,
            command=self._clear_or_close_copy_search,
        ).pack(side="right")

        RoundedPrimaryButton(
            frame,
            text="+ 텍스트 추가",
            command=lambda: self._open_copy_modal(None),
            height=42,
        ).pack(side="bottom", fill="x", padx=12, pady=(6, 4))

        self.copy_scroll = ScrollableFrame(
            frame,
            bg=BG_MAIN,
            on_width_change=self._on_copy_canvas_resize,
        )
        self.copy_scroll.pack(fill="both", expand=True, padx=12, pady=(2, 4))

        self._render_copy_cards()
        return frame

    def _toggle_copy_search(self) -> None:
        if self._copy_search_visible:
            self._close_copy_search()
        else:
            self._copy_search_visible = True
            self.copy_search_bar.pack(fill="x", padx=12, pady=(0, 6), before=self.copy_scroll)
            self.copy_search_btn.configure(bg=BG_CARD_ACTIVE, fg=ACCENT_BLUE)
            self.copy_search_entry.focus_set()

    def _close_copy_search(self) -> None:
        self._copy_search_visible = False
        self._copy_search_query = ""
        self.copy_search_entry.delete(0, "end")
        self.copy_search_bar.pack_forget()
        self.copy_search_btn.configure(bg=BG_SUBTLE, fg=TEXT_PRIMARY)
        self._render_copy_cards()

    def _clear_or_close_copy_search(self) -> None:
        if self.copy_search_entry.get():
            self.copy_search_entry.delete(0, "end")
            self._copy_search_query = ""
            self._render_copy_cards()
            self.copy_search_entry.focus_set()
        else:
            self._close_copy_search()

    def _on_copy_search_change(self, _event: tk.Event[Any]) -> None:
        self._copy_search_query = self.copy_search_entry.get().strip().lower()
        self._render_copy_cards()

    def _on_copy_canvas_resize(self, width: int) -> None:
        wrap_w = max(140, width - 44)
        for lbl in self._copy_wrap_labels:
            if lbl.winfo_exists():
                lbl.configure(wraplength=wrap_w)

    def _render_copy_cards(self) -> None:
        container = self.copy_scroll.inner
        for child in container.winfo_children():
            child.destroy()
        self._copy_wrap_labels.clear()

        all_cards = self.data.get("copy_cards", [])
        query = getattr(self, "_copy_search_query", "")
        if query:
            cards = [
                c
                for c in all_cards
                if query in str(c.get("title", "")).lower()
                or query in str(c.get("content", "")).lower()
            ]
        else:
            cards = all_cards

        if not cards:
            empty_msg = (
                f"'{query}'에 대한 검색 결과가 없습니다."
                if query
                else "등록된 텍스트가 없습니다.\n하단의 [+ 텍스트 추가] 버튼을 눌러 추가해 보세요!"
            )
            empty_lbl = tk.Label(
                container,
                text=empty_msg,
                bg=BG_MAIN,
                fg=TEXT_SECONDARY,
                font=(FONT_FAMILY, 9),
                justify="center",
                wraplength=240,
                pady=40,
            )
            empty_lbl.pack(fill="x", padx=8)
            empty_lbl.bind(
                "<Configure>",
                lambda e, lbl=empty_lbl: lbl.configure(wraplength=max(140, e.width - 16)),
            )
            return

        for card in cards:
            self._create_copy_card_widget(container, card)

    def _create_copy_card_widget(self, parent: tk.Frame, card: dict[str, Any]) -> None:
        wrapper = tk.Frame(parent, bg=BG_MAIN, pady=4)
        wrapper.pack(fill="x")

        is_collapsed = bool(card.get("collapsed", True))
        title_text = card.get("title") or "(제목 없음)"
        content_text = card.get("content", "")
        kind = "link" if card.get("kind") == "link" else "text"

        pill = PillItemCard(
            wrapper,
            title=title_text,
            is_expanded=not is_collapsed,
            on_copy=lambda: None,
            on_toggle=lambda c=card: self._toggle_copy_card_collapse(c),
            kind=kind,
            on_drag_start=lambda _p, y, cid=card["id"]: self._start_card_drag(cid, y),
            on_drag_move=self._update_card_drag,
            on_drag_end=self._finish_card_drag,
        )
        pill._on_copy = (
            lambda txt=content_text, ttl=title_text, k=kind, p=pill: self._handle_card_action(
                txt, ttl, k, p
            )
        )
        pill.pack(fill="x")

        if not is_collapsed:
            detail = tk.Frame(
                wrapper,
                bg=BG_CARD_EXPANDED,
                highlightbackground=BORDER_CARD,
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            detail.pack(fill="x", padx=4, pady=(4, 2))

            wrap_w = max(140, self.copy_scroll.canvas.winfo_width() - 44)
            content_lbl = tk.Label(
                detail,
                text=content_text,
                bg=BG_CARD_EXPANDED,
                fg=TEXT_PRIMARY,
                font=(FONT_FAMILY, 9),
                justify="left",
                anchor="nw",
                wraplength=wrap_w,
            )
            content_lbl.pack(fill="x", pady=(0, 8))
            self._copy_wrap_labels.append(content_lbl)

            actions = tk.Frame(detail, bg=BG_CARD_EXPANDED)
            actions.pack(fill="x")

            tk.Button(
                actions,
                text="삭제",
                bg=BG_CARD_EXPANDED,
                fg=TEXT_DANGER,
                activebackground="#FEE2E2",
                bd=0,
                font=(FONT_FAMILY, 8, "bold"),
                cursor="hand2",
                padx=8,
                pady=2,
                command=lambda cid=card["id"]: self._delete_copy_card(cid),
            ).pack(side="right")

            tk.Button(
                actions,
                text="수정",
                bg=BG_CARD_EXPANDED,
                fg=ACCENT_BLUE,
                activebackground=BG_CARD_ACTIVE,
                bd=0,
                font=(FONT_FAMILY, 8, "bold"),
                cursor="hand2",
                padx=8,
                pady=2,
                command=lambda c=card: self._open_copy_modal(c),
            ).pack(side="right", padx=(0, 4))

    def _start_card_drag(self, card_id: str, y_root: int) -> None:
        self._drag_card_id = card_id
        self._drag_target_idx: int | None = None
        if not hasattr(self, "_drop_line") or not self._drop_line.winfo_exists():
            self._drop_line = tk.Frame(self.copy_scroll.inner, bg=ACCENT_BLUE, height=3)
        self._show_copy_toast("↕️ 위아래로 드래그하여 위치를 이동하세요")
        self._update_card_drag(y_root)

    def _update_card_drag(self, y_root: int) -> None:
        container = self.copy_scroll.inner
        wrappers = [w for w in container.winfo_children() if w is not getattr(self, "_drop_line", None)]
        if not wrappers:
            return

        target_idx = len(wrappers)
        line_y = wrappers[-1].winfo_y() + wrappers[-1].winfo_height()
        for i, w in enumerate(wrappers):
            mid_y_root = w.winfo_rooty() + w.winfo_height() // 2
            if y_root < mid_y_root:
                target_idx = i
                line_y = max(0, w.winfo_y() - 2)
                break

        self._drag_target_idx = target_idx
        self._drop_line.place(in_=container, x=4, relwidth=1.0, width=-8, y=line_y, height=3)
        self._drop_line.lift()

    def _finish_card_drag(self) -> None:
        if hasattr(self, "_drop_line") and self._drop_line.winfo_exists():
            self._drop_line.place_forget()

        card_id = getattr(self, "_drag_card_id", None)
        target_idx = getattr(self, "_drag_target_idx", None)
        self._drag_card_id = None
        self._drag_target_idx = None

        if card_id is None or target_idx is None:
            return

        cards = self.data.get("copy_cards", [])
        if self._copy_search_query:
            return
        cur_idx = next((i for i, c in enumerate(cards) if c["id"] == card_id), None)
        if cur_idx is None:
            return

        insert_idx = target_idx if target_idx <= cur_idx else target_idx - 1
        insert_idx = max(0, min(len(cards) - 1, insert_idx))
        if insert_idx != cur_idx:
            item = cards.pop(cur_idx)
            cards.insert(insert_idx, item)
            save_data(self.data)
            self._render_copy_cards()

    def _toggle_copy_card_collapse(self, card: dict[str, Any]) -> None:
        card["collapsed"] = not bool(card.get("collapsed", True))
        save_data(self.data)
        self._render_copy_cards()

    def _handle_card_action(self, text: str, title: str, kind: str, pill: PillItemCard) -> None:
        if kind == "link":
            url = text.strip()
            if url and not url.startswith(("http://", "https://", "mailto:", "file://")):
                url = "https://" + url
            if url:
                webbrowser.open(url)
                pill.trigger_copied_feedback()
                self._show_copy_toast(f"↗ 링크 열림: {title}")
            return

        self._copy_to_clipboard(text)
        pill.trigger_copied_feedback()
        self._show_copy_toast(f"✓ 복사됨: {title}")

    def _show_copy_toast(self, message: str) -> None:
        if self._copy_toast_after_id is not None:
            self.root.after_cancel(self._copy_toast_after_id)

        self.copy_toast.configure(text=message, fg=ACCENT_BLUE)
        self._copy_toast_after_id = self.root.after(
            3000,
            lambda: self.copy_toast.configure(
                text="카드를 클릭하면 바로 복사 · 우클릭 시 내용 보기",
                fg=TEXT_SECONDARY,
            ),
        )

    def _delete_copy_card(self, card_id: str) -> None:
        self.data["copy_cards"] = [c for c in self.data["copy_cards"] if c["id"] != card_id]
        save_data(self.data)
        self._render_copy_cards()

    def _open_copy_modal(self, card: dict[str, Any] | None) -> None:
        is_edit = card is not None
        modal = self._create_modal("항목 수정" if is_edit else "새 항목 추가")

        kind_var = tk.StringVar(
            value="link" if (is_edit and card is not None and card.get("kind") == "link") else "text"
        )

        tk.Label(
            modal.body,
            text="유형",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 3))

        kind_row = tk.Frame(modal.body, bg=BG_MAIN)
        kind_row.pack(fill="x", pady=(0, 8))

        content_label = tk.Label(
            modal.body,
            text="이동할 URL" if kind_var.get() == "link" else "복사할 내용",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        )

        def on_kind_change() -> None:
            content_label.configure(
                text="이동할 URL" if kind_var.get() == "link" else "복사할 내용"
            )

        for val, text in (("text", "텍스트 (클릭 시 복사)"), ("link", "링크 (클릭 시 이동)")):
            tk.Radiobutton(
                kind_row,
                text=text,
                variable=kind_var,
                value=val,
                bg=BG_MAIN,
                fg=TEXT_PRIMARY,
                activebackground=BG_MAIN,
                selectcolor=BG_CARD,
                font=(FONT_FAMILY, 9),
                cursor="hand2",
                command=on_kind_change,
            ).pack(side="left", padx=(0, 12))

        tk.Label(
            modal.body,
            text="제목",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 3))

        title_entry = tk.Entry(
            modal.body,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9),
            relief="solid",
            bd=1,
        )
        if is_edit:
            title_entry.insert(0, card.get("title", ""))
        title_entry.pack(fill="x", pady=(0, 10))

        content_label.pack(fill="x", pady=(0, 3))

        content_text = tk.Text(
            modal.body,
            height=5,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9),
            relief="solid",
            bd=1,
            wrap="word",
            padx=12,
            pady=10,
            spacing1=3,
            spacing2=4,
        )
        if is_edit:
            content_text.insert("1.0", card.get("content", ""))
        content_text.pack(fill="x", pady=(0, 12))

        def save_card() -> None:
            new_kind = kind_var.get()
            new_title = title_entry.get().strip() or "제목 없음"
            new_content = content_text.get("1.0", "end-1c").strip()
            if not new_content:
                return
            if is_edit and card is not None:
                card["kind"] = new_kind
                card["title"] = new_title
                card["content"] = new_content
            else:
                self.data["copy_cards"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "kind": new_kind,
                        "title": new_title,
                        "content": new_content,
                        "collapsed": True,
                    }
                )
            save_data(self.data)
            self._render_copy_cards()
            modal.destroy()

        RoundedPrimaryButton(
            modal.body,
            text="저장" if is_edit else "추가",
            command=save_card,
            height=40,
        ).pack(fill="x")

        modal.center_on_parent(self.root)
        title_entry.focus_set()

    # ------------------------------------------------------------------
    # Tab 2: [메모용]
    # ------------------------------------------------------------------
    def _build_memo_tab(self) -> tk.Frame:
        frame = tk.Frame(self.content_area, bg=BG_MAIN, padx=12, pady=4)

        status_row = tk.Frame(frame, bg=BG_MAIN)
        status_row.pack(fill="x", pady=(0, 6))

        tk.Label(
            status_row,
            text="자유 메모장",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left")

        self.memo_status_label = tk.Label(
            status_row,
            text="자동 저장됨 ✓",
            bg=BG_MAIN,
            fg=ACCENT_BLUE,
            font=(FONT_FAMILY, 8, "bold"),
        )
        self.memo_status_label.pack(side="right")

        box = tk.Frame(
            frame,
            bg=BG_CARD,
            highlightbackground=BORDER_CARD,
            highlightcolor=BORDER_CARD,
            highlightthickness=1,
        )
        box.pack(fill="both", expand=True)

        self.memo_text = tk.Text(
            box,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10),
            bd=0,
            padx=12,
            pady=10,
            spacing1=3,
            spacing2=4,
            wrap="word",
            undo=True,
        )
        self.memo_scroll_indicator = MinimalScrollIndicator(
            box,
            bg=BG_CARD,
            on_scroll_to=self.memo_text.yview_moveto,
            on_step=lambda units: self.memo_text.yview_scroll(units, "units"),
        )
        self.memo_text.configure(yscrollcommand=self.memo_scroll_indicator.set_fraction)
        self.memo_scroll_indicator.pack(side="right", fill="y", padx=(0, 3), pady=4)
        self.memo_text.pack(side="left", fill="both", expand=True)

        self.memo_text.insert("1.0", self.data.get("memo", ""))
        self.memo_text.bind("<KeyRelease>", self._on_memo_key_release)
        self.memo_text.bind("<MouseWheel>", self._on_memo_mousewheel)
        return frame

    def _on_memo_mousewheel(self, event: tk.Event[Any]) -> str:
        delta = -1 if event.delta > 0 else 1
        self.memo_text.yview_scroll(delta, "units")
        return "break"

    def _on_memo_key_release(self, _event: tk.Event[Any]) -> None:
        self.data["memo"] = self.memo_text.get("1.0", "end-1c")
        if save_data(self.data):
            self.memo_status_label.configure(text="자동 저장됨 ✓", fg=ACCENT_BLUE)
        else:
            self.memo_status_label.configure(text="저장 실패", fg=TEXT_DANGER)

    # ------------------------------------------------------------------
    # Tab 3: [단축어]
    # ------------------------------------------------------------------
    def _build_shortcut_tab(self) -> tk.Frame:
        frame = tk.Frame(self.content_area, bg=BG_MAIN)

        self.shortcut_toast = tk.Label(
            frame,
            text="카드를 클릭하면 규칙 변환 후 복사 · 우클릭 시 내용 보기",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            font=(FONT_FAMILY, 8),
            anchor="w",
            padx=14,
            pady=2,
        )
        self.shortcut_toast.pack(fill="x", pady=(0, 4))

        RoundedPrimaryButton(
            frame,
            text="+ 단축어 추가",
            command=lambda: self._open_shortcut_modal(None),
            height=42,
        ).pack(side="bottom", fill="x", padx=12, pady=(6, 4))

        self.shortcut_scroll = ScrollableFrame(
            frame,
            bg=BG_MAIN,
            on_width_change=self._on_shortcut_canvas_resize,
        )
        self.shortcut_scroll.pack(fill="both", expand=True, padx=12, pady=(2, 4))

        self._render_shortcuts()
        return frame

    def _on_shortcut_canvas_resize(self, width: int) -> None:
        wrap_w = max(140, width - 44)
        for lbl in self._shortcut_wrap_labels:
            if lbl.winfo_exists():
                lbl.configure(wraplength=wrap_w)

    def _build_tag_chips(self, parent: tk.Frame, on_click: Callable[[str], None]) -> None:
        chips_frame = tk.Frame(parent, bg=BG_SUBTLE, padx=6, pady=6)
        chips_frame.pack(fill="x", pady=(2, 6))

        row_frame = tk.Frame(chips_frame, bg=BG_SUBTLE)
        row_frame.pack(fill="x", pady=2)

        for idx, (tag, _desc) in enumerate(AVAILABLE_TAGS):
            if idx in (3, 6):
                row_frame = tk.Frame(chips_frame, bg=BG_SUBTLE)
                row_frame.pack(fill="x", pady=2)
            label = FRIENDLY_TAG_LABELS.get(tag, tag)
            btn = tk.Button(
                row_frame,
                text=label,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                activebackground=BG_CARD_ACTIVE,
                bd=1,
                relief="solid",
                font=(FONT_FAMILY, 8),
                cursor="hand2",
                padx=5,
                pady=2,
                command=lambda t=tag: on_click(t),
            )
            btn.pack(side="left", padx=(0, 4))
            HoverTooltip(btn, lambda t=tag: _get_tag_tooltip_text(t))

    @staticmethod
    def _insert_tag(text_widget: tk.Text, tag: str) -> None:
        text_widget.insert(tk.INSERT, tag)
        text_widget.focus_set()

    def _render_shortcuts(self) -> None:
        container = self.shortcut_scroll.inner
        for child in container.winfo_children():
            child.destroy()
        self._shortcut_wrap_labels.clear()

        shortcuts = self.data.get("shortcuts", [])
        if not shortcuts:
            empty_lbl = tk.Label(
                container,
                text="등록된 단축어가 없습니다.\n하단의 [+ 단축어 추가] 버튼을 눌러 양식을 만들어 보세요!",
                bg=BG_MAIN,
                fg=TEXT_SECONDARY,
                font=(FONT_FAMILY, 9),
                justify="center",
                wraplength=240,
                pady=40,
            )
            empty_lbl.pack(fill="x", padx=8)
            empty_lbl.bind(
                "<Configure>",
                lambda e, lbl=empty_lbl: lbl.configure(wraplength=max(140, e.width - 16)),
            )
            return

        for sc in shortcuts:
            self._create_shortcut_card_widget(container, sc)

    def _create_shortcut_card_widget(self, parent: tk.Frame, sc: dict[str, Any]) -> None:
        wrapper = tk.Frame(parent, bg=BG_MAIN, pady=4)
        wrapper.pack(fill="x")

        is_collapsed = bool(sc.get("collapsed", True))
        name_text = sc.get("name") or "(이름 없음)"
        template_text = sc.get("template", "")

        pill = PillItemCard(
            wrapper,
            title=name_text,
            is_expanded=not is_collapsed,
            on_copy=lambda: None,
            on_toggle=lambda s=sc: self._toggle_shortcut_collapse(s),
        )
        pill._on_copy = lambda s=sc, p=pill: self._execute_shortcut(s, p)
        pill.pack(fill="x")

        if not is_collapsed:
            detail = tk.Frame(
                wrapper,
                bg=BG_CARD_EXPANDED,
                highlightbackground=BORDER_CARD,
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            detail.pack(fill="x", padx=4, pady=(4, 2))

            wrap_w = max(140, self.shortcut_scroll.canvas.winfo_width() - 44)
            tpl_lbl = tk.Label(
                detail,
                text=template_text,
                bg=BG_CARD_EXPANDED,
                fg=TEXT_SECONDARY,
                font=(FONT_FAMILY, 8),
                justify="left",
                anchor="nw",
                wraplength=wrap_w,
            )
            tpl_lbl.pack(fill="x", pady=(0, 8))
            self._shortcut_wrap_labels.append(tpl_lbl)

            actions = tk.Frame(detail, bg=BG_CARD_EXPANDED)
            actions.pack(fill="x")

            tk.Button(
                actions,
                text="삭제",
                bg=BG_CARD_EXPANDED,
                fg=TEXT_DANGER,
                activebackground="#FEE2E2",
                bd=0,
                font=(FONT_FAMILY, 8, "bold"),
                cursor="hand2",
                padx=8,
                pady=2,
                command=lambda sid=sc["id"]: self._delete_shortcut(sid),
            ).pack(side="right")

            tk.Button(
                actions,
                text="수정",
                bg=BG_CARD_EXPANDED,
                fg=ACCENT_BLUE,
                activebackground=BG_CARD_ACTIVE,
                bd=0,
                font=(FONT_FAMILY, 8, "bold"),
                cursor="hand2",
                padx=8,
                pady=2,
                command=lambda s=sc: self._open_shortcut_modal(s),
            ).pack(side="right", padx=(0, 4))

    def _toggle_shortcut_collapse(self, sc: dict[str, Any]) -> None:
        sc["collapsed"] = not bool(sc.get("collapsed", True))
        save_data(self.data)
        self._render_shortcuts()

    def _execute_shortcut(self, sc: dict[str, Any], pill: PillItemCard) -> None:
        template = sc.get("template", "")
        clipboard_text = self._read_clipboard()
        fields = extract_input_fields(template)

        if fields:
            self._prompt_shortcut_inputs(
                sc.get("name", "단축어"),
                fields,
                lambda values: self._finalize_shortcut(template, clipboard_text, values, pill),
            )
        else:
            self._finalize_shortcut(template, clipboard_text, {}, pill)

    def _prompt_shortcut_inputs(
        self,
        shortcut_name: str,
        fields: list[str],
        on_submit: Callable[[dict[str, str]], None],
    ) -> None:
        modal = self._create_modal(f"입력 필요 - {shortcut_name}", width=300)
        entries: dict[str, tk.Entry] = {}

        for field in fields:
            tk.Label(
                modal.body,
                text=field,
                bg=BG_MAIN,
                fg=TEXT_PRIMARY,
                font=(FONT_FAMILY, 9, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 2))

            entry = tk.Entry(
                modal.body,
                bg=BG_INPUT,
                fg=TEXT_PRIMARY,
                font=(FONT_FAMILY, 9),
                relief="solid",
                bd=1,
            )
            entry.pack(fill="x", pady=(0, 8))
            entries[field] = entry

        def submit(_event: tk.Event[Any] | None = None) -> None:
            values = {k: v.get() for k, v in entries.items()}
            modal.destroy()
            on_submit(values)

        for entry in entries.values():
            entry.bind("<Return>", submit)

        RoundedPrimaryButton(
            modal.body,
            text="확인 및 복사",
            command=submit,
            height=38,
        ).pack(fill="x", pady=(4, 0))

        modal.center_on_parent(self.root)
        first_entry = next(iter(entries.values()), None)
        if first_entry:
            first_entry.focus_set()

    def _finalize_shortcut(
        self,
        template: str,
        clipboard_text: str,
        input_values: dict[str, str],
        pill: PillItemCard,
    ) -> None:
        rendered = render_template(template, clipboard_text=clipboard_text, input_values=input_values)
        self._copy_to_clipboard(rendered)
        pill.trigger_copied_feedback()

        preview = " / ".join(line.strip() for line in rendered.splitlines() if line.strip())
        if len(preview) > 36:
            preview = preview[:36] + "..."
        self._show_shortcut_toast(f"✓ 복사됨: {preview or '(빈 텍스트)'}")

    def _show_shortcut_toast(self, message: str) -> None:
        if self._shortcut_toast_after_id is not None:
            self.root.after_cancel(self._shortcut_toast_after_id)

        self.shortcut_toast.configure(text=message, fg=ACCENT_BLUE)
        self._shortcut_toast_after_id = self.root.after(
            3500,
            lambda: self.shortcut_toast.configure(
                text="카드를 클릭하면 규칙 변환 후 복사 · 우클릭 시 내용 보기",
                fg=TEXT_SECONDARY,
            ),
        )

    def _delete_shortcut(self, shortcut_id: str) -> None:
        self.data["shortcuts"] = [s for s in self.data["shortcuts"] if s["id"] != shortcut_id]
        save_data(self.data)
        self._render_shortcuts()

    def _open_shortcut_modal(self, sc: dict[str, Any] | None) -> None:
        is_edit = sc is not None
        modal = self._create_modal("단축어 수정" if is_edit else "새 단축어 추가", width=335)

        tk.Label(
            modal.body,
            text="1. 단축어 이름",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 3))

        name_entry = tk.Entry(
            modal.body,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9),
            relief="solid",
            bd=1,
        )
        if is_edit:
            name_entry.insert(0, sc.get("name", ""))
        name_entry.pack(fill="x", pady=(0, 8))

        tk.Label(
            modal.body,
            text="2. 자동 변환 태그 넣기 (클릭하면 아래 양식에 삽입)",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        template_text = tk.Text(
            modal.body,
            height=5,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9),
            relief="solid",
            bd=1,
            wrap="word",
            padx=12,
            pady=10,
            spacing1=3,
            spacing2=4,
        )

        self._build_tag_chips(modal.body, lambda tag: self._insert_tag(template_text, tag))

        tk.Label(
            modal.body,
            text="3. 양식 내용 (예: {오늘날짜} ({요일}) / {입력:항목명})",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            font=(FONT_FAMILY, 8),
            anchor="w",
        ).pack(fill="x", pady=(0, 3))

        if is_edit:
            template_text.insert("1.0", sc.get("template", ""))
        template_text.pack(fill="x", pady=(0, 12))

        def save_shortcut() -> None:
            new_name = name_entry.get().strip() or "새 단축어"
            new_template = template_text.get("1.0", "end-1c").strip()
            if not new_template:
                return
            if is_edit and sc is not None:
                sc["name"] = new_name
                sc["template"] = new_template
            else:
                self.data["shortcuts"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": new_name,
                        "template": new_template,
                        "collapsed": True,
                    }
                )
            save_data(self.data)
            self._render_shortcuts()
            modal.destroy()

        RoundedPrimaryButton(
            modal.body,
            text="저장" if is_edit else "단축어 추가",
            command=save_shortcut,
            height=40,
        ).pack(fill="x")

        modal.center_on_parent(self.root)
        name_entry.focus_set()


def main() -> None:
    guard = SingleInstanceGuard()
    if not guard.acquire():
        return
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    BokbutWidgetApp(root, instance_guard=guard)
    root.mainloop()


if __name__ == "__main__":
    main()
