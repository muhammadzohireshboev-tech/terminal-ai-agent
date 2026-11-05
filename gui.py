"""agent.py ustida tkinter GUI: suhbat oynasi, jonli status, provayder paneli."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

import agent

LINE_STYLES = {
    "siz": ("#0a58ca", "right"),
    "agent": ("#0f7b3a", "left"),
    "xato": ("#b3261e", "left"),
    "tizim": ("#666666", "left"),
}


class AgentWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.messages: list = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
        self.client = None
        self.model = ""
        self.busy = False

        root.title("AI Agent")
        root.geometry("800x580")
        root.minsize(560, 400)

        self.header = ttk.Label(root, text="sozlanmoqda...", padding=(12, 8), anchor="w")
        self.header.pack(fill="x")

        self.log = scrolledtext.ScrolledText(root, wrap="word", state="disabled", padx=12, pady=8)
        self.log.pack(fill="both", expand=True)
        for name, (color, _) in LINE_STYLES.items():
            self.log.tag_configure(name, foreground=color, font=("Segoe UI", 10, "bold"))

        self.statusbar = ttk.Label(root, text="tayyor", padding=(12, 4), anchor="w")
        self.statusbar.pack(fill="x")

        row = ttk.Frame(root, padding=(12, 8))
        row.pack(fill="x")
        self.entry = ttk.Entry(row)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _event: self.submit())
        self.send_button = ttk.Button(row, text="Yuborish", width=11, command=self.submit)
        self.send_button.pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Tarixni tozalash", width=16, command=self.reset).pack(side="left", padx=(8, 0))

        agent.load_env()
        agent.STATUS_HOOK = lambda text: self.events.put(("status", text))
        threading.Thread(target=self.connect, daemon=True).start()
        root.after(80, self.pump)
        self.entry.focus_set()

    def connect(self) -> None:
        try:
            provider, model, client = agent.connect()
            self.events.put(("ready", provider, model, client))
        except Exception as exc:
            self.events.put(("config_error", str(exc)))

    def write(self, kind: str, text: str) -> None:
        _, side = LINE_STYLES[kind]
        self.log.configure(state="normal")
        if side == "right":
            self.log.insert("end", "\n")
        self.log.insert("end", f"{kind}> ", kind)
        self.log.insert("end", text + "\n\n" if side == "right" else text + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_button.configure(state="disabled" if busy else "normal")
        if busy:
            self.statusbar.configure(text="bajarilmoqda...")

    def submit(self) -> None:
        text = self.entry.get().strip()
        if not text or self.busy or self.client is None:
            return
        self.entry.delete(0, "end")
        if text in ("/exit", "/quit", "/reset"):
            self.reset()
            return
        self.messages.append({"role": "user", "content": text})
        self.write("siz", text)
        self.set_busy(True)
        threading.Thread(target=self.ask, args=(agent.shorten(text),), daemon=True).start()

    def ask(self, task: str) -> None:
        try:
            answer = agent.chat(self.client, self.model, self.messages, task)
            self.events.put(("answer", answer))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {str(exc)[:300]}"))

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
        self.write("tizim", "tarix tozalandi")

    def pump(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "status":
                self.statusbar.configure(text=event[1])
            elif kind == "ready":
                _, provider, model, client = event
                self.client, self.model = client, model
                self.header.configure(text=f"provayder: {provider} | model: {model} | papka: {agent.ROOT}")
                self.write("tizim", "agent tayyor. Savol yozing.")
            elif kind == "config_error":
                self.header.configure(text="sozlama xatosi")
                self.write("xato", event[1])
            elif kind == "answer":
                self.set_busy(False)
                self.statusbar.configure(text="tayyor")
                self.write("agent", event[1])
            elif kind == "error":
                self.set_busy(False)
                self.statusbar.configure(text="xato")
                self.write("xato", event[1])
        self.root.after(80, self.pump)


def main() -> None:
    root = tk.Tk()
    AgentWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
