"""Bokbut_it (복붙잇) - Smart Work Post-it Desktop Widget."""

from __future__ import annotations

import ctypes
from datetime import datetime
import tkinter as tk
from tkinter import font as tkfont
import uuid
from typing import Any, Callable

from shortcut_engine import AVAILABLE_TAGS, extract_input_fields, render_template
from storage import load_data, save_data

# Stationery Label & Post-it Color Palette
BG_MAIN = "#FFFDF5"
BG_HEADER = "#F7E896"
BG_TAB_BAR = "#F3EED9"
BG_TAB_ACTIVE = "#FFFDF5"
BG_TAB_INACTIVE = "#F3EED9"
BG_CARD = "#FFFFFF"
BG_INPUT = "#FFFFFF"
BG_BUTTON = "#F7E896"
BG_BUTTON_HOVER = "#EFE082"
BG_CHIP = "#FAF5E4"
BG_SUBTLE = "#F3EED9"
BG_TOAST = "#2D2A26"

BORDER_CARD = "#E5DEC9"
BORDER_ACCENT = "#E0B020"
SCROLL_THUMB = "#DDD5BE"

TEXT_PRIMARY = "#1F2937"
TEXT_SECONDARY = "#6B7280"
TEXT_TAB_INACTIVE = "#7A725E"
TEXT_SUCCESS = "#1E7E34"
TEXT_DANGER = "#C92A2A"
TEXT_TOAST = "#FFFDF5"

ALPHA_LEVELS = (0.93, 0.78, 1.0)
ALPHA_DEFAULT = 0.93

FONT_FAMILY = "맑은 고딕"
DEFAULT_WIDTH = 360
DEFAULT_HEIGHT = 540
MIN_WIDTH = 300
MIN_HEIGHT = 380

FRIENDLY_TAG_LABELS: dict[str, str] = {
    "{오늘날짜}": "📅 오늘날짜",
    "{오늘날짜_간략}": "📅 간략날짜",
    "{현재시간}": "🕒 현재시간",
    "{요일}": "📆 요일",
    "{클립보드}": "📋 클립보드",
    "{클립보드_숫자만}": "🔢 숫자만",
    "{입력:항목명}": "✏️ 실행시 입력",
}


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

        lbl = tk.Label(
            tip,
            text=self._text_fn(),
            bg=BG_TOAST,
            fg=TEXT_TOAST,
            font=(FONT_FAMILY, 8),
            padx=8,
            pady=4,
        )
        lbl.pack()

        tip.update_idletasks()
        wx = self._widget.winfo_rootx()
        wy = self._widget.winfo_rooty()
        th = tip.winfo_reqheight()
        tw = tip.winfo_reqwidth()
        sw = tip.winfo_screenwidth()

        x = max(4, min(wx, sw - tw - 4))
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


