import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

import psutil

from logging_setup import configure_logging, install_exception_hooks
from single_instance import SingleInstance
from tray_controller import TrayController

STARTUP_SPLASH_ARG = "--startup-splash"
STARTUP_SPLASH_POLL_MS = 100
STARTUP_SPLASH_DONE_DELAY_MS = 1800


def _show_message(kind, title, message):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.update_idletasks()

    try:
        if kind == "error":
            messagebox.showerror(title, message, parent=root)
        else:
            messagebox.showinfo(title, message, parent=root)
    finally:
        root.destroy()


def _show_transient_notice(title, message, timeout_ms=1800):
    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    frame = tk.Frame(root, padx=18, pady=14)
    frame.pack(fill="both", expand=True)

    label = tk.Label(frame, text=message, justify="left", wraplength=300)
    label.pack()

    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x_pos = (root.winfo_screenwidth() - width) // 2
    y_pos = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
    root.after(timeout_ms, root.destroy)
    root.mainloop()


def _show_startup_splash_window(state_path, parent_pid, title, message):
    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#0b1120")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Startup.Horizontal.TProgressbar",
        troughcolor="#162033",
        background="#22c55e",
        lightcolor="#22c55e",
        darkcolor="#16a34a",
        bordercolor="#162033",
        thickness=10,
    )

    outer = tk.Frame(root, bg="#0b1120", padx=16, pady=16)
    outer.pack(fill="both", expand=True)

    card = tk.Frame(
        outer,
        bg="#111827",
        padx=18,
        pady=18,
        highlightthickness=1,
        highlightbackground="#243041",
    )
    card.pack(fill="both", expand=True)

    header = tk.Frame(card, bg="#111827")
    header.pack(fill="x")

    logo = tk.Canvas(
        header,
        width=56,
        height=56,
        bg="#111827",
        highlightthickness=0,
        bd=0,
    )
    logo.pack(side="left", padx=(0, 14))
    logo.create_oval(5, 5, 51, 51, fill="#f0b429", outline="#f8d77b", width=2)
    logo.create_oval(13, 13, 43, 43, fill="#22c55e", outline="#a7f3d0", width=2)
    logo.create_oval(19, 18, 31, 30, fill="#ffffff", outline="")

    title_block = tk.Frame(header, bg="#111827")
    title_block.pack(side="left", fill="x", expand=True)

    tk.Label(
        title_block,
        text="Tiamat",
        bg="#111827",
        fg="#f8fafc",
        font=("Segoe UI Semibold", 18),
        anchor="w",
    ).pack(anchor="w")
    tk.Label(
        title_block,
        text="League client tray utilities",
        bg="#111827",
        fg="#94a3b8",
        font=("Segoe UI", 10),
        anchor="w",
    ).pack(anchor="w", pady=(2, 0))

    badge_label = tk.Label(
        card,
        text="STARTING",
        bg="#1d4ed8",
        fg="#eff6ff",
        font=("Segoe UI Semibold", 8),
        padx=10,
        pady=4,
    )
    badge_label.pack(anchor="w", pady=(16, 14))

    message_label = tk.Label(
        card,
        text=message,
        justify="left",
        wraplength=340,
        bg="#111827",
        fg="#e5e7eb",
        font=("Segoe UI", 10),
    )
    message_label.pack(anchor="w")

    hint_label = tk.Label(
        card,
        text="If the icon is not visible on the taskbar, check the Windows hidden icons area.",
        justify="left",
        wraplength=340,
        bg="#111827",
        fg="#7dd3fc",
        font=("Segoe UI", 9),
    )
    hint_label.pack(anchor="w", pady=(10, 0))

    progress = ttk.Progressbar(
        card,
        mode="indeterminate",
        length=280,
        style="Startup.Horizontal.TProgressbar",
    )
    progress.pack(fill="x", pady=(16, 0))
    progress.start(12)

    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x_pos = (root.winfo_screenwidth() - width) // 2
    y_pos = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    completion_applied = False

    def read_state():
        try:
            return state_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def close_window():
        progress.stop()
        root.destroy()

    def poll_state():
        nonlocal completion_applied

        if not psutil.pid_exists(parent_pid):
            close_window()
            return

        state = read_state()
        if state == "close":
            close_window()
            return

        if state == "complete" and not completion_applied:
            completion_applied = True
            progress.stop()
            progress.configure(mode="determinate", value=100)
            badge_label.configure(text="RUNNING IN TRAY", bg="#15803d")
            message_label.configure(
                text="Tiamat started successfully. The app will keep running in the system tray."
            )
            hint_label.configure(
                text="Right-click the tray icon to open the menu.",
                fg="#86efac",
            )
            root.after(STARTUP_SPLASH_DONE_DELAY_MS, close_window)
            return

        root.after(STARTUP_SPLASH_POLL_MS, poll_state)

    poll_state()

    try:
        root.mainloop()
    finally:
        try:
            state_path.unlink()
        except OSError:
            pass


