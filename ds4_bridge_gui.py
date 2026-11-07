"""
FC 27 DualShock 4 Bridge - friendly window

A step-by-step setup wizard plus a Start/Stop panel around ds4_xbox_bridge.py.
The bridge itself (the part that does the real work) runs as a separate process;
this window only checks what is installed, helps with each setup step, and shows
live status.

Run it with Start-DS4-Bridge-GUI.bat (double-click).
"""
import glob
import importlib
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk

APP_TITLE = "FC 27 DualShock 4 Bridge"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRIDGE = os.path.join(HERE, "ds4_xbox_bridge.py")
SETTINGS_PATH = os.path.join(HERE, "settings.json")
HIDHIDE_URL = "https://github.com/nefarius/HidHide/releases"
VIGEM_URL = "https://github.com/nefarius/ViGEmBus/releases"
KOFI_URL = "https://ko-fi.com/xmo07"

IS_WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

GREEN, RED, AMBER, GREY = "#1a7f37", "#c62828", "#b26a00", "#6b7280"
COLORS = {"ok": GREEN, "bad": RED, "warn": AMBER, "idle": GREY}
ICONS = {"ok": "\u2714", "bad": "\u2716", "warn": "\u25cf", "idle": "\u25cb"}


# ---------------------------------------------------------------- helpers
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:  # noqa: BLE001
        pass


def console_python():
    """python.exe (not pythonw.exe): this is the program HidHide must whitelist."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(cand):
            return cand
    return exe


def pkg_installed(name):
    importlib.invalidate_caches()
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:  # noqa: BLE001
        return False


def service_state(name):
    """True = service exists, False = does not exist, None = could not tell."""
    if not IS_WINDOWS:
        return None
    try:
        r = subprocess.run(["sc", "query", name], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=8, creationflags=NO_WINDOW)
        if r.returncode == 0:
            return True
        if r.returncode == 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
            return False
    except Exception:  # noqa: BLE001
        pass
    return None


def find_hidhide_client():
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), r"C:\Program Files"]
    for root in filter(None, dict.fromkeys(roots)):
        pattern = os.path.join(root, "Nefarius Software Solutions", "**", "HidHideClient.exe")
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    return None


class Scrollable(ttk.Frame):
    """A vertically scrollable area; put widgets in .inner"""

    def __init__(self, parent):
        super().__init__(parent)
        bg = ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=bg)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


# ---------------------------------------------------------------- app
class App:
    def __init__(self, root, bridge_path):
        self.root = root
        self.bridge = bridge_path
        self.python = console_python()
        self.settings = load_settings()
        self.proc = None
        self.installing = False
        self.virtual_failed = False
        self.q = queue.Queue()

        root.title(APP_TITLE)
        root.geometry("860x760")
        root.minsize(760, 620)
        self._set_icon()
        self._style()

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        self.tab_setup = ttk.Frame(self.nb, padding=10)
        self.tab_play = ttk.Frame(self.nb, padding=14)
        self.nb.add(self.tab_setup, text="   1. Setup   ")
        self.nb.add(self.tab_play, text="   2. Play   ")

        self._build_log()      # bottom panel, created first so every tab can log
        self._build_footer()
        self._build_setup()
        self._build_play()

        self.refresh()
        if self.settings.get("setup_done"):
            self.nb.select(self.tab_play)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(120, self.poll)
        if self.settings.get("setup_done") and self.settings.get("autostart"):
            root.after(600, self.start_bridge)

    # ---- icon
    def _set_icon(self):
        ico = os.path.join(HERE, "controller.ico")
        png = os.path.join(HERE, "controller_icon.png")
        if IS_WINDOWS and os.path.exists(ico):
            try:
                self.root.iconbitmap(default=ico)   # window, taskbar, Alt+Tab and dialogs
                return
            except tk.TclError:
                pass
        if os.path.exists(png):
            try:
                self._icon_img = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._icon_img)
            except tk.TclError:
                pass

    def create_shortcut(self):
        """Desktop shortcut that starts the window, with the controller icon."""
        launcher = os.path.join(HERE, "Start-DS4-Bridge-GUI.bat")
        ico = os.path.join(HERE, "controller.ico")
        if not IS_WINDOWS:
            messagebox.showinfo(APP_TITLE, "Desktop shortcuts are only created on Windows.")
            return
        if not os.path.exists(launcher):
            messagebox.showerror(APP_TITLE, "Start-DS4-Bridge-GUI.bat is missing. Keep all files from the "
                                            "download in the same folder.")
            return
        script = (
            "$d = [Environment]::GetFolderPath('Desktop');"
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'FC 27 DS4 Bridge.lnk'));"
            "$s.TargetPath = $env:DS4_TARGET;"
            "$s.WorkingDirectory = $env:DS4_HERE;"
            "$s.IconLocation = $env:DS4_ICON;"
            "$s.WindowStyle = 7;"
            "$s.Description = 'FC 27 DualShock 4 Bridge';"
            "$s.Save();"
            "Write-Output (Join-Path $d 'FC 27 DS4 Bridge.lnk')"
        )
        env = dict(os.environ, DS4_TARGET=launcher, DS4_HERE=HERE, DS4_ICON=ico + ",0")
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, timeout=30, env=env, creationflags=NO_WINDOW)
        except Exception as e:  # noqa: BLE001
            self.log(f"Could not create the shortcut: {e}")
            messagebox.showwarning(APP_TITLE, f"Could not create the shortcut:\n{e}")
            return
        if r.returncode == 0:
            self.log("Desktop shortcut created: " + (r.stdout.strip() or "FC 27 DS4 Bridge.lnk"))
            messagebox.showinfo(APP_TITLE, "Done. A shortcut called 'FC 27 DS4 Bridge' is now on your Desktop.\n\n"
                                           "Tip: right-click it and choose 'Pin to taskbar' if you like.")
        else:
            self.log("Shortcut failed: " + (r.stderr.strip() or r.stdout.strip() or f"code {r.returncode}"))
            messagebox.showwarning(APP_TITLE, "Could not create the shortcut. See the Activity log for details.")

    # ---- look
    def _style(self):
        st = ttk.Style()
        for theme in (("vista", "clam") if IS_WINDOWS else ("clam",)):
            try:
                st.theme_use(theme)
                break
            except tk.TclError:
                continue
        base = ("Segoe UI", 10)
        st.configure("TLabel", font=base)
        st.configure("TButton", font=base, padding=(10, 5))
        st.configure("TCheckbutton", font=base)
        st.configure("StepTitle.TLabel", font=("Segoe UI", 11, "bold"))
        st.configure("Desc.TLabel", foreground="#374151")
        st.configure("Badge.TLabel", font=("Segoe UI", 11, "bold"), foreground="white", background="#2563eb")
        st.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        st.configure("Big.TButton", font=("Segoe UI", 13, "bold"), padding=(18, 12))
        st.configure("Head.TLabel", font=("Segoe UI", 14, "bold"))

    @staticmethod
    def set_status(label, kind, text):
        label.configure(text=f"{ICONS[kind]} {text}", foreground=COLORS[kind])

    # ---- bottom activity log
    def _build_log(self):
        box = ttk.LabelFrame(self.root, text=" Activity log ", padding=6)
        box.pack(fill="x", padx=10, pady=(0, 10))
        self.log_text = tk.Text(box, height=6, wrap="word", state="disabled", font=("Consolas", 9),
                                background="#111827", foreground="#e5e7eb", borderwidth=0)
        bar = ttk.Scrollbar(box, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=bar.set)
        self.log_text.pack(side="left", fill="x", expand=True)
        bar.pack(side="right", fill="y")

    # ---- footer with the support button
    def _build_footer(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(bar, text="Free, open-source tool. If it saved your match night, you can support it:",
                  style="Desc.TLabel").pack(side="left")
        self.btn_kofi = tk.Button(bar, text="☕  Support me on Ko-fi", command=self.open_kofi,
                                  bg="#ff5e5b", fg="white", activebackground="#e24b48", activeforeground="white",
                                  font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0,
                                  padx=14, pady=6, cursor="hand2")
        self.btn_kofi.pack(side="right")

    def open_kofi(self):
        webbrowser.open(KOFI_URL)

    def log(self, line):
        t = self.log_text
        t.configure(state="normal")
        t.insert("end", line + "\n")
        count = int(t.index("end-1c").split(".")[0])
        if count > 600:
            t.delete("1.0", f"{count - 600}.0")
        t.see("end")
        t.configure(state="disabled")

    # ---- setup tab
    def _step(self, parent, num, title, desc, with_status=True):
        f = ttk.Frame(parent, padding=(0, 10))
        f.pack(fill="x")
        ttk.Label(f, text=str(num), style="Badge.TLabel", width=3, anchor="center").grid(
            row=0, column=0, rowspan=3, sticky="n", padx=(0, 12))
        ttk.Label(f, text=title, style="StepTitle.TLabel").grid(row=0, column=1, sticky="w")
        status = None
        if with_status:
            status = ttk.Label(f, text="", style="Status.TLabel")
            status.grid(row=0, column=2, sticky="e")
        ttk.Label(f, text=desc, style="Desc.TLabel", wraplength=640, justify="left").grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(2, 0))
        actions = ttk.Frame(f)
        actions.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        f.columnconfigure(1, weight=1)
        ttk.Separator(parent).pack(fill="x")
        return status, actions

    def _build_setup(self):
        sc = Scrollable(self.tab_setup)
        sc.pack(fill="both", expand=True)
        p = sc.inner
        ttk.Label(p, text="Do these steps once, from top to bottom.", style="Head.TLabel").pack(anchor="w")
        ttk.Label(p, text="Steps with a status turn green by themselves. Press Re-check after installing something.",
                  style="Desc.TLabel").pack(anchor="w", pady=(2, 6))

        self.st_pkg, a = self._step(
            p, 1, "Install the Python packages",
            "Installs the two small libraries the bridge needs. A ViGEmBus installer window may pop up during this: "
            "accept it, and restart Windows if it asks.")
        self.btn_install = ttk.Button(a, text="Install now", command=self.install_packages)
        self.btn_install.pack(side="left")

        self.st_vigem, a = self._step(
            p, 2, "ViGEmBus driver (the virtual Xbox controller)",
            "Normally installed by step 1. If it still says 'not detected' after step 1 and a restart, "
            "download and install it yourself.")
        ttk.Button(a, text="Download ViGEmBus", command=lambda: webbrowser.open(VIGEM_URL)).pack(side="left")

        self.st_hh, a = self._step(
            p, 3, "HidHide (hides your real controller from the game)",
            "Download the latest setup, install it, then RESTART WINDOWS. Without the restart it will not work.")
        ttk.Button(a, text="Download HidHide", command=lambda: webbrowser.open(HIDHIDE_URL)).pack(side="left")

        _, a = self._step(
            p, 4, "Tell HidHide about this program",
            "Open HidHide Configuration Client, go to the Applications tab, press the + button and paste this path. "
            "(This lets the bridge still see your real controller.)", with_status=False)
        r1 = ttk.Frame(a)
        r1.pack(anchor="w")
        ent = ttk.Entry(r1, width=64)
        ent.insert(0, self.python)
        ent.configure(state="readonly")
        ent.pack(side="left", padx=(0, 6))
        ttk.Button(r1, text="Copy path", command=self.copy_path).pack(side="left")
        r2 = ttk.Frame(a)
        r2.pack(anchor="w", pady=(8, 0))
        ttk.Button(r2, text="Open HidHide", command=self.open_hidhide).pack(side="left", padx=(0, 12))
        self.var_whitelist = tk.BooleanVar(value=bool(self.settings.get("whitelist_done")))
        ttk.Checkbutton(r2, text="Done: path added", variable=self.var_whitelist,
                        command=self._save_checks).pack(side="left")

        _, a = self._step(
            p, 5, "Hide your DualShock 4",
            "Turn your DS4 on over Bluetooth (PS button). In HidHide open the Devices tab, tick your DualShock 4 "
            "(it shows as 'Wireless Controller' or 'PS4 Controller'; tick both if you see two), "
            "then tick 'Enable device hiding'. Do not tick any Xbox entry.", with_status=False)
        self.var_hidden = tk.BooleanVar(value=bool(self.settings.get("hidden_done")))
        ttk.Checkbutton(a, text="Done: controller hidden and hiding enabled", variable=self.var_hidden,
                        command=self._save_checks).pack(side="left")

        _, a = self._step(
            p, 6, "Check that it worked",
            "Go to the Play tab and press Start. Then open the Windows controller test below: you should see ONLY "
            "'Xbox 360 Controller for Windows', and its bars should move when you move the sticks.",
            with_status=False)
        ttk.Button(a, text="Open Windows controller test", command=self.open_joycpl).pack(side="left", padx=(0, 10))
        ttk.Button(a, text="Go to Play tab", command=self.finish_setup).pack(side="left")

        bar = ttk.Frame(self.tab_setup)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Re-check", command=self.refresh).pack(side="left")

    # ---- play tab
    def _build_play(self):
        p = self.tab_play
        ttk.Label(p, text="Play", style="Head.TLabel").pack(anchor="w")
        ttk.Label(p, text="Press Start, wait for both lights to turn green, then launch FC 27.",
                  style="Desc.TLabel").pack(anchor="w", pady=(2, 12))

        grid = ttk.Frame(p)
        grid.pack(anchor="w", fill="x")
        ttk.Label(grid, text="Virtual Xbox controller", width=26).grid(row=0, column=0, sticky="w", pady=3)
        self.st_virtual = ttk.Label(grid, text="", style="Status.TLabel")
        self.st_virtual.grid(row=0, column=1, sticky="w")
        ttk.Label(grid, text="Your DualShock 4", width=26).grid(row=1, column=0, sticky="w", pady=3)
        self.st_ds4 = ttk.Label(grid, text="", style="Status.TLabel")
        self.st_ds4.grid(row=1, column=1, sticky="w")
        self.set_status(self.st_virtual, "idle", "Not running")
        self.set_status(self.st_ds4, "idle", "Not running")

        self.btn_toggle = ttk.Button(p, text="Start bridge", style="Big.TButton", command=self.toggle_bridge)
        self.btn_toggle.pack(anchor="w", pady=(16, 8))

        self.tip = ttk.Label(p, text="", style="Desc.TLabel", wraplength=720, justify="left")
        self.tip.pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(p)
        row.pack(anchor="w", pady=(0, 8))
        ttk.Button(row, text="Open Windows controller test", command=self.open_joycpl).pack(side="left", padx=(0, 10))
        ttk.Button(row, text="Back to Setup", command=lambda: self.nb.select(self.tab_setup)).pack(side="left",
                                                                                                  padx=(0, 10))
        ttk.Button(row, text="Create desktop shortcut", command=self.create_shortcut).pack(side="left")

        self.var_auto = tk.BooleanVar(value=bool(self.settings.get("autostart")))
        ttk.Checkbutton(p, text="Start the bridge automatically when I open this program",
                        variable=self.var_auto, command=self._save_checks).pack(anchor="w", pady=(6, 0))

        note = ("Keep this window open while you play. Close FC 27 first, then press Stop.\n"
                "Unofficial community tool, not affiliated with EA. Use at your own risk.")
        ttk.Label(p, text=note, style="Desc.TLabel", justify="left").pack(anchor="w", pady=(16, 0))
        self._set_tip("idle")

    def _set_tip(self, kind):
        tips = {
            "idle": "Nothing is running. Press Start bridge.",
            "starting": "Starting... this takes a second.",
            "waiting": "Turn on your DualShock 4 (press the PS button). If you already hid it with HidHide and it "
                       "is still not found, check step 4 on the Setup tab (the program path).",
            "ready": "All good. Leave this window open and launch FC 27 now.",
            "lost": "The controller disconnected. Turn it back on and the bridge will pick it up by itself.",
            "failed": "The virtual controller could not be created: ViGEmBus is probably missing. "
                      "Go to Setup, step 2, install it, restart Windows and try again.",
        }
        self.tip.configure(text=tips[kind])

    # ---- settings
    def _save_checks(self):
        self.settings["whitelist_done"] = bool(self.var_whitelist.get())
        self.settings["hidden_done"] = bool(self.var_hidden.get())
        self.settings["autostart"] = bool(self.var_auto.get())
        save_settings(self.settings)

    def finish_setup(self):
        self.settings["setup_done"] = True
        save_settings(self.settings)
        self.nb.select(self.tab_play)

    # ---- detection
    def refresh(self):
        pk = pkg_installed("pygame") and pkg_installed("vgamepad")
        self.set_status(self.st_pkg, "ok" if pk else "bad", "Installed" if pk else "Not installed")

        v = service_state("ViGEmBus")
        if v is True:
            self.set_status(self.st_vigem, "ok", "Detected")
        elif v is False:
            self.set_status(self.st_vigem, "warn", "Not detected yet")
        else:
            self.set_status(self.st_vigem, "idle", "Unknown (Start will confirm)")

        client = find_hidhide_client()
        h = True if client else service_state("HidHide")
        if h is True:
            self.set_status(self.st_hh, "ok", "Detected")
        elif h is False:
            self.set_status(self.st_hh, "bad", "Not installed")
        else:
            self.set_status(self.st_hh, "idle", "Unknown")
        self.hidhide_client = client

    # ---- small actions
    def copy_path(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.python)
        self.log("Path copied to the clipboard: " + self.python)

    def open_hidhide(self):
        client = getattr(self, "hidhide_client", None) or find_hidhide_client()
        if client:
            try:
                subprocess.Popen([client], stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"Could not start HidHide directly: {e}")
        messagebox.showinfo(APP_TITLE, "Open 'HidHide Configuration Client' from the Windows Start menu.\n\n"
                                       "If it is not there, HidHide is not installed yet (step 3).")

    def open_joycpl(self):
        try:
            subprocess.Popen(["control.exe", "joy.cpl"], stdin=subprocess.DEVNULL)
        except Exception:  # noqa: BLE001
            messagebox.showinfo(APP_TITLE, "Press Win+R, type  joy.cpl  and press Enter.")

    # ---- package install
    def install_packages(self):
        if self.installing:
            return
        self.installing = True
        self.btn_install.configure(state="disabled", text="Installing...")
        self.log("Installing pygame-ce and vgamepad. If a ViGEmBus window or a Windows prompt appears, accept it.")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        cmd = [self.python, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade",
               "pygame-ce", "vgamepad"]
        rc = -1
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
            for line in p.stdout:
                line = line.rstrip()
                if line:
                    self.q.put(("log", line))
            rc = p.wait()
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"Install failed: {e}"))
        self.q.put(("install_done", rc))

    def on_install_done(self, rc):
        self.installing = False
        self.btn_install.configure(state="normal", text="Install now")
        self.refresh()
        if rc == 0:
            self.log("Packages installed.")
        else:
            self.log(f"Install finished with code {rc}. Check your internet connection and press Install now again.")
            messagebox.showwarning(APP_TITLE, "The install did not finish. Check your internet connection and try again.\n"
                                              "See the Activity log for details.")

    # ---- bridge process
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def toggle_bridge(self):
        if self.running():
            self.stop_bridge()
        else:
            self.start_bridge()

    def start_bridge(self):
        if self.running():
            return
        if not (pkg_installed("pygame") and pkg_installed("vgamepad")):
            messagebox.showinfo(APP_TITLE, "The Python packages are not installed yet.\n\nGo to Setup and press "
                                           "'Install now' in step 1.")
            self.nb.select(self.tab_setup)
            return
        if not os.path.exists(self.bridge):
            messagebox.showerror(APP_TITLE, "ds4_xbox_bridge.py is missing. Keep all files from the download in "
                                            "the same folder.")
            return
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        self.virtual_failed = False
        try:
            self.proc = subprocess.Popen([self.python, "-u", self.bridge], stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
                                         env=env, cwd=HERE)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Could not start the bridge:\n{e}")
            return
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
        self.btn_toggle.configure(text="Stop bridge")
        self.set_status(self.st_virtual, "warn", "Starting...")
        self.set_status(self.st_ds4, "idle", "Waiting...")
        self._set_tip("starting")
        self.log("--- bridge started ---")

    def _reader(self, proc):
        try:
            for line in proc.stdout:
                self.q.put(("bridge", proc, line.rstrip()))
        except Exception:  # noqa: BLE001
            pass
        rc = proc.wait()
        self.q.put(("exit", proc, rc))

    def stop_bridge(self):
        p = self.proc
        if p is None or p.poll() is not None:
            return
        self.btn_toggle.configure(state="disabled")
        self.log("Stopping the bridge...")
        try:
            p.terminate()
        except Exception:  # noqa: BLE001
            pass
        threading.Thread(target=self._kill_later, args=(p,), daemon=True).start()

    @staticmethod
    def _kill_later(p):
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass

    # ---- events from the bridge
    def on_bridge_line(self, proc, line):
        if not line.strip() or set(line.strip()) == {"="}:
            return
        self.log(line)
        if proc is not self.proc:
            return
        low = line.lower()
        if "virtual xbox 360 controller created" in low:
            self.set_status(self.st_virtual, "ok", "Ready")
            self.set_status(self.st_ds4, "warn", "Looking for your DualShock 4...")
            self._set_tip("waiting")
        elif "could not create the virtual xbox controller" in low:
            self.virtual_failed = True
            self.set_status(self.st_virtual, "bad", "Failed (ViGEmBus missing?)")
            self.set_status(self.st_ds4, "idle", "Not running")
            self._set_tip("failed")
        elif low.startswith("connected:"):
            self.set_status(self.st_ds4, "ok", line.split(":", 1)[1].strip() or "Connected")
            self._set_tip("ready")
        elif "disconnected" in low:
            self.set_status(self.st_ds4, "warn", "Disconnected")
            self._set_tip("lost")
        elif "no dualshock 4 visible" in low:
            self.set_status(self.st_ds4, "warn", "Not found yet")
            self._set_tip("waiting")
        elif "missing package" in low or "could not load vgamepad" in low:
            self.set_status(self.st_virtual, "bad", "Python packages missing")

    def on_exit(self, proc, rc):
        if proc is not self.proc:
            return
        self.proc = None
        self.btn_toggle.configure(text="Start bridge", state="normal")
        self.log(f"--- bridge stopped (code {rc}) ---")
        if not self.virtual_failed:
            self.set_status(self.st_virtual, "idle", "Not running")
            self.set_status(self.st_ds4, "idle", "Not running")
            self._set_tip("idle")
        else:
            messagebox.showwarning(APP_TITLE, "The virtual Xbox controller could not be created.\n\n"
                                              "ViGEmBus is probably not installed. Install it (Setup, step 2), "
                                              "restart Windows and try again.")

    def poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.log(item[1])
                elif kind == "bridge":
                    self.on_bridge_line(item[1], item[2])
                elif kind == "exit":
                    self.on_exit(item[1], item[2])
                elif kind == "install_done":
                    self.on_install_done(item[1])
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

    def on_close(self):
        if self.running():
            if not messagebox.askokcancel(APP_TITLE, "The bridge is running. Closing this window stops it and "
                                                     "FC 27 will lose the controller.\n\nClose anyway?"):
                return
            try:
                self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        self.root.destroy()


def main():
    bridge = DEFAULT_BRIDGE
    if "--bridge" in sys.argv:  # for testing
        bridge = sys.argv[sys.argv.index("--bridge") + 1]
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
        try:
            # own taskbar identity, so Windows shows our icon instead of grouping us under "Python"
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xmo07.FC27DS4Bridge")
        except Exception:  # noqa: BLE001
            pass
    try:
        root = tk.Tk()
        App(root, bridge)
        root.mainloop()
    except Exception:  # noqa: BLE001
        import traceback
        try:
            with open(os.path.join(HERE, "gui_error.log"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:  # noqa: BLE001
            pass
        raise


if __name__ == "__main__":
    main()