class MinimalScrollIndicator(tk.Canvas):
    """Minimal 4px custom scroll indicator supporting click-hold auto-scroll and thumb drag."""

    def __init__(
        self,
        parent: tk.Widget,
        bg: str = BG_MAIN,
        thumb_color: str = SCROLL_THUMB,
        on_scroll_to: Callable[[float], None] | None = None,
        on_step: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent, width=8, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
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
        self.create_rectangle(3, top, 7, bottom, fill=self._thumb_color, outline="")

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
    """Vertically scrollable container using mouse wheel and minimal 4px indicator."""

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
    """Frameless, theme-consistent modal dialog centered over the main widget."""

    def __init__(self, parent: tk.Tk, title: str, width: int = 320) -> None:
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=BORDER_CARD, padx=1, pady=1)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.bind("<Escape>", lambda _e: self.destroy())

        self._container = tk.Frame(self, bg=BG_MAIN)
        self._container.pack(fill="both", expand=True)

        header = tk.Frame(self._container, bg=BG_HEADER, height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=title,
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
        ).pack(side="left", fill="y")

        tk.Button(
            header,
            text="✕",
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            command=self.destroy,
            padx=8,
        ).pack(side="right", fill="y")

        self.body = tk.Frame(self._container, bg=BG_MAIN, padx=14, pady=12)
        self.body.pack(fill="both", expand=True)

        self._target_width = width

    def center_on_parent(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        req_h = self.winfo_reqheight()
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

    def __init__(self, root: tk.Tk) -> None:
        global FONT_FAMILY
        self.root = root
        FONT_FAMILY = _resolve_font_family(root)
        self.data = load_data()
        self.active_tab = "copy"

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
        self._switch_tab("copy")

    # ------------------------------------------------------------------
    # Window Setup, Dragging & Resizing
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        self.root.overrideredirect(True)
        self.root.configure(bg=BORDER_CARD, padx=1, pady=1)
        self.root.attributes("-topmost", bool(self.data.get("topmost", True)))
        self.root.attributes("-alpha", float(self.data.get("alpha", ALPHA_DEFAULT)))

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        size = self.data.get("window_size", {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT})
        w = max(MIN_WIDTH, min(int(size.get("width", DEFAULT_WIDTH)), screen_w))
        h = max(MIN_HEIGHT, min(int(size.get("height", DEFAULT_HEIGHT)), screen_h))

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
            text="복붙잇 (Bokbut_it)",
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 10, "bold"),
            padx=12,
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
            fg=TEXT_PRIMARY,
            activebackground="#F7C6C7",
            bd=0,
            font=(FONT_FAMILY, 10, "bold"),
            width=3,
            cursor="hand2",
            command=self._on_close,
        )
        close_btn.pack(side="right", fill="y")

        self.pin_btn = tk.Button(
            self.header,
            text="📌",
            bd=0,
            font=(FONT_FAMILY, 10),
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
            font=(FONT_FAMILY, 10),
            width=3,
            cursor="hand2",
            command=self._toggle_alpha,
        )
        self.alpha_btn.pack(side="right", fill="y", padx=(0, 1))
        self._refresh_alpha_style()

    def _build_resize_footer(self) -> None:
        footer = tk.Frame(self.outer_frame, bg=BG_MAIN, height=16)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        grip = tk.Label(
            footer,
            text="◢",
            bg=BG_MAIN,
            fg=BORDER_CARD,
            font=(FONT_FAMILY, 9),
            cursor="size_nw_se",
            padx=5,
        )
        grip.pack(side="right", fill="y")
        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._on_resize)
        grip.bind("<ButtonRelease-1>", self._end_resize)

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

    def _start_resize(self, event: tk.Event[Any]) -> None:
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _on_resize(self, event: tk.Event[Any]) -> None:
        new_w = max(MIN_WIDTH, self._resize_start_w + (event.x_root - self._resize_start_x))
        new_h = max(MIN_HEIGHT, self._resize_start_h + (event.y_root - self._resize_start_y))
        self.root.geometry(f"{new_w}x{new_h}")

    def _end_resize(self, _event: tk.Event[Any]) -> None:
        self.data["window_size"] = {
            "width": self.root.winfo_width(),
            "height": self.root.winfo_height(),
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
            bg=BG_BUTTON_HOVER if is_pinned else BG_HEADER,
            fg=TEXT_PRIMARY if is_pinned else TEXT_SECONDARY,
            activebackground=BG_BUTTON_HOVER,
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
            bg = BG_HEADER
            fg = TEXT_SECONDARY
        elif current >= 0.85:
            bg = BG_SUBTLE
            fg = TEXT_PRIMARY
        else:
            bg = BG_BUTTON_HOVER
            fg = TEXT_PRIMARY
        self.alpha_btn.configure(bg=bg, fg=fg, activebackground=BG_BUTTON_HOVER)

    def _on_close(self) -> None:
        self.data["window_pos"] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        self.data["window_size"] = {
            "width": self.root.winfo_width(),
            "height": self.root.winfo_height(),
        }
        if hasattr(self, "memo_text"):
            self.data["memo"] = self.memo_text.get("1.0", "end-1c")
        save_data(self.data)
        self.root.destroy()

    # ------------------------------------------------------------------
    # Tab Navigation (Paper Index Tabs with 2px Bottom Accent)
    # ------------------------------------------------------------------
    def _build_tab_bar(self) -> None:
        tab_bar = tk.Frame(self.outer_frame, bg=BG_TAB_BAR, height=36)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self.tab_buttons: dict[str, tk.Button] = {}
        self.tab_indicators: dict[str, tk.Frame] = {}

        tabs = [
            ("copy", "📋 복사용"),
            ("memo", "📝 메모용"),
            ("shortcut", "⚡ 단축어"),
        ]
        for key, label in tabs:
            cell = tk.Frame(tab_bar, bg=BG_TAB_INACTIVE)
            cell.pack(side="left", fill="both", expand=True)

            btn = tk.Button(
                cell,
                text=label,
                bd=0,
                font=(FONT_FAMILY, 9, "bold"),
                cursor="hand2",
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(fill="both", expand=True)

            indicator = tk.Frame(cell, height=2, bg=BORDER_CARD)
            indicator.pack(fill="x", side="bottom")

            self.tab_buttons[key] = btn
            self.tab_indicators[key] = indicator

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

        for key, btn in self.tab_buttons.items():
            if key == tab_key:
                btn.configure(bg=BG_TAB_ACTIVE, fg=TEXT_PRIMARY, activebackground=BG_TAB_ACTIVE)
                self.tab_indicators[key].configure(bg=BORDER_ACCENT)
            else:
                btn.configure(bg=BG_TAB_INACTIVE, fg=TEXT_TAB_INACTIVE, activebackground=BG_TAB_BAR)
                self.tab_indicators[key].configure(bg=BORDER_CARD)

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

        self.copy_toast = tk.Label(
            frame,
            text="카드나 접힌 제목을 클릭하면 바로 복사됩니다.",
            bg=BG_SUBTLE,
            fg=TEXT_TAB_INACTIVE,
            font=(FONT_FAMILY, 8),
            anchor="w",
            padx=10,
            pady=5,
        )
        self.copy_toast.pack(fill="x", padx=10, pady=(8, 4))

        tk.Button(
            frame,
            text="+ 새 복사 카드 추가",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            pady=7,
            command=lambda: self._open_copy_modal(None),
        ).pack(side="bottom", fill="x", padx=10, pady=(0, 4))

        self.copy_scroll = ScrollableFrame(
            frame,
            bg=BG_MAIN,
            on_width_change=self._on_copy_canvas_resize,
        )
        self.copy_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 6))

        self._render_copy_cards()
        return frame

    def _on_copy_canvas_resize(self, width: int) -> None:
        wrap_w = max(140, width - 95)
        for lbl in self._copy_wrap_labels:
            if lbl.winfo_exists():
                lbl.configure(wraplength=wrap_w)

    def _render_copy_cards(self) -> None:
        container = self.copy_scroll.inner
        for child in container.winfo_children():
            child.destroy()
        self._copy_wrap_labels.clear()

        cards = self.data.get("copy_cards", [])
        if not cards:
            tk.Label(
                container,
                text="등록된 복사 카드가 없습니다.\n하단의 [+ 새 복사 카드 추가] 버튼을 눌러 추가해 보세요!",
                bg=BG_MAIN,
                fg=TEXT_SECONDARY,
                font=(FONT_FAMILY, 9),
                justify="center",
                pady=40,
            ).pack(fill="x")
            return

        for card in cards:
            self._create_copy_card_widget(container, card)

    def _create_copy_card_widget(self, parent: tk.Frame, card: dict[str, Any]) -> None:
        wrapper = tk.Frame(parent, bg=BG_MAIN, pady=4, padx=2)
        wrapper.pack(fill="x")

        is_collapsed = bool(card.get("collapsed", False))
        title_text = card.get("title") or "(제목 없음)"
        content_text = card.get("content", "")

        if is_collapsed:
            box = tk.Frame(
                wrapper,
                bg=BG_CARD,
                highlightbackground=BORDER_CARD,
                highlightcolor=BORDER_CARD,
                highlightthickness=1,
                padx=10,
                pady=8,
                cursor="hand2",
            )
            box.pack(fill="x")

            tk.Button(
                box,
                text="▸",
                bg=BG_CARD,
                fg=TEXT_SECONDARY,
                activebackground=BG_SUBTLE,
                bd=0,
                font=(FONT_FAMILY, 9, "bold"),
                cursor="hand2",
                padx=4,
                command=lambda c=card: self._toggle_copy_card_collapse(c),
            ).pack(side="left", padx=(0, 4))

            title_lbl = tk.Label(
                box,
                text=title_text,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                font=(FONT_FAMILY, 9, "bold"),
                anchor="w",
                cursor="hand2",
            )
            title_lbl.pack(side="left", fill="x", expand=True)

            tk.Button(
                box,
                text="✕",
                bg=BG_CARD,
                fg=TEXT_DANGER,
                activebackground="#FFE3E3",
                bd=0,
                font=(FONT_FAMILY, 8, "bold"),
                cursor="hand2",
                padx=4,
                command=lambda cid=card["id"]: self._delete_copy_card(cid),
            ).pack(side="right", padx=(2, 0))

            tk.Button(
                box,
                text="수정",
                bg=BG_CARD,
                fg=TEXT_SECONDARY,
                activebackground=BG_SUBTLE,
                bd=0,
                font=(FONT_FAMILY, 8),
                cursor="hand2",
                padx=4,
                command=lambda c=card: self._open_copy_modal(c),
            ).pack(side="right")

            copy_btn = tk.Button(
                box,
                text="➜",
                bg=BG_SUBTLE,
                fg=TEXT_PRIMARY,
                activebackground=BG_BUTTON,
                bd=0,
                width=3,
                anchor="center",
                justify="center",
                padx=2,
                pady=2,
                font=(FONT_FAMILY, 9),
                cursor="hand2",
            )
            copy_handler = lambda _e=None, txt=content_text, ttl=title_text, btn=copy_btn: self._handle_copy_click(
                txt, ttl, btn
            )
            copy_btn.configure(command=copy_handler)
            copy_btn.pack(side="right", padx=(4, 4))

            box.bind("<Button-1>", copy_handler)
            title_lbl.bind("<Button-1>", copy_handler)
            return

        # Expanded mode
        top_row = tk.Frame(wrapper, bg=BG_MAIN)
        top_row.pack(fill="x", pady=(0, 3))

        tk.Button(
            top_row,
            text="▾",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            padx=3,
            command=lambda c=card: self._toggle_copy_card_collapse(c),
        ).pack(side="left", padx=(0, 2))

        title_lbl = tk.Label(
            top_row,
            text=title_text,
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
            cursor="hand2",
        )
        title_lbl.pack(side="left", fill="x", expand=True)
        title_lbl.bind("<Button-1>", lambda _e, c=card: self._toggle_copy_card_collapse(c))

        tk.Button(
            top_row,
            text="✕",
            bg=BG_MAIN,
            fg=TEXT_DANGER,
            activebackground="#FFE3E3",
            bd=0,
            font=(FONT_FAMILY, 8, "bold"),
            cursor="hand2",
            command=lambda cid=card["id"]: self._delete_copy_card(cid),
        ).pack(side="right", padx=(2, 0))

        tk.Button(
            top_row,
            text="수정",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 8),
            cursor="hand2",
            padx=4,
            command=lambda c=card: self._open_copy_modal(c),
        ).pack(side="right")

        box = tk.Frame(
            wrapper,
            bg=BG_CARD,
            highlightbackground=BORDER_CARD,
            highlightcolor=BORDER_CARD,
            highlightthickness=1,
            padx=12,
            pady=10,
            cursor="hand2",
        )
        box.pack(fill="x")

        wrap_w = max(140, self.copy_scroll.canvas.winfo_width() - 95)
        content_lbl = tk.Label(
            box,
            text=content_text,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9),
            justify="left",
            anchor="nw",
            wraplength=wrap_w,
            cursor="hand2",
        )
        content_lbl.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._copy_wrap_labels.append(content_lbl)

        copy_btn = tk.Button(
            box,
            text="➜",
            bg=BG_SUBTLE,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON,
            bd=0,
            width=3,
            anchor="center",
            justify="center",
            padx=2,
            pady=4,
            font=(FONT_FAMILY, 10),
            cursor="hand2",
        )
        copy_handler = lambda _e=None, txt=content_text, ttl=title_text, btn=copy_btn: self._handle_copy_click(
            txt, ttl, btn
        )
        copy_btn.configure(command=copy_handler)
        copy_btn.pack(side="right", anchor="center")

        box.bind("<Button-1>", copy_handler)
        content_lbl.bind("<Button-1>", copy_handler)

    def _toggle_copy_card_collapse(self, card: dict[str, Any]) -> None:
        card["collapsed"] = not bool(card.get("collapsed", False))
        save_data(self.data)
        self._render_copy_cards()

    def _handle_copy_click(self, text: str, title: str, btn: tk.Button) -> None:
        self._copy_to_clipboard(text)
        btn.configure(text="✓", fg=TEXT_SUCCESS, bg="#E6F4EA")
        self.root.after(
            800,
            lambda: btn.winfo_exists() and btn.configure(text="➜", fg=TEXT_PRIMARY, bg=BG_SUBTLE),
        )
        self._show_copy_toast(f"✓ 복사됨: {title}")

    def _show_copy_toast(self, message: str) -> None:
        if self._copy_toast_after_id is not None:
            self.root.after_cancel(self._copy_toast_after_id)

        self.copy_toast.configure(text=message, bg=BG_TOAST, fg=TEXT_TOAST)
        self._copy_toast_after_id = self.root.after(
            3000,
            lambda: self.copy_toast.configure(
                text="카드나 접힌 제목을 클릭하면 바로 복사됩니다.",
                bg=BG_SUBTLE,
                fg=TEXT_TAB_INACTIVE,
            ),
        )

    def _delete_copy_card(self, card_id: str) -> None:
        self.data["copy_cards"] = [c for c in self.data["copy_cards"] if c["id"] != card_id]
        save_data(self.data)
        self._render_copy_cards()

    def _open_copy_modal(self, card: dict[str, Any] | None) -> None:
        is_edit = card is not None
        modal = self._create_modal("복사 카드 수정" if is_edit else "새 복사 카드 추가")

        tk.Label(
            modal.body,
            text="제목",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

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
        title_entry.pack(fill="x", pady=(0, 8))

        tk.Label(
            modal.body,
            text="복사할 내용",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

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
        content_text.pack(fill="x", pady=(0, 10))

        def save_card() -> None:
            new_title = title_entry.get().strip() or "제목 없음"
            new_content = content_text.get("1.0", "end-1c").strip()
            if not new_content:
                return
            if is_edit and card is not None:
                card["title"] = new_title
                card["content"] = new_content
            else:
                self.data["copy_cards"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": new_title,
                        "content": new_content,
                        "collapsed": False,
                    }
                )
            save_data(self.data)
            self._render_copy_cards()
            modal.destroy()

        tk.Button(
            modal.body,
            text="저장" if is_edit else "카드 추가",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            pady=6,
            command=save_card,
        ).pack(fill="x")

        modal.center_on_parent(self.root)
        title_entry.focus_set()

    # ------------------------------------------------------------------
    # Tab 2: [메모용] (Zero native scrollbar, 4px custom indicator)
    # ------------------------------------------------------------------
    def _build_memo_tab(self) -> tk.Frame:
        frame = tk.Frame(self.content_area, bg=BG_MAIN, padx=10, pady=8)

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
            fg=TEXT_SUCCESS,
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
            self.memo_status_label.configure(text="자동 저장됨 ✓", fg=TEXT_SUCCESS)
        else:
            self.memo_status_label.configure(text="저장 실패", fg=TEXT_DANGER)

    # ------------------------------------------------------------------
    # Tab 3: [⚡ 단축어]
    # ------------------------------------------------------------------
    def _build_shortcut_tab(self) -> tk.Frame:
        frame = tk.Frame(self.content_area, bg=BG_MAIN)

        self.shortcut_toast = tk.Label(
            frame,
            text="단축어를 실행하면 날짜·시간 등이 자동 변환되어 복사됩니다.",
            bg=BG_SUBTLE,
            fg=TEXT_TAB_INACTIVE,
            font=(FONT_FAMILY, 8),
            anchor="w",
            padx=10,
            pady=5,
        )
        self.shortcut_toast.pack(fill="x", padx=10, pady=(8, 4))

        tk.Button(
            frame,
            text="+ 새 단축어 추가",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            pady=7,
            command=lambda: self._open_shortcut_modal(None),
        ).pack(side="bottom", fill="x", padx=10, pady=(0, 4))

        self.shortcut_scroll = ScrollableFrame(
            frame,
            bg=BG_MAIN,
            on_width_change=self._on_shortcut_canvas_resize,
        )
        self.shortcut_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 6))

        self._render_shortcuts()
        return frame

    def _on_shortcut_canvas_resize(self, width: int) -> None:
        wrap_w = max(160, width - 48)
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
                bg=BG_CHIP,
                fg=TEXT_PRIMARY,
                activebackground=BG_BUTTON,
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
            tk.Label(
                container,
                text="등록된 단축어가 없습니다.\n하단의 [+ 새 단축어 추가] 버튼을 눌러 양식을 만들어 보세요!",
                bg=BG_MAIN,
                fg=TEXT_SECONDARY,
                font=(FONT_FAMILY, 9),
                justify="center",
                pady=40,
            ).pack(fill="x")
            return

        for sc in shortcuts:
            self._create_shortcut_card_widget(container, sc)

    def _create_shortcut_card_widget(self, parent: tk.Frame, sc: dict[str, str]) -> None:
        wrapper = tk.Frame(parent, bg=BG_MAIN, pady=4, padx=2)
        wrapper.pack(fill="x")

        top_row = tk.Frame(wrapper, bg=BG_MAIN)
        top_row.pack(fill="x", pady=(0, 3))

        tk.Label(
            top_row,
            text=sc.get("name") or "(이름 없음)",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            top_row,
            text="✕",
            bg=BG_MAIN,
            fg=TEXT_DANGER,
            activebackground="#FFE3E3",
            bd=0,
            font=(FONT_FAMILY, 8, "bold"),
            cursor="hand2",
            command=lambda sid=sc["id"]: self._delete_shortcut(sid),
        ).pack(side="right", padx=(2, 0))

        tk.Button(
            top_row,
            text="수정",
            bg=BG_MAIN,
            fg=TEXT_SECONDARY,
            activebackground=BG_SUBTLE,
            bd=0,
            font=(FONT_FAMILY, 8),
            cursor="hand2",
            padx=4,
            command=lambda s=sc: self._open_shortcut_modal(s),
        ).pack(side="right")

        box = tk.Frame(
            wrapper,
            bg=BG_CARD,
            highlightbackground=BORDER_CARD,
            highlightcolor=BORDER_CARD,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        box.pack(fill="x")

        wrap_w = max(160, self.shortcut_scroll.canvas.winfo_width() - 48)
        tpl_lbl = tk.Label(
            box,
            text=sc.get("template", ""),
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            font=(FONT_FAMILY, 8),
            justify="left",
            anchor="nw",
            wraplength=wrap_w,
        )
        tpl_lbl.pack(fill="x", pady=(0, 8))
        self._shortcut_wrap_labels.append(tpl_lbl)

        tk.Button(
            box,
            text="▶️ 실행 및 복사",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 8, "bold"),
            cursor="hand2",
            pady=4,
            command=lambda s=sc: self._execute_shortcut(s),
        ).pack(fill="x")

    def _execute_shortcut(self, sc: dict[str, str]) -> None:
        template = sc.get("template", "")
        clipboard_text = self._read_clipboard()
        fields = extract_input_fields(template)

        if fields:
            self._prompt_shortcut_inputs(
                sc.get("name", "단축어"),
                fields,
                lambda values: self._finalize_shortcut(template, clipboard_text, values),
            )
        else:
            self._finalize_shortcut(template, clipboard_text, {})

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

        tk.Button(
            modal.body,
            text="확인 및 복사",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            pady=5,
            command=submit,
        ).pack(fill="x")

        modal.center_on_parent(self.root)
        first_entry = next(iter(entries.values()), None)
        if first_entry:
            first_entry.focus_set()

    def _finalize_shortcut(
        self,
        template: str,
        clipboard_text: str,
        input_values: dict[str, str],
    ) -> None:
        rendered = render_template(template, clipboard_text=clipboard_text, input_values=input_values)
        self._copy_to_clipboard(rendered)

        preview = " / ".join(line.strip() for line in rendered.splitlines() if line.strip())
        if len(preview) > 36:
            preview = preview[:36] + "..."
        self._show_shortcut_toast(f"✓ 복사됨: {preview or '(빈 텍스트)'}")

    def _show_shortcut_toast(self, message: str) -> None:
        if self._shortcut_toast_after_id is not None:
            self.root.after_cancel(self._shortcut_toast_after_id)

        self.shortcut_toast.configure(text=message, bg=BG_TOAST, fg=TEXT_TOAST)
        self._shortcut_toast_after_id = self.root.after(
            3500,
            lambda: self.shortcut_toast.configure(
                text="단축어를 실행하면 날짜·시간 등이 자동 변환되어 복사됩니다.",
                bg=BG_SUBTLE,
                fg=TEXT_TAB_INACTIVE,
            ),
        )

    def _delete_shortcut(self, shortcut_id: str) -> None:
        self.data["shortcuts"] = [s for s in self.data["shortcuts"] if s["id"] != shortcut_id]
        save_data(self.data)
        self._render_shortcuts()

    def _open_shortcut_modal(self, sc: dict[str, str] | None) -> None:
        is_edit = sc is not None
        modal = self._create_modal("단축어 수정" if is_edit else "새 단축어 추가", width=335)

        tk.Label(
            modal.body,
            text="1. 단축어 이름",
            bg=BG_MAIN,
            fg=TEXT_PRIMARY,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

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
        ).pack(fill="x", pady=(0, 2))

        if is_edit:
            template_text.insert("1.0", sc.get("template", ""))
        template_text.pack(fill="x", pady=(0, 10))

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
                    }
                )
            save_data(self.data)
            self._render_shortcuts()
            modal.destroy()

        tk.Button(
            modal.body,
            text="저장" if is_edit else "단축어 추가",
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            bd=0,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            pady=6,
            command=save_shortcut,
        ).pack(fill="x")

        modal.center_on_parent(self.root)
        name_entry.focus_set()


def main() -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    BokbutWidgetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
