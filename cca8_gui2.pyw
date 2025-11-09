# cca8_gui2.pyw  (double-click from Windows)


import os, subprocess, sys, tkinter as tk
from tkinter import messagebox

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(ROOT, "cca8_run.py")

def open_console():
    # Open a new console window running CCA8; /k keeps it open after exit.
    subprocess.Popen(["cmd", "/k", "py", "-3.11", RUNNER], cwd=ROOT)

def run_preflight():
    # Also open in a console so you can see the output live
    subprocess.Popen(["cmd", "/k", "py", "-3.11", RUNNER, "--preflight"], cwd=ROOT)

def open_log():
    # If you have a log file path, open it in Notepad
    log_path = os.path.join(ROOT, "cca8.log")
    try:
        os.startfile(log_path)
    except OSError:
        messagebox.showinfo("CCA8", "Log file not found.")

app = tk.Tk()
app.title("CCA8 Launcher")
tk.Button(app, text="Open CCA8 Console", width=24, command=open_console).pack(padx=12, pady=8)
tk.Button(app, text="Run Preflight (Console)", width=24, command=run_preflight).pack(padx=12, pady=8)
tk.Button(app, text="Open Log", width=24, command=open_log).pack(padx=12, pady=8)
app.mainloop()