class StartupSplash:
    def __init__(self, title, message):
        self.title = title
        self.message = message
        self._process = None
        self._state_path = None

    def show(self):
        if self._process is not None:
            return

        self._state_path = Path(tempfile.gettempdir()) / (
            f"tiamat-startup-{os.getpid()}-{uuid.uuid4().hex}.state"
        )
        self._write_state("starting")

        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._process = subprocess.Popen(
                self._command(),
                creationflags=creationflags,
            )
        except Exception:
            self._cleanup_state_file()
            self._process = None

    def complete(self):
        self._write_state("complete")

    def close(self, wait=False, timeout=1.5):
        self._write_state("close")

        if wait and self._process is not None:
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                pass

        if self._process is not None and self._process.poll() is not None:
            self._process = None
            self._cleanup_state_file()

    def _command(self):
        base_command = [
            sys.executable,
            STARTUP_SPLASH_ARG,
            str(self._state_path),
            str(os.getpid()),
            self.title,
            self.message,
        ]

        if getattr(sys, "frozen", False):
            return base_command
        return [sys.executable, str(Path(__file__).resolve())] + base_command[1:]

    def _write_state(self, state):
        if self._state_path is None:
            return

        try:
            self._state_path.write_text(state, encoding="utf-8")
        except OSError:
            pass

    def _cleanup_state_file(self):
        if self._state_path is None:
            return

        try:
            self._state_path.unlink()
        except OSError:
            pass
        self._state_path = None


def _handle_startup_splash_invocation():
    if len(sys.argv) < 2 or sys.argv[1] != STARTUP_SPLASH_ARG:
        return False

    if len(sys.argv) != 6:
        raise SystemExit(1)

    _show_startup_splash_window(
        state_path=Path(sys.argv[2]),
        parent_pid=int(sys.argv[3]),
        title=sys.argv[4],
        message=sys.argv[5],
    )
    return True


if __name__ == "__main__":
    if _handle_startup_splash_invocation():
        sys.exit(0)

    logger = configure_logging()
    install_exception_hooks(logger)
    instance = SingleInstance("TiamatSystemTray")
    startup_splash = None

    logger.info("Tiamat startup requested.")

    try:
        if not instance.acquire():
            logger.info("Blocked a second Tiamat instance.")
            _show_transient_notice("Tiamat", "Tiamat is already running.")
            sys.exit(0)

        logger.info("Tiamat instance lock acquired.")
        startup_splash = StartupSplash(
            "Tiamat",
            "Starting Tiamat and preparing the tray icon. This should only take a moment.",
        )
        startup_splash.show()
        TrayController(on_ready=startup_splash.complete).run()
        logger.info("Tiamat exited normally.")
    except SystemExit:
        raise
    except Exception:
        if startup_splash is not None:
            startup_splash.close(wait=True)
        logger.exception("Tiamat crashed before normal shutdown.")
        _show_message(
            "error",
            "Tiamat",
            "Tiamat encountered an unexpected error and was closed.",
        )
        sys.exit(1)
    finally:
        if startup_splash is not None:
            startup_splash.close(wait=True)
        instance.release()
        logger.info("Tiamat instance lock released.")
