"""Small cross-platform desktop controller for a local JupyterLab server."""

from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText


URL_PATTERN = re.compile(r"https?://[^\s\x1b]+")
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def jupyter_command(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "jupyter",
        "lab",
        "--no-browser",
        "--ServerApp.ip=127.0.0.1",
        f"--ServerApp.port={port}",
        "--ServerApp.port_retries=0",
    ]


class JupyterLabManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JupyterLab Manager")
        self.root.minsize(600, 380)

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str | None] = queue.Queue()
        self.server_url: str | None = None
        self.stop_deadline: float | None = None

        self.port_var = tk.StringVar(value="8888")
        self.status_var = tk.StringVar(value="Gestoppt")
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        toolbar = ttk.Frame(container)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Label(toolbar, text="Port").pack(side="left")
        self.port_input = ttk.Spinbox(
            toolbar,
            from_=1,
            to=65535,
            textvariable=self.port_var,
            width=7,
        )
        self.port_input.pack(side="left", padx=(6, 12))

        self.start_button = ttk.Button(toolbar, text="Starten", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            toolbar, text="Stoppen", command=self.stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=6)
        self.browser_button = ttk.Button(
            toolbar,
            text="Im Browser öffnen",
            command=self.open_browser,
            state="disabled",
        )
        self.browser_button.pack(side="left")

        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        self.log_view = ScrolledText(container, state="disabled", wrap="word", height=20)
        self.log_view.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text=f"Arbeitsverzeichnis: {Path.cwd()}",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ungültiger Port", "Der Port muss zwischen 1 und 65535 liegen.")
            return

        self.server_url = None
        self.browser_button.configure(state="disabled")
        self._write_log(f"Starte JupyterLab auf Port {port} ...")
        try:
            self.process = subprocess.Popen(
                jupyter_command(port),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            self.process = None
            self.status_var.set("Start fehlgeschlagen")
            self._write_log(f"JupyterLab konnte nicht gestartet werden: {error}")
            return

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Startet ...")
        threading.Thread(target=self._read_process_output, daemon=True).start()
        self._poll_process()

    def _read_process_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                self.log_queue.put(line.rstrip())
        finally:
            self.log_queue.put(None)

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.stop_deadline = time.monotonic() + 5
        self.status_var.set("Wird gestoppt ...")
        self.process.terminate()

    def _poll_process(self) -> None:
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            if self.stop_deadline is not None and time.monotonic() >= self.stop_deadline:
                process.kill()
                self.stop_deadline = None
            self.root.after(200, self._poll_process)
            return

        return_code = process.returncode
        self.process = None
        self.stop_deadline = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.browser_button.configure(state="normal" if self.server_url else "disabled")
        self.status_var.set("Gestoppt" if return_code == 0 else f"Beendet ({return_code})")

    def _drain_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if line is None:
                continue
            cleaned_line = ANSI_PATTERN.sub("", line)
            match = URL_PATTERN.search(cleaned_line)
            if match:
                self.server_url = match.group(0).rstrip(".,)")
                self.browser_button.configure(state="normal")
                self.status_var.set("Läuft")
            self._write_log(cleaned_line)
        self.root.after(100, self._drain_log_queue)

    def _write_log(self, text: str) -> None:
        self.log_view.configure(state="normal")
        self.log_view.insert("end", text + "\n")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def open_browser(self) -> None:
        if self.server_url:
            webbrowser.open(self.server_url)

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    JupyterLabManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()