import sys
import tkinter as tk
from tkinter import messagebox

from logging_setup import configure_logging, install_exception_hooks
from single_instance import SingleInstance
from tray_controller import TrayController


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


if __name__ == "__main__":
    logger = configure_logging()
    install_exception_hooks(logger)
    instance = SingleInstance("TiamatSystemTray")

    logger.info("Tiamat startup requested.")

    try:
        if not instance.acquire():
            logger.info("Blocked a second Tiamat instance.")
            _show_transient_notice("Tiamat", "Tiamat is already running.")
            sys.exit(0)

        logger.info("Tiamat instance lock acquired.")
        TrayController().run()
        logger.info("Tiamat exited normally.")
    except SystemExit:
        raise
    except Exception:
        logger.exception("Tiamat crashed before normal shutdown.")
        _show_message(
            "error",
            "Tiamat",
            "Tiamat encountered an unexpected error and was closed.",
        )
        sys.exit(1)
    finally:
        instance.release()
        logger.info("Tiamat instance lock released.")
