"""Floating Windows status panel for the voice loop."""

from __future__ import annotations

import queue
import threading
import tkinter as tk

from jarvis.core import Core

LABELS = {
    "loading": "INICIANDO",
    "idle": "EM ESPERA",
    "awake": "ATIVADO",
    "listening": "OUVINDO",
    "followup": "CONVERSA ABERTA",
    "transcribing": "TRANSCREVENDO",
    "thinking": "PENSANDO",
    "working": "CONSULTANDO",
    "confirmation": "CONFIRMAÇÃO",
    "speaking": "RESPONDENDO",
    "error": "ERRO",
}
COLORS = {
    "idle": "#3e8097",
    "awake": "#69f4ff",
    "listening": "#38f2ec",
    "followup": "#38f2ec",
    "thinking": "#ffc773",
    "working": "#ffc773",
    "confirmation": "#ff9270",
    "error": "#ff9270",
}


def run_hud(core: Core) -> None:
    from jarvis.voice import VoiceLoop

    updates: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
    stop = threading.Event()
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.95)
    root.configure(bg="#07121e")
    width, height = 460, 174
    root.geometry(f"{width}x{height}+{root.winfo_screenwidth() - width - 28}+48")
    canvas = tk.Canvas(root, width=width, height=height, bg="#07121e", highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(1, 1, width - 2, height - 2, outline="#1d728d", width=2)
    canvas.create_text(
        28, 22, anchor="w", text="J.A.R.V.I.S", fill="#70e9fa", font=("Segoe UI", 12, "bold")
    )
    canvas.create_line(28, 43, width - 28, 43, fill="#1b6176")
    ring = canvas.create_arc(
        30, 66, 112, 148, start=0, extent=260, style="arc", outline="#3e8097", width=6
    )
    canvas.create_oval(47, 83, 95, 131, outline="#226980", width=2)
    state_text = canvas.create_text(
        138, 80, anchor="w", text="INICIANDO", fill="#70e9fa", font=("Segoe UI", 16, "bold")
    )
    detail_text = canvas.create_text(
        138,
        110,
        anchor="nw",
        text="Preparando assistente...",
        fill="#cfdfec",
        width=288,
        font=("Segoe UI", 10),
    )
    canvas.create_text(
        width - 23,
        20,
        anchor="center",
        text="×",
        fill="#9db8c7",
        font=("Segoe UI", 16),
        tags="close",
    )
    canvas.tag_bind("close", "<Button-1>", lambda _event: close())
    drag: dict[str, int] = {}

    def drag_start(event: tk.Event) -> None:
        drag["x"] = event.x_root - root.winfo_x()
        drag["y"] = event.y_root - root.winfo_y()

    def drag_move(event: tk.Event) -> None:
        root.geometry(f"+{event.x_root - drag['x']}+{event.y_root - drag['y']}")

    canvas.bind("<ButtonPress-1>", drag_start)
    canvas.bind("<B1-Motion>", drag_move)

    def close() -> None:
        stop.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    core.progress = lambda state, detail: updates.put((state, detail))

    def worker() -> None:
        com = None
        try:
            try:
                import pythoncom

                pythoncom.CoInitialize()
                com = pythoncom
            except ImportError:
                pass
            VoiceLoop(core.settings.voice, core, lambda s, d: updates.put((s, d)), stop).run()
        except Exception as exc:
            updates.put(("error", str(exc)))
        finally:
            if com:
                com.CoUninitialize()

    threading.Thread(target=worker, daemon=True, name="jarvis-voice").start()
    phase = 0
    state = "loading"

    def refresh() -> None:
        nonlocal phase, state
        while not updates.empty():
            state, detail = updates.get()
            canvas.itemconfigure(state_text, text=LABELS.get(state, state.upper()))
            canvas.itemconfigure(detail_text, text=detail)
        phase = (phase + 12) % 360
        canvas.itemconfigure(ring, start=phase, outline=COLORS.get(state, "#70e9fa"))
        if not stop.is_set():
            root.after(80, refresh)

    refresh()
    root.mainloop()
