import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import os
import threading
import queue
import json
import logging
import logging.handlers
from tkinter import messagebox
from tkinter import filedialog
import time
import base64 # For embedding icons

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# --- Base64 encoded icons (GIF format) ---
# Simple 1x1 pixel colored GIFs for compatibility with tk.PhotoImage(data=...)
# These are placeholders. For better icons, generate 16x16 or 20x20 GIF images
# using an image editor and convert them to Base64 (e.g., via https://www.base64-image.de/).
# Replace these strings with your own generated Base64 GIF data.
ICON_PLAY = "R0lGODlhAQABAIAAAAUEBAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Green
ICON_STOP = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Red
ICON_RELOAD = "R0lGODlhAQABAIAAAACYmSH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Aqua (placeholder)
ICON_ADD = "R0lGODlhAQABAIAAAAUEBAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Green
ICON_EDIT = "R0lGODlhAQABAIAAAAUEBAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Blue
ICON_DELETE = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Red
ICON_FOLDER = "R0lGODlhAQABAIAAAAwMDCH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Dark Grey
ICON_CONFIG = "R0lGODlhAQABAIAAAAgICAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" # Light Grey


class Tooltip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                      background="#ffffe0", relief='solid', borderwidth=1,
                      font=("Helvetica", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None


class Switch(ttk.Frame):
    """A custom switch widget that can be toggled."""
    def __init__(self, parent, variable, command=None, **kwargs):
        # Inherit the parent's style to blend in
        try:
            parent_style = parent.cget("style")
        except tk.TclError:
            parent_style = parent.winfo_class() # Fallback for non-ttk widgets

        super().__init__(parent, style=parent_style, **kwargs)

        self.variable = variable
        self.command = command
        self.variable.trace_add("write", self._update_switch)

        # Determine background color from our own style
        style = ttk.Style()
        bg_color = style.lookup(self.cget("style"), "background")

        self.canvas = tk.Canvas(self, width=40, height=20, bg=bg_color, highlightthickness=0)
        self.canvas.pack()

        # Colors
        self.on_color = "#007acc" # ACCENT_COLOR
        self.off_color = "#cccccc"
        self.handle_color = "white"

        # Dimensions
        self.width = 40
        self.height = 20
        self.handle_radius = (self.height - 6) / 2
        self.track_radius = self.height / 2

        self.canvas.bind("<Button-1>", self._on_click)
        self._draw_switch(self.variable.get())

    def _draw_switch(self, is_on):
        self.canvas.delete("all")
        
        # Track
        # Using a set of ovals and a rectangle to create a rounded track
        self.canvas.create_oval(0, 0, self.height, self.height, fill=self.on_color if is_on else self.off_color, outline="")
        self.canvas.create_oval(self.width - self.height, 0, self.width, self.height, fill=self.on_color if is_on else self.off_color, outline="")
        self.canvas.create_rectangle(self.track_radius, 0, self.width - self.track_radius, self.height, fill=self.on_color if is_on else self.off_color, outline="")

        # Handle
        if is_on:
            x_pos = self.width - self.track_radius
        else:
            x_pos = self.track_radius
        
        self.canvas.create_oval(
            x_pos - self.handle_radius, 
            (self.height / 2) - self.handle_radius,
            x_pos + self.handle_radius,
            (self.height / 2) + self.handle_radius,
            fill=self.handle_color,
            outline=""
        )

    def _on_click(self, event):
        new_state = not self.variable.get()
        self.variable.set(new_state)
        if self.command:
            self.command()

    def _update_switch(self, *args):
        self._draw_switch(self.variable.get())


class BatchManager(tk.Tk):
    APP_NAME = "Batch Script Manager"
    APP_VERSION = "2.38" # Updated version

    # --- Styling Constants ---
    # Fonts
    DEFAULT_FONT = ("Segoe UI", 10) # Modern, clean font
    DEFAULT_MONOSPACE_FONT = ("Cascadia Code", 9) # Dev-friendly font
    # Fallback for monospace font if Cascadia Code is not available
    FALLBACK_MONOSPACE_FONT = ("Consolas", 9) 

    # Colors - Moderne Farbabstufungen wie im Backup Manager
    MAIN_BG_COLOR = "#f8f9fa"      # Haupt-Hintergrund
    ACCENT_COLOR = "#007acc"      # Hauptaktionen (blau)
    ACCENT_GREEN = "#28a745"      # Erfolg/Recovery (grün)
    ACCENT_SECONDARY = "#6c757d"  # Sekundäre Aktionen (grau)
    TEXT_COLOR_DARK = "#2c3e50"    # Haupttext
    TEXT_COLOR_LIGHT = "#ffffff"  # White for light text areas
    BUTTON_BG_NORMAL = "#e1e1e1"   # Neutral button background
    BUTTON_BG_HOVER = "#d3d3d3"    # Slightly darker on hover
    NOTEBOOK_TAB_BG_INACTIVE = "#e0e0e0"
    NOTEBOOK_TAB_BG_ACTIVE = "#ffffff"
    LOG_BG_COLOR = "#fafbfc"      # Log-Bereich (heller für Kontrast)
    LOG_FG_COLOR = "#2c3e50"      # Dunkler Text für Logs
    SPARKLINE_BG_COLOR = "#e8e8e8" # Light background for sparklines
    BORDER_LIGHT = "#e1e8ed"      # Leichte Rahmen

    OVERVIEW_SPARKLINE_WIDTH = 150  # Width for sparklines in overview
    OVERVIEW_SPARKLINE_HEIGHT = 40 # Height for sparklines in overview

    def __init__(self, scripts, global_start_delay=2, autostart_enabled=True, full_config_path="config.json"):
        super().__init__()
        self.title(self.APP_NAME)
        self.geometry("1200x900") # Start with a larger window for better log visibility
        self.minsize(1000, 700)   # Set a larger minimum size
        self.configure(bg=self.MAIN_BG_COLOR) # Set root window background

        self.full_config_path = full_config_path
        self.scripts = scripts
        self.global_start_delay = global_start_delay
        self.autostart_enabled_var = tk.BooleanVar(value=autostart_enabled)
        
        self.processes = {}
        self.threads = {}
        self.output_queue = queue.Queue()
        self.psutil_processes = {}
        self.log_queue = queue.Queue()
        self.logger, self.log_formatter = self._setup_logger() # Store formatter
        self.script_raw_output = {name: [] for name in scripts}
        self.cpu_history = {name: [0.0] * 20 for name in scripts} # Store last 20 CPU values for sparkline

        # Auto-scroll state for each script output tab
        self.autoscroll_vars = {name: tk.BooleanVar(value=True) for name in scripts}
        # Widgets for the overview tab
        self.overview_script_widgets = {} 
        # Dictionary to hold UI widgets for each script tab
        self.script_ui_widgets = {} 
        # NEW: BooleanVar for overview tab switches
        self.overview_switch_vars = {name: tk.BooleanVar(value=False) for name in scripts}


        self.logger.info("Batch Script Manager wird gestartet...")
        if not PLYER_AVAILABLE:
            self.logger.warning("plyer Modul nicht gefunden. Desktop-Benachrichtigungen werden deaktiviert. Installieren mit: pip install plyer")
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil Modul nicht gefunden. CPU-Auslastung wird deaktiviert. Installieren mit: pip install psutil")

        # --- Load Icons ---
        # Icons are 1x1 GIFs, which are guaranteed to work. Replace with better 16x16 GIFs if desired.
        self.icon_play = tk.PhotoImage(data=ICON_PLAY)
        self.icon_stop = tk.PhotoImage(data=ICON_STOP)
        self.icon_reload = tk.PhotoImage(data=ICON_RELOAD)
        self.icon_add = tk.PhotoImage(data=ICON_ADD)
        self.icon_edit = tk.PhotoImage(data=ICON_EDIT)
        self.icon_delete = tk.PhotoImage(data=ICON_DELETE)
        self.icon_folder = tk.PhotoImage(data=ICON_FOLDER)
        self.icon_config = tk.PhotoImage(data=ICON_CONFIG)

        # Determine actual monospace font
        try:
            # Test if Cascadia Code is available (requires a Tkinter window)
            test_font = tk.font.Font(family=self.DEFAULT_MONOSPACE_FONT[0])
            # If no error, Cascadia Code is likely available or Tkinter silently substituted
            self.actual_monospace_font = self.DEFAULT_MONOSPACE_FONT
        except Exception:
            self.actual_monospace_font = self.FALLBACK_MONOSPACE_FONT
        self.logger.info(f"Monospace-Schriftart für Protokolle: {self.actual_monospace_font[0]}")


        # --- Apply a modern theme and custom styles ---
        self.style = ttk.Style(self)
        self.style.theme_use("clam") # Options: "default", "alt", "clam", "vista", "xpnative" (Windows only)

        # General font configuration for all ttk widgets
        self.style.configure('.', font=self.DEFAULT_FONT, background=self.MAIN_BG_COLOR, foreground=self.TEXT_COLOR_DARK)

        # Custom Button Styles (flat design with hover)
        self.style.configure("TButton",
                             font=self.DEFAULT_FONT,
                             padding=(5, 5), # More spacious buttons
                             relief="flat",
                             background=self.ACCENT_COLOR,
                             foreground=self.TEXT_COLOR_LIGHT)
        self.style.map("TButton",
                       background=[('active', "#005999"), ("pressed", "#004d80")],
                       foreground=[('active', self.TEXT_COLOR_LIGHT), ('pressed', self.TEXT_COLOR_LIGHT)],
                       relief=[('pressed', 'sunken'), ('!disabled', 'flat')])
        
        # Spezielle Button-Styles
        self.style.configure("Success.TButton", 
                             font=self.DEFAULT_FONT,
                             padding=(5, 5),
                             relief="flat",
                             background=self.ACCENT_GREEN,
                             foreground=self.TEXT_COLOR_LIGHT)
        self.style.map("Success.TButton",
                       background=[('active', "#1e7e34"), ("pressed", "#155724")],
                       foreground=[('active', self.TEXT_COLOR_LIGHT), ('pressed', self.TEXT_COLOR_LIGHT)],
                       relief=[('pressed', 'sunken'), ('!disabled', 'flat')])
        
        # Sekundäre Buttons
        self.style.configure("Secondary.TButton", 
                             font=self.DEFAULT_FONT,
                             padding=(5, 5),
                             relief="flat",
                             background=self.ACCENT_SECONDARY,
                             foreground=self.TEXT_COLOR_LIGHT)
        self.style.map("Secondary.TButton",
                       background=[('active', "#545b62"), ("pressed", "#495057")],
                       foreground=[('active', self.TEXT_COLOR_LIGHT), ('pressed', self.TEXT_COLOR_LIGHT)],
                       relief=[('pressed', 'sunken'), ('!disabled', 'flat')])
        
        # Danger Button Style (rot für Stop All und einzelne Stop)
        self.style.configure("Danger.TButton", 
                             font=self.DEFAULT_FONT,
                             padding=(5, 5),
                             relief="flat",
                             background="#dc3545",
                             foreground=self.TEXT_COLOR_LIGHT)
        self.style.map("Danger.TButton",
                       background=[('active', "#c82333"), ("pressed", "#bd2130")],
                       foreground=[('active', self.TEXT_COLOR_LIGHT), ('pressed', self.TEXT_COLOR_LIGHT)],
                       relief=[('pressed', 'sunken'), ('!disabled', 'flat')])
        
        # Warning Button Style (orange für Delete)
        self.style.configure("Warning.TButton", 
                             font=self.DEFAULT_FONT,
                             padding=(5, 5),
                             relief="flat",
                             background="#ffc107",
                             foreground=self.TEXT_COLOR_DARK)
        self.style.map("Warning.TButton",
                       background=[('active', "#e0a800"), ("pressed", "#d39e00")],
                       foreground=[('active', self.TEXT_COLOR_DARK), ('pressed', self.TEXT_COLOR_DARK)],
                       relief=[('pressed', 'sunken'), ('!disabled', 'flat')])
        
        # Notebook (Tab) Styles
        self.style.configure("TNotebook", background=self.MAIN_BG_COLOR, borderwidth=0)
        self.style.configure("TNotebook.Tab", 
                             background=self.NOTEBOOK_TAB_BG_INACTIVE, 
                             foreground=self.TEXT_COLOR_DARK,
                             padding=[8, 5],
                             font=self.DEFAULT_FONT)
        self.style.map("TNotebook.Tab",
                       background=[('selected', self.NOTEBOOK_TAB_BG_ACTIVE), ('active', self.BUTTON_BG_HOVER)],
                       foreground=[('selected', self.TEXT_COLOR_DARK), ('active', self.TEXT_COLOR_DARK)])
        
        # Frame styles
        self.style.configure("TFrame", background=self.MAIN_BG_COLOR)

        # NEW STYLE: For script panels in the Overview tab
        self.style.configure("OverviewPanel.TFrame", background=self.NOTEBOOK_TAB_BG_ACTIVE)

        # Label styles for status indicators and overview script names
        # Status.TLabel is for individual script tabs (background MAIN_BG_COLOR)
        self.style.configure("Status.TLabel", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1], 'bold'), 
                             background=self.MAIN_BG_COLOR, foreground=self.TEXT_COLOR_DARK)
        
        # OverviewScript.TLabel is for script names in the overview (background NOTEBOOK_TAB_BG_ACTIVE)
        self.style.configure("OverviewScript.TLabel", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1], 'bold'), 
                             background=self.NOTEBOOK_TAB_BG_ACTIVE, foreground=self.TEXT_COLOR_DARK) 

        # NEW STYLE: For generic info labels (PID, CPU) in overview panels
        self.style.configure("OverviewInfo.TLabel", font=self.DEFAULT_FONT, 
                             background=self.NOTEBOOK_TAB_BG_ACTIVE, foreground=self.TEXT_COLOR_DARK)
        
        # NEW STYLE: For status labels in overview panels
        self.style.configure("OverviewStatus.TLabel", font=self.DEFAULT_FONT, 
                             background=self.NOTEBOOK_TAB_BG_ACTIVE, foreground="red") # Initial 'red' foreground

        # Entry (input fields) styling
        self.style.configure("TEntry", fieldbackground=self.TEXT_COLOR_LIGHT, foreground=self.TEXT_COLOR_DARK, font=self.DEFAULT_FONT)

        # NEW STYLE: For Checkbuttons, ensuring indicator is visible
        self.style.configure("Autostart.TCheckbutton", indicatoron=True, font=self.DEFAULT_FONT)

        self.create_widgets()
        self.after(100, self.process_queue)
        self.after(100, self.process_log_queue)
        if self.autostart_enabled_var.get():
            self.autostart_scripts()
        if PSUTIL_AVAILABLE:
            self.update_cpu_usage()

    def _send_notification(self, title, message):
        if PLYER_AVAILABLE:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name=self.APP_NAME,
                    timeout=5
                )
            except Exception as e:
                self.logger.error(f"Fehler beim Senden der Benachrichtigung: {e}")
        else:
            self.logger.warning("plyer nicht verfügbar, konnte keine Desktop-Benachrichtigung senden.")

    def _setup_logger(self):
        logger = logging.getLogger("BatchManager")
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        queue_handler = logging.handlers.QueueHandler(self.log_queue)
        queue_handler.setFormatter(formatter) # Set formatter on the handler

        logger.addHandler(queue_handler)
        
        return logger, formatter # Return logger and formatter

    def autostart_scripts(self):
        self.logger.info("Prüfe auf automatisch zu startende Skripte...")
        autostart_scripts = [name for name, data in self.scripts.items() if data.get('autostart', False)]
        def _autostart_thread():
            for i, name in enumerate(autostart_scripts):
                self.logger.info(f"Autostart: Starte '{name}' in {self.global_start_delay} Sekunden...")
                self.after(0, lambda n=name: self.start_script(n))
                if i < len(autostart_scripts) - 1 and self.global_start_delay > 0:
                    time.sleep(self.global_start_delay)
        thread = threading.Thread(target=_autostart_thread, daemon=True)
        thread.start()

    def _find_pid_by_port(self, port):
        """Find PID using a port (Windows only). Returns PID or None."""
        try:
            result = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True)
            for line in result.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    pid = int(parts[-1])
                    return pid
        except Exception:
            return None
        return None

    def update_cpu_usage(self):
        total_managed_cpu = 0.0
        for name in list(self.psutil_processes.keys()):
            try:
                process_cache = self.psutil_processes.get(name, {})
                if not process_cache:
                    continue

                main_popen_process = self.processes.get(name)
                if not main_popen_process or main_popen_process.poll() is not None:
                    self.handle_process_exit(name)
                    continue

                root_psutil_proc = process_cache.get(main_popen_process.pid)
                if not root_psutil_proc:
                    continue

                all_current_pids = {child.pid for child in root_psutil_proc.children(recursive=True)}
                all_current_pids.add(root_psutil_proc.pid)

                dead_pids = set(process_cache.keys()) - all_current_pids
                for pid in dead_pids:
                    del process_cache[pid]

                for pid in all_current_pids:
                    if pid not in process_cache:
                        try:
                            new_proc = psutil.Process(pid)
                            new_proc.cpu_percent(interval=None)
                            process_cache[pid] = new_proc
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                
                total_cpu = 0
                for pid, proc in list(process_cache.items()):
                    try:
                        total_cpu += proc.cpu_percent(interval=None)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        del process_cache[pid]

                # Update individual script tab CPU label and sparkline
                if name in self.script_ui_widgets and 'cpu_label' in self.script_ui_widgets[name]:
                    self.script_ui_widgets[name]['cpu_label'].config(text=f"CPU: {total_cpu:.1f}%")
                    self.cpu_history[name].append(total_cpu)
                    self.cpu_history[name] = self.cpu_history[name][-20:]
                    self._draw_sparkline(self.script_ui_widgets[name]['sparkline_canvas'], self.cpu_history[name], 
                                         width=50, height=15, draw_value=False)

                # Update overview tab CPU label and sparkline
                if name in self.overview_script_widgets:
                    overview_widgets = self.overview_script_widgets[name]
                    overview_widgets['cpu_label'].config(text=f"CPU: {total_cpu:.1f}%")
                    self._draw_sparkline(overview_widgets['sparkline_canvas'], self.cpu_history[name], 
                                         width=self.OVERVIEW_SPARKLINE_WIDTH, height=self.OVERVIEW_SPARKLINE_HEIGHT, 
                                         draw_value=True, line_width=2)


                total_managed_cpu += total_cpu

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.handle_process_exit(name)
            except Exception as e:
                self.logger.error(f"Fehler beim Aktualisieren der CPU-Auslastung für {name}: {e}")
        
        if PSUTIL_AVAILABLE and hasattr(self, 'total_cpu_label'):
            self.total_cpu_label.config(text=f"Total CPU: {total_managed_cpu:.1f}%")

        self.after(2000, self.update_cpu_usage)

    def _draw_sparkline(self, canvas, history, width, height, draw_value=False, line_width=1):
        canvas.delete("all")
        
        current_width = canvas.winfo_width()
        current_height = canvas.winfo_height()
        if current_width <= 1 or current_height <= 1:
            current_width = width
            current_height = height
            if current_width <= 1 or current_height <= 1:
                return

        # --- Modernized Sparkline ---
        line_color = self.ACCENT_COLOR
        fill_color = "#cce5ff"  # Lighter shade of accent color
        dot_color = "red"

        max_cpu = max(history) if history else 100
        if max_cpu < 50: max_cpu = 50 # Set a minimum ceiling so small values aren't exaggerated
        
        # Handle cases with not enough data to draw a line
        if len(history) < 2: 
            if history and draw_value:
                last_value = history[-1]
                # Determine text color based on value
                if last_value <= 10: text_color = "green"
                elif last_value <= 70: text_color = "#E69B00" # Orange/yellow
                else: text_color = "red"
                canvas.create_text(current_width / 2, current_height / 2, anchor="center", 
                                   text=f"{last_value:.1f}%", fill=text_color, font=(self.DEFAULT_FONT[0], 9, 'bold'))
            return 

        # Calculate points for the line graph
        points = []
        for i, val in enumerate(history):
            x = (i / (len(history) - 1)) * current_width if len(history) > 1 else current_width / 2
            y = current_height - (val / max_cpu) * (current_height - 2) # Leave 1px margin
            y = max(1, min(current_height - 1, y)) # Clamp within margin
            points.extend([x, y])
        
        if points:
            # 1. Draw the filled area (polygon) under the line
            polygon_points = list(points)
            polygon_points.extend([current_width, current_height, 0, current_height])
            canvas.create_polygon(polygon_points, fill=fill_color, outline="")

            # 2. Draw the smoothed line over the polygon
            canvas.create_line(points, fill=line_color, width=line_width, smooth=True)
            
            # 3. Draw a marker dot for the most recent value
            canvas.create_oval(points[-2]-3, points[-1]-3, points[-2]+3, points[-1]+3, fill=dot_color, outline="")
        
        if draw_value and history:
            last_value = history[-1]
            
            # Determine text color based on CPU value
            if last_value <= 10:
                text_color = "green"
            elif last_value <= 70:
                text_color = "#E69B00" # Orange/yellow
            else:
                text_color = "red"
            
            # 4. Draw the percentage text with dynamic color
            canvas.create_text(current_width - 5, 5, anchor="ne", 
                               text=f"{last_value:.1f}%", fill=text_color, font=(self.DEFAULT_FONT[0], 9, 'bold'))

    def create_widgets(self):
        # Clear existing widgets if reloading
        for widget in self.winfo_children():
            widget.destroy()

        # --- Menu Bar ---
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="Konfiguration öffnen", command=self.open_config)
        file_menu.add_command(label="Skripte neu laden", command=self.reload_scripts_from_config)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.on_closing)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        help_menu.add_command(label="Über", command=self._show_about_dialog)

        # --- Header/Logo ---
        header_frame = ttk.Frame(self, padding="10", relief="raised", borderwidth=1)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        logo_label = ttk.Label(header_frame, text="🔄 Firat´s Batch Script Manager", 
                              font=("Segoe UI", 16, "bold"), foreground=self.ACCENT_COLOR, 
                              background=self.MAIN_BG_COLOR)
        logo_label.pack(anchor="center")

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)

        # Container for global controls at the top of main_frame
        top_controls_container_frame = ttk.Frame(main_frame, padding=(0, 0))
        top_controls_container_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        main_frame.grid_rowconfigure(0, weight=0)

        # Global controls (Start All, Stop All, Delay Setting, Global CPU)
        global_buttons_frame = ttk.Frame(top_controls_container_frame, padding="10")
        global_buttons_frame.pack(side=tk.LEFT, padx=(0,10))
        
        start_all_button = ttk.Button(global_buttons_frame, text=" Start All", image=self.icon_play, compound=tk.LEFT, style="Success.TButton", command=self.start_all)
        start_all_button.pack(side=tk.LEFT, padx=5)
        Tooltip(start_all_button, "Alle Skripte nacheinander starten")

        stop_all_button = ttk.Button(global_buttons_frame, text=" Stop All", image=self.icon_stop, compound=tk.LEFT, style="Danger.TButton", command=self.stop_all)
        stop_all_button.pack(side=tk.LEFT, padx=5)
        Tooltip(stop_all_button, "Alle laufenden Skripte stoppen")

        ttk.Label(global_buttons_frame, text="Start Delay (s):").pack(side=tk.LEFT, padx=(15,5))
        self.delay_entry = ttk.Entry(global_buttons_frame, width=5, font=self.DEFAULT_FONT)
        self.delay_entry.insert(0, str(self.global_start_delay))
        self.delay_entry.pack(side=tk.LEFT)
        Tooltip(self.delay_entry, "Verzögerung in Sekunden zwischen dem Start von Skripten (bei 'Start All')")
        self.delay_entry.bind("<Return>", lambda event: self._update_global_delay_from_entry())
        self.delay_entry.bind("<FocusOut>", lambda event: self._update_global_delay_from_entry()) # Save on focus lost

        autostart_check = ttk.Checkbutton(global_buttons_frame, text="Enable Autostart", variable=self.autostart_enabled_var, command=self._on_autostart_toggle)
        autostart_check.pack(side=tk.LEFT, padx=(15, 5))
        Tooltip(autostart_check, "Wenn aktiviert, werden alle Skripte, die als 'autostart' markiert sind, beim Start des Managers ausgeführt.")

        if PSUTIL_AVAILABLE:
            self.total_cpu_label = ttk.Label(global_buttons_frame, text="Total CPU: 0.0%", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1], 'bold'))
            self.total_cpu_label.pack(side=tk.LEFT, padx=(20, 5))
            Tooltip(self.total_cpu_label, "Gesamte CPU-Auslastung aller vom Manager gestarteten Prozesse")

        # Config controls (Add Script)
        config_buttons_frame = ttk.Frame(top_controls_container_frame, padding="10")
        config_buttons_frame.pack(side=tk.RIGHT, padx=(10,0))

        add_script_button = ttk.Button(config_buttons_frame, text=" Add Script", image=self.icon_add, compound=tk.LEFT, style="TButton", command=self.add_script_dialog)
        add_script_button.pack(side=tk.LEFT, padx=5)
        Tooltip(add_script_button, "Fügt ein neues Batch-Skript zur Verwaltung hinzu")


        # Notebook for scripts and manager log
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        main_frame.grid_rowconfigure(1, weight=1)

        # Create "Overview" tab (this now includes Manager Log)
        self._create_overview_tab()

        # Script-specific frames (each in its own tab)
        for i, (name, data) in enumerate(self.scripts.items()):
            script_tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(script_tab, text=name)

            # Initialize a dictionary for this script's UI widgets
            self.script_ui_widgets[name] = {}

            # --- Top control part for each script --- 
            top_script_frame = ttk.Frame(script_tab)
            top_script_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 5))

            # Labels (path, status, PID, CPU) on the left
            script_labels_frame = ttk.Frame(top_script_frame)
            script_labels_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            path_label = ttk.Label(script_labels_frame, text=os.path.basename(data['path']), font=self.DEFAULT_FONT)
            path_label.pack(side=tk.LEFT, anchor='w')
            Tooltip(path_label, data['path'])
            
            # Status Indicator (LED-like)
            status_indicator = tk.Canvas(script_labels_frame, width=10, height=10, bg="red", highlightthickness=0)
            status_indicator.pack(side=tk.LEFT, padx=(5,0), anchor='w')
            self.script_ui_widgets[name]['status_indicator'] = status_indicator # Store indicator for updates

            status_label = ttk.Label(script_labels_frame, text="Status: Gestoppt", foreground="red", style="Status.TLabel")
            status_label.pack(side=tk.LEFT, padx=(2,10), anchor='w')
            self.script_ui_widgets[name]['status_label'] = status_label
            
            if PSUTIL_AVAILABLE:
                pid_label = ttk.Label(script_labels_frame, text="", font=self.DEFAULT_FONT)
                pid_label.pack(side=tk.LEFT, padx=5, anchor='w')
                self.script_ui_widgets[name]['pid_label'] = pid_label
                
                cpu_label = ttk.Label(script_labels_frame, text="", font=self.DEFAULT_FONT)
                cpu_label.pack(side=tk.LEFT, padx=5, anchor='w')
                self.script_ui_widgets[name]['cpu_label'] = cpu_label

                # Sparkline for CPU usage on individual tab (smaller)
                sparkline_canvas = tk.Canvas(script_labels_frame, width=50, height=15, bg=self.SPARKLINE_BG_COLOR, highlightthickness=1, highlightbackground="lightgray")
                sparkline_canvas.pack(side=tk.LEFT, padx=5, anchor='w')
                self.script_ui_widgets[name]['sparkline_canvas'] = sparkline_canvas
                Tooltip(sparkline_canvas, "CPU-Auslastungsverlauf (letzte 20 Messungen)")


            # Buttons (Start, Stop, Restart, Edit, Delete) on the right
            script_buttons_frame = ttk.Frame(top_script_frame)
            script_buttons_frame.pack(side=tk.RIGHT)

            start_button = ttk.Button(script_buttons_frame, text=" Start", image=self.icon_play, compound=tk.LEFT, style="Success.TButton", command=lambda n=name: self.start_script(n))
            start_button.pack(side=tk.LEFT, padx=2)
            self.script_ui_widgets[name]['start_button'] = start_button
            Tooltip(start_button, f"Starte '{name}'")

            stop_button = ttk.Button(script_buttons_frame, text=" Stop", image=self.icon_stop, compound=tk.LEFT, style="Danger.TButton", command=lambda n=name: self.stop_script(n), state=tk.DISABLED)
            stop_button.pack(side=tk.LEFT, padx=2)
            self.script_ui_widgets[name]['stop_button'] = stop_button
            Tooltip(stop_button, f"Stoppe '{name}'")
            
            restart_button = ttk.Button(script_buttons_frame, text=" Restart", image=self.icon_reload, compound=tk.LEFT, style="TButton", command=lambda n=name: self.restart_script(n), state=tk.DISABLED)
            restart_button.pack(side=tk.LEFT, padx=2)
            self.script_ui_widgets[name]['restart_button'] = restart_button
            Tooltip(restart_button, f"Starte '{name}' neu")

            edit_button = ttk.Button(script_buttons_frame, text=" Edit", image=self.icon_edit, compound=tk.LEFT, style="Secondary.TButton", command=lambda n=name: self.edit_script_dialog(n))
            edit_button.pack(side=tk.LEFT, padx=2)
            Tooltip(edit_button, f"Bearbeite die Details von '{name}'")

            delete_button = ttk.Button(script_buttons_frame, text=" Delete", image=self.icon_delete, compound=tk.LEFT, style="Warning.TButton", command=lambda n=name: self.delete_script(n))
            delete_button.pack(side=tk.LEFT, padx=2)
            Tooltip(delete_button, f"Lösche '{name}' dauerhaft")
            
            # Search/Filter and highlighting controls
            search_frame = ttk.Frame(script_tab, padding=(0,5))
            search_frame.pack(fill=tk.X, side=tk.TOP)

            ttk.Label(search_frame, text="Search/Filter:").pack(side=tk.LEFT, padx=(0,5))
            search_entry = ttk.Entry(search_frame, font=self.DEFAULT_FONT)
            search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            search_entry.bind("<Return>", lambda event, n=name: self.apply_filter_and_highlight(n))
            self.script_ui_widgets[name]['search_entry'] = search_entry

            search_button = ttk.Button(search_frame, text="Apply", command=lambda n=name: self.apply_filter_and_highlight(n))
            search_button.pack(side=tk.LEFT, padx=5)
            
            clear_search_button = ttk.Button(search_frame, text="Clear Filter", command=lambda n=name: self.clear_filter(n))
            clear_search_button.pack(side=tk.LEFT)

            # Auto-scroll checkbox
            autoscroll_checkbox = ttk.Checkbutton(search_frame, text="Auto-scroll", variable=self.autoscroll_vars[name])
            autoscroll_checkbox.pack(side=tk.RIGHT, padx=10)
            Tooltip(autoscroll_checkbox, "Automatische Bildlaufleiste am Ende der Ausgabe ein-/ausschalten")


            # Output text area
            output_frame = ttk.Frame(script_tab)
            output_frame.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM, pady=(5,0))
            
            output_area = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=10, 
                                                    bg=self.LOG_BG_COLOR, fg=self.LOG_FG_COLOR, 
                                                    font=self.actual_monospace_font, insertbackground=self.LOG_FG_COLOR)
            output_area.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            output_area.configure(state='disabled')
            self.script_ui_widgets[name]['output_widget'] = output_area

            # Configure tags for highlighting
            output_area.tag_config('error', foreground='red', font=(self.actual_monospace_font[0], self.actual_monospace_font[1], 'bold'))
            output_area.tag_config('warning', foreground='orange')
            output_area.tag_config('success', foreground='green') # Adjusted for light background
            output_area.tag_config('info', foreground='blue')
            output_area.tag_config('filter_match', background='#404000', foreground='white')
            
            # Output controls (Clear, Copy)
            output_control_frame = ttk.Frame(output_frame, padding=(5, 0))
            output_control_frame.pack(side=tk.RIGHT, fill=tk.Y)

            clear_button = ttk.Button(output_control_frame, text="Clear", command=lambda n=name: self.clear_output(n))
            clear_button.pack(pady=2, anchor='n')
            Tooltip(clear_button, "Dieses Ausgabefenster leeren")

            copy_button = ttk.Button(output_control_frame, text="Copy", command=lambda n=name: self.copy_output(n))
            copy_button.pack(pady=2, anchor='n')
            Tooltip(copy_button, "Gesamten Text aus diesem Ausgabefenster kopieren")

        # Removed the duplicate "Manager Log" tab from here.
        # It is now integrated into the "_create_overview_tab" method.

    def _create_overview_tab(self):
        overview_tab = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(overview_tab, text="Overview")

        # Use a PanedWindow to create two resizable columns
        paned_window = ttk.PanedWindow(overview_tab, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # --- Left Pane: Script Controls ---
        left_pane = ttk.Frame(paned_window, padding="5")
        paned_window.add(left_pane, weight=1)

        # --- Right Pane: Outputs ---
        right_pane = ttk.Frame(paned_window, padding="5")
        paned_window.add(right_pane, weight=2) # Give more space to outputs

        # --- Populate Left Pane (Script Overview) ---
        left_header = ttk.Label(left_pane, text="Script Overview", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1]+2, 'bold'), background=self.MAIN_BG_COLOR)
        left_header.pack(pady=(0, 10), anchor='w')

        # Scrollable frame for the script list
        left_canvas = tk.Canvas(left_pane, borderwidth=0, background=self.MAIN_BG_COLOR, highlightthickness=0)
        left_vsb = ttk.Scrollbar(left_pane, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_vsb.set)
        
        left_vsb.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)

        script_list_container = ttk.Frame(left_canvas, padding=(0,0))
        left_canvas_window_id = left_canvas.create_window((0, 0), window=script_list_container, anchor="nw")

        def _on_left_inner_frame_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        def _on_left_canvas_resize(event):
            left_canvas.itemconfig(left_canvas_window_id, width=event.width)

        script_list_container.bind("<Configure>", _on_left_inner_frame_configure)
        left_canvas.bind('<Configure>', _on_left_canvas_resize)

        self.overview_script_widgets = {} # Clear previous widgets

        for name, data in self.scripts.items():
            script_panel = ttk.Frame(script_list_container, relief="solid", borderwidth=1, padding=(10,5), style="OverviewPanel.TFrame") 
            script_panel.pack(fill=tk.X, pady=2, expand=True) 
            
            script_panel.grid_columnconfigure(0, weight=1)
            script_panel.grid_columnconfigure(1, weight=0)
            script_panel.grid_columnconfigure(2, weight=0)
            script_panel.grid_rowconfigure(0, weight=1)

            # Frame to hold script name, status, PID, CPU
            text_labels_subframe = ttk.Frame(script_panel, style="OverviewPanel.TFrame") 
            text_labels_subframe.grid(row=0, column=0, sticky="ew")
            text_labels_subframe.grid_columnconfigure(0, weight=1) # Name label takes space

            # Row 0: Name and Status
            name_label = ttk.Label(text_labels_subframe, text=name, style="OverviewScript.TLabel") 
            name_label.grid(row=0, column=0, sticky='w', padx=(0,10))

            status_indicator = tk.Canvas(text_labels_subframe, width=10, height=10, bg="red", highlightthickness=0)
            status_indicator.grid(row=0, column=1, padx=(5,0), sticky='w')
            
            status_label = ttk.Label(text_labels_subframe, text="Gestoppt", style="OverviewStatus.TLabel") 
            status_label.grid(row=0, column=2, padx=(2,10), sticky='w')

            # Row 1: PID and CPU
            info_labels_frame = ttk.Frame(text_labels_subframe, style="OverviewPanel.TFrame")
            info_labels_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5,0))
            
            pid_label = ttk.Label(info_labels_frame, text="", style="OverviewInfo.TLabel") 
            pid_label.pack(side=tk.LEFT, padx=(0,10), anchor='w')

            cpu_label = ttk.Label(info_labels_frame, text="", style="OverviewInfo.TLabel") 
            cpu_label.pack(side=tk.LEFT, padx=5, anchor='w')

            # --- Controls Subframe (Switch, Restart) ---
            controls_subframe = ttk.Frame(script_panel, style="OverviewPanel.TFrame")
            controls_subframe.grid(row=0, column=1, sticky="e")

            restart_button = ttk.Button(controls_subframe, text=" Restart", image=self.icon_reload, compound=tk.LEFT, style="TButton", command=lambda n=name: self.restart_script(n))
            restart_button.pack(side=tk.TOP, pady=2)
            Tooltip(restart_button, f"'{name}' neu starten")

            toggle_switch = Switch(controls_subframe, variable=self.overview_switch_vars[name], command=lambda n=name: self.toggle_script_from_overview(n))
            toggle_switch.pack(side=tk.TOP, pady=2)


            sparkline_canvas = tk.Canvas(script_panel, width=self.OVERVIEW_SPARKLINE_WIDTH, height=self.OVERVIEW_SPARKLINE_HEIGHT, 
                                        bg=self.SPARKLINE_BG_COLOR, highlightthickness=1, highlightbackground="lightgray")
            sparkline_canvas.grid(row=0, column=2, sticky="e", padx=5, pady=2)
            Tooltip(sparkline_canvas, "CPU-Auslastungsverlauf (letzte 20 Messungen)")

            self.overview_script_widgets[name] = {
                'script_panel': script_panel, 'status_indicator': status_indicator, 'status_label': status_label,
                'pid_label': pid_label, 'cpu_label': cpu_label, 'sparkline_canvas': sparkline_canvas, 'toggle_switch': toggle_switch
            }

        # --- Populate Right Pane (Outputs) ---
        right_header = ttk.Label(right_pane, text="Live Outputs", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1]+2, 'bold'), background=self.MAIN_BG_COLOR)
        right_header.pack(pady=(0, 10), anchor='w')

        right_canvas = tk.Canvas(right_pane, borderwidth=0, background=self.MAIN_BG_COLOR, highlightthickness=0)
        right_vsb = ttk.Scrollbar(right_pane, orient="vertical", command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_vsb.set)
        right_vsb.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        
        outputs_container = ttk.Frame(right_canvas)
        right_canvas_window_id = right_canvas.create_window((0, 0), window=outputs_container, anchor="nw")

        def _on_right_inner_frame_configure(event):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        def _on_right_canvas_resize(event):
            right_canvas.itemconfig(right_canvas_window_id, width=event.width)

        outputs_container.bind("<Configure>", _on_right_inner_frame_configure)
        right_canvas.bind('<Configure>', _on_right_canvas_resize)
        
        # Create output widgets for each script
        for name in self.scripts:
            output_panel_frame = ttk.Frame(outputs_container, padding=(0, 5))
            output_panel_frame.pack(fill=tk.X, expand=True)
            
            label = ttk.Label(output_panel_frame, text=name, font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1], 'bold'))
            label.pack(anchor='w')
            
            output_area = scrolledtext.ScrolledText(output_panel_frame, wrap=tk.WORD, height=8,
                                                    bg=self.LOG_BG_COLOR, fg=self.LOG_FG_COLOR, 
                                                    font=self.actual_monospace_font, insertbackground=self.LOG_FG_COLOR)
            output_area.pack(fill=tk.BOTH, expand=True, pady=(2, 10))
            output_area.configure(state='disabled')
            
            self.overview_script_widgets[name]['overview_output_widget'] = output_area

        # Add Manager Log at the bottom
        log_header = ttk.Label(outputs_container, text="Manager Log", font=(self.DEFAULT_FONT[0], self.DEFAULT_FONT[1]+2, 'bold'), background=self.MAIN_BG_COLOR)
        log_header.pack(pady=(15, 5), anchor='w')

        self.manager_log_text = scrolledtext.ScrolledText(outputs_container, wrap=tk.WORD, 
                                                        bg=self.LOG_BG_COLOR, fg=self.LOG_FG_COLOR, 
                                                        font=self.actual_monospace_font, insertbackground=self.LOG_FG_COLOR, height=10)
        self.manager_log_text.pack(fill=tk.BOTH, expand=True)
        self.manager_log_text.configure(state='disabled')



    def _on_autostart_toggle(self):
        self.logger.info(f"Autostart-Einstellung auf {self.autostart_enabled_var.get()} geändert.")
        self._save_config_to_file()

    def _update_global_delay_from_entry(self):
        try:
            new_delay = int(self.delay_entry.get())
            if new_delay >= 0:
                self.global_start_delay = new_delay
                self.logger.info(f"Globale Startverzögerung auf {self.global_start_delay} Sekunden aktualisiert.")
                self._save_config_to_file() # Save change to config.json
            else:
                self.logger.warning("Startverzögerung muss eine positive Zahl sein. Wert nicht geändert.")
                self.delay_entry.delete(0, tk.END)
                self.delay_entry.insert(0, str(self.global_start_delay))
        except ValueError:
            self.logger.error("Ungültiger Wert für Startverzögerung. Bitte geben Sie eine ganze Zahl ein.")
            self.delay_entry.delete(0, tk.END)
            self.delay_entry.insert(0, str(self.global_start_delay))

    def process_log_queue(self):
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get_nowait()
                msg = self.log_formatter.format(record) # Use the stored formatter
                
                self.manager_log_text.configure(state='normal')
                self.manager_log_text.insert(tk.END, msg + '\n')
                self.manager_log_text.see(tk.END)
                self.manager_log_text.configure(state='disabled')
            except queue.Empty:
                pass
        self.after(100, self.process_log_queue)

    def start_script(self, name):
        if self.processes.get(name) and self.processes[name].poll() is None:
            self.logger.info(f"'{name}' läuft bereits.")
            return

        path = self.scripts[name]['path']
        script_dir = os.path.dirname(path)
        output_widget = self.script_ui_widgets[name]['output_widget']
        output_widget.configure(state='normal')
        output_widget.delete('1.0', tk.END)
        output_widget.configure(state='disabled')
        self.script_raw_output[name].clear()
        self.cpu_history[name] = [0.0] * 20 # Reset CPU history

        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                ['cmd', '/c', path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                shell=False,
                startupinfo=si,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                cwd=script_dir
            )
            self.processes[name] = process
            self.update_status(name, "Läuft", "green", process.pid)
            self.toggle_buttons(name, is_running=True)
            self.logger.info(f"'{name}' gestartet. PID: {process.pid}")
            self._send_notification(f"Skript gestartet: {name}", f"'{name}' wurde erfolgreich gestartet. (PID: {process.pid})")

            if PSUTIL_AVAILABLE:
                try:
                    p = psutil.Process(process.pid)
                    p.cpu_percent(interval=None)
                    self.psutil_processes[name] = {process.pid: p}
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    self.logger.warning(f"Konnte psutil für PID {process.pid} nicht initialisieren: {e}")

            thread = threading.Thread(target=self.enqueue_output, args=(process.stdout, name), daemon=True)
            self.threads[name] = thread
            thread.start()

        except Exception as e:
            self.update_status(name, f"Fehler: {e}", "red")
            self.logger.error(f"Fehler beim Starten von '{name}': {e}")
            self._send_notification(f"Fehler beim Starten: {name}", f"'{name}' konnte nicht gestartet werden: {e}")

    def enqueue_output(self, pipe, name):
        try:
            buffer = ''
            while True:
                char = pipe.read(1)
                if not char:
                    if buffer:
                        self.output_queue.put((name, buffer))
                    break
                buffer += char
                if char == '\n':
                    self.output_queue.put((name, buffer))
                    buffer = ''
            pipe.close()
        except Exception as e:
            self.logger.error(f"Ausnahme im Output-Reader für {name}: {e}")
        
        self.after(0, self.handle_process_exit, name)

    def handle_process_exit(self, name):
        self.update_status(name, "Gestoppt", "red")
        self.toggle_buttons(name, is_running=False)
        if name in self.processes:
            pid = self.processes[name].pid
            self.processes.pop(name)
            self.logger.info(f"'{name}' beendet. PID: {pid}")
            self._send_notification(f"Skript beendet: {name}", f"'{name}' (PID: {pid}) wurde beendet.")
        
        if PSUTIL_AVAILABLE and name in self.psutil_processes:
            self.psutil_processes.pop(name)
            if name in self.script_ui_widgets and 'cpu_label' in self.script_ui_widgets[name]:
                self.script_ui_widgets[name]['cpu_label'].config(text="")
            if name in self.script_ui_widgets and 'sparkline_canvas' in self.script_ui_widgets[name]: # Clear individual tab sparkline
                self.script_ui_widgets[name]['sparkline_canvas'].delete("all")
            if name in self.overview_script_widgets: # Clear overview sparkline
                self.overview_script_widgets[name]['cpu_label'].config(text="")
                self.overview_script_widgets[name]['sparkline_canvas'].delete("all")
            self.cpu_history[name] = [0.0] * 20 # Reset CPU history

    def process_queue(self):
        while not self.output_queue.empty():
            try:
                name, line = self.output_queue.get_nowait()
                if name in self.scripts:
                    self.script_raw_output[name].append(line)
                    
                    widget = self.script_ui_widgets[name]['output_widget']
                    search_term = self.script_ui_widgets[name]['search_entry'].get().strip()
                    
                    if not search_term or search_term.lower() in line.lower():
                        widget.configure(state='normal')
                        start_index = widget.index(tk.END)
                        widget.insert(tk.END, line)
                        end_index = widget.index(tk.END + "-1c")
                        
                        self._apply_keyword_highlighting(widget, start_index, end_index, line)
                        
                        if search_term:
                            self._apply_search_highlighting(widget, start_index, end_index, line, search_term)
                        
                        if self.autoscroll_vars[name].get(): # Check autoscroll setting
                            widget.see(tk.END)
                        widget.configure(state='disabled')

                    # Also update the new overview output widget (always unfiltered)
                    if name in self.overview_script_widgets and 'overview_output_widget' in self.overview_script_widgets[name]:
                        overview_widget = self.overview_script_widgets[name]['overview_output_widget']
                        overview_widget.configure(state='normal')
                        overview_widget.insert(tk.END, line)
                        overview_widget.see(tk.END) # Always autoscroll overview outputs
                        overview_widget.configure(state='disabled')
            except queue.Empty:
                pass
        self.after(100, self.process_queue)

    def _apply_keyword_highlighting(self, widget, start_index, end_index, line):
        keywords = {
            'error': ['error', 'exception', 'failed', 'fatal'],
            'warning': ['warn', 'warning'],
            'success': ['success', 'completed', 'finished'],
            'info': ['info', 'starting', 'running']
        }
        
        for tag, words in keywords.items():
            for word in words:
                start_pos = 0
                while True:
                    start_pos = line.lower().find(word.lower(), start_pos)
                    if start_pos == -1:
                        break
                    tag_start_char_idx = int(start_index.split('.')[1]) + start_pos
                    tag_end_char_idx = int(start_index.split('.')[1]) + start_pos + len(word)
                    
                    tag_start = f"{start_index.split('.')[0]}.{tag_start_char_idx}"
                    tag_end = f"{start_index.split('.')[0]}.{tag_end_char_idx}"
                    widget.tag_add(tag, tag_start, tag_end)
                    start_pos += len(word)

    def _apply_search_highlighting(self, widget, start_index, end_index, line, search_term):
        if search_term:
            start_pos = 0
            while True:
                start_pos = line.lower().find(search_term.lower(), start_pos)
                if start_pos == -1:
                    break
                tag_start_char_idx = int(start_index.split('.')[1]) + start_pos
                tag_end_char_idx = int(start_index.split('.')[1]) + start_pos + len(search_term)
                
                tag_start = f"{start_index.split('.')[0]}.{tag_start_char_idx}"
                tag_end = f"{start_index.split('.')[0]}.{tag_end_char_idx}"
                widget.tag_add('filter_match', tag_start, tag_end)
                start_pos += len(search_term)

    def apply_filter_and_highlight(self, name):
        widget = self.script_ui_widgets[name]['output_widget']
        search_term = self.script_ui_widgets[name]['search_entry'].get().strip().lower()
        
        widget.configure(state='normal')
        widget.delete('1.0', tk.END)
        
        for line in self.script_raw_output[name]:
            if not search_term or search_term in line.lower():
                start_index = widget.index(tk.END)
                widget.insert(tk.END, line)
                end_index = widget.index(tk.END + "-1c")
                
                self._apply_keyword_highlighting(widget, start_index, end_index, line)
                
                if search_term:
                    self._apply_search_highlighting(widget, start_index, end_index, line, search_term)
        
        widget.see(tk.END)
        widget.configure(state='disabled')
        self.logger.info(f"Filter/Highlighting für '{name}' mit Suchbegriff '{search_term}' angewendet.")

    def clear_filter(self, name):
        self.script_ui_widgets[name]['search_entry'].delete(0, tk.END)
        self.apply_filter_and_highlight(name)
        self.logger.info(f"Filter für '{name}' gelöscht.")

    def _execute_taskkill(self, pid, name):
        """Runs taskkill in a separate thread to avoid UI freeze. Tries to kill by PID, and if ein Port in config steht, sucht erst PID über Port."""
        def _kill():
            try:
                port = self.scripts.get(name, {}).get('port')
                target_pid = pid
                if port:
                    found_pid = self._find_pid_by_port(port)
                    if found_pid:
                        target_pid = found_pid
                        self.logger.info(f"Finde PID {target_pid} für Port {port} (Skript: {name})")
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    f"taskkill /F /T /PID {target_pid}", 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    startupinfo=si
                )
                self.logger.info(f"Prozess PID {target_pid} für '{name}' beendet.")
                self._send_notification(f"Skript gestoppt: {name}", f"Prozess PID {target_pid} für '{name}' wurde beendet.")
            except subprocess.CalledProcessError:
                self.logger.info(f"Konnte Prozess PID {pid} für '{name}' nicht beenden (möglicherweise bereits beendet).")
                self._send_notification(f"Skript Stopp-Info: {name}", f"Konnte Prozess PID {pid} für '{name}' nicht beenden (möglicherweise bereits beendet).")
            except Exception as e:
                self.logger.error(f"Fehler beim Beenden von '{name}': {e}")
                self._send_notification(f"Fehler beim Stoppen: {name}", f"Fehler beim Beenden von PID {pid} für '{name}': {e}")
        thread = threading.Thread(target=_kill, daemon=True)
        thread.start()

    def stop_script(self, name):
        if name in self.processes:
            process = self.processes[name]
            if process.poll() is None:
                # Port aus config holen, falls vorhanden
                port = self.scripts.get(name, {}).get('port')
                if port:
                    found_pid = self._find_pid_by_port(port)
                    if found_pid:
                        self.logger.info(f"Stoppe '{name}' über Port {port} (PID: {found_pid})")
                        kill_thread = threading.Thread(target=self._execute_taskkill, args=(found_pid, name), daemon=True)
                        kill_thread.start()
                        return
                self.logger.info(f"Stoppe '{name}' (PID: {process.pid})...")
                self._send_notification(f"Skript stoppt: {name}", f"Sende Stopp-Befehl an '{name}' (PID: {process.pid})...")
                kill_thread = threading.Thread(target=self._execute_taskkill, args=(process.pid, name), daemon=True)
                kill_thread.start()
            else:
                self.handle_process_exit(name)

    def restart_script(self, name):
        self.logger.info(f"Neustart von '{name}'...")
        self._send_notification(f"Skript startet neu: {name}", f"'{name}' wird neu gestartet.")
        self.stop_script(name)
        # Warte immer 3 Sekunden nach dem Stoppen, bevor neu gestartet wird
        self.after(3000, lambda: self.start_script(name))

    def toggle_script_from_overview(self, name):
        """Starts or stops a script based on the overview toggle switch."""
        if self.overview_switch_vars[name].get():
            self.start_script(name)
        else:
            self.stop_script(name)

    def start_all(self):
        self.logger.info("Starte alle Skripte...")
        
        # Starte Skripte mit Verzögerung in einem separaten Thread
        def _start_all_threaded():
            for name in self.scripts:
                self.start_script(name)
                # Pause between starting scripts
                if self.global_start_delay > 0:
                    self.logger.info(f"Warte {self.global_start_delay} Sekunden vor dem Start des nächsten Skripts...")
                    time.sleep(self.global_start_delay)
            self.logger.info("Alle Skripte im 'Start All'-Prozess wurden zum Starten gesendet.")
        
        # Starte die Thread-Funktion
        thread = threading.Thread(target=_start_all_threaded, daemon=True)
        thread.start()

    def stop_all(self):
        self.logger.info("Stoppe alle Skripte...")
        for name in list(self.processes.keys()):
            self.stop_script(name)

    def update_status(self, name, text, color, pid=None):
        # Update status for individual script tab
        if name in self.script_ui_widgets and 'status_label' in self.script_ui_widgets[name]:
            self.script_ui_widgets[name]['status_label'].config(text=f"Status: {text}", foreground=color)
            indicator_color = "green" if text == "Läuft" else "red"
            if "Fehler" in text: indicator_color = "darkred"
            self.script_ui_widgets[name]['status_indicator'].config(bg=indicator_color)
            self.script_ui_widgets[name]['status_indicator'].delete("all")
            self.script_ui_widgets[name]['status_indicator'].create_oval(2,2,8,8, fill=indicator_color, outline=indicator_color)
            if PSUTIL_AVAILABLE and 'pid_label' in self.script_ui_widgets[name]:
                pid_text = f"PID: {pid}" if pid else ""
                self.script_ui_widgets[name]['pid_label'].config(text=pid_text)
        
        # Update status for overview tab
        if name in self.overview_script_widgets:
            overview_widgets = self.overview_script_widgets[name]
            overview_widgets['status_label'].config(text=text, foreground=color) # Foreground can still be changed dynamically
            indicator_color = "green" if text == "Läuft" else "red"
            if "Fehler" in text: indicator_color = "darkred"
            overview_widgets['status_indicator'].config(bg=indicator_color)
            overview_widgets['status_indicator'].delete("all")
            overview_widgets['status_indicator'].create_oval(2,2,8,8, fill=indicator_color, outline=indicator_color)
            if PSUTIL_AVAILABLE:
                pid_text = f"PID: {pid}" if pid else ""
                overview_widgets['pid_label'].config(text=pid_text)

        # NEW: Update overview switch state
        is_running = (text == "Läuft")
        if name in self.overview_switch_vars:
            self.overview_switch_vars[name].set(is_running)


    def toggle_buttons(self, name, is_running):
        state_if_running = tk.DISABLED if is_running else tk.NORMAL
        state_if_stopped = tk.NORMAL if is_running else tk.DISABLED

        self.script_ui_widgets[name]['start_button'].config(state=state_if_running)
        self.script_ui_widgets[name]['stop_button'].config(state=state_if_stopped)
        self.script_ui_widgets[name]['restart_button'].config(state=state_if_stopped)

        # Edit/Delete buttons are always enabled unless explicitly disabled (e.g., during reload)
        if 'edit_button' in self.script_ui_widgets[name]:
            self.script_ui_widgets[name]['edit_button'].config(state=tk.NORMAL)
        if 'delete_button' in self.script_ui_widgets[name]:
            self.script_ui_widgets[name]['delete_button'].config(state=tk.NORMAL)


    def clear_output(self, name):
        # Clear individual tab widget
        widget = self.script_ui_widgets[name]['output_widget']
        widget.configure(state='normal')
        widget.delete('1.0', tk.END)
        widget.configure(state='disabled')

        # Also clear the overview tab widget
        if name in self.overview_script_widgets and 'overview_output_widget' in self.overview_script_widgets[name]:
            overview_widget = self.overview_script_widgets[name]['overview_output_widget']
            overview_widget.configure(state='normal')
            overview_widget.delete('1.0', tk.END)
            overview_widget.configure(state='disabled')
            
        self.script_raw_output[name].clear()
        self.logger.info(f"Ausgabefenster für '{name}' geleert.")

    def copy_output(self, name):
        widget = self.script_ui_widgets[name]['output_widget']
        self.clipboard_clear()
        self.clipboard_append(widget.get('1.0', tk.END))
        self.logger.info(f"Ausgabe von '{name}' in die Zwischenablage kopiert.")

    def open_config(self):
        if os.path.exists(self.full_config_path):
            self.logger.info(f"Öffne Konfigurationsdatei: {self.full_config_path}")
            os.startfile(self.full_config_path)
        else:
            self.logger.error(f"Die Konfigurationsdatei wurde nicht gefunden: {self.full_config_path}")
            messagebox.showerror("Fehler", f"Konfigurationsdatei nicht gefunden: {self.full_config_path}")

    @staticmethod
    def _initial_config_load(path):
        """
        Static method to load script configurations and global delay from config.json.
        Creates an example config if none exists.
        """
        scripts = {}
        global_delay = 2 # Default value if not found
        autostart_enabled = True # Default to True to maintain old behavior
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    scripts = config_data.get('scripts', {})
                    global_delay = config_data.get('global_start_delay_seconds', 2)
                    autostart_enabled = config_data.get('autostart_enabled', True)
                logging.getLogger("BatchManager").info(f"Konfigurationsdatei '{path}' erfolgreich geladen.")
            else:
                logging.getLogger("BatchManager").warning(f"Konfigurationsdatei '{path}' nicht gefunden. Erstelle eine Beispielkonfiguration.")
                scripts = {
                    "KI Web Server": { "path": r"c:\project_ki_web\start_app_final.bat", "autostart": True },
                    "Chat Server": { "path": r"C:\Users\firat\OneDrive\Desktop\start_chat.bat", "autostart": False },
                    "Email Service": { "path": r"C:\Users\firat\OneDrive\Desktop\eemail\start.bat", "autostart": False },
                }
                example_config = {
                    'scripts': scripts,
                    'global_start_delay_seconds': global_delay,
                    'autostart_enabled': autostart_enabled
                }
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(example_config, f, indent=4)
                logging.getLogger("BatchManager").info(f"Beispielkonfiguration in '{path}' gespeichert. Bitte anpassen.")
        except json.JSONDecodeError as e:
            logging.getLogger("BatchManager").error(f"Fehler beim Laden oder Erstellen der Konfigurationsdatei '{path}': {e}")
            logging.getLogger("BatchManager").info("Verwende eine leere Skriptliste.")
            scripts = {}
        except Exception as e:
            logging.getLogger("BatchManager").error(f"Ein unerwarteter Fehler ist beim Laden oder Erstellen der Konfigurationsdatei aufgetreten: {e}")
            logging.getLogger("BatchManager").info("Verwende eine leere Skriptliste.")
            scripts = {}
        return scripts, global_delay, autostart_enabled

    def _load_config_from_file(self):
        """Instance method for loading config, delegates to the static method."""
        return BatchManager._initial_config_load(self.full_config_path)

    def _save_config_to_file(self):
        """Saves the current scripts and global_start_delay to config.json."""
        try:
            config_data = {
                'scripts': self.scripts,
                'global_start_delay_seconds': self.global_start_delay,
                'autostart_enabled': self.autostart_enabled_var.get()
            }
            with open(self.full_config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.logger.info("Konfigurationsdatei erfolgreich gespeichert.")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Konfigurationsdatei: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern der Konfiguration: {e}")


    def reload_scripts_from_config(self):
        self.logger.info("Beginne mit dem Neuladen der Skripte aus der Konfiguration...")
        self.stop_all()
        # Give a moment for processes to terminate
        self.after(500, self._reload_ui)

    def _reload_ui(self):
        self.logger.info("Lade Skripte aus der Konfigurationsdatei neu...")
        
        # Load fresh configuration using the instance method which delegates to static loader
        new_scripts, new_global_start_delay, new_autostart_enabled = self._load_config_from_file()

        if not new_scripts:
            self.logger.warning("Keine Skripte in der Konfiguration gefunden. Manager bleibt im leeren Zustand.")
            # Do not create a new BatchManager instance and call mainloop again
            messagebox.showwarning("Keine Skripte gefunden", "Es wurden keine Skripte in der Konfiguration gefunden. Bitte fügen Sie Skripte hinzu oder prüfen Sie die config.json.", parent=self)
            # Clear UI if no scripts
            self.scripts = {}
            self.create_widgets() # Rebuilds with empty script list
            return

        # Update internal state with new configuration
        self.scripts = new_scripts
        self.global_start_delay = new_global_start_delay
        self.autostart_enabled_var.set(new_autostart_enabled)
        if hasattr(self, 'delay_entry') and self.delay_entry:
            self.delay_entry.delete(0, tk.END)
            self.delay_entry.insert(0, str(self.global_start_delay))

        # Reset all dynamic states
        self.processes = {}
        self.threads = {}
        self.script_raw_output = {name: [] for name in self.scripts}
        self.cpu_history = {name: [0.0] * 20 for name in self.scripts}
        self.autoscroll_vars = {name: tk.BooleanVar(value=True) for name in self.scripts} # Re-initialize autoscroll_vars
        self.overview_switch_vars = {name: tk.BooleanVar(value=False) for name in self.scripts} # Re-initialize switch vars
        self.overview_script_widgets = {} # Clear overview widgets before recreating
        self.script_ui_widgets = {} # Clear script UI widgets before recreating

        # Recreate all UI widgets to reflect new script list
        self.create_widgets()
        self.autostart_scripts()

    def on_closing(self):
        if messagebox.askyesno("Beenden", "Möchten Sie wirklich beenden? Alle laufenden Skripte werden gestoppt."):
            self.stop_all()
            time.sleep(0.1) # Give a short moment for termination attempts
            self.destroy()
        else:
            self.logger.info("Beenden abgebrochen.")

    def _show_about_dialog(self):
        messagebox.showinfo(
            "Über " + self.APP_NAME,
            f"{self.APP_NAME}\n"
            f"Version: {self.APP_VERSION}\n"
            "\n"
            "Ein einfacher Manager zum Starten, Stoppen und Überwachen von Batch-Skripten."
        )

    def add_script_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Skript hinzufügen")
        dialog.transient(self)
        dialog.grab_set()

        dialog_frame = ttk.Frame(dialog, padding="15")
        dialog_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(dialog_frame, text="Skript-Name:", font=self.DEFAULT_FONT).grid(row=0, column=0, sticky="w", pady=5)
        script_name_entry = ttk.Entry(dialog_frame, width=40, font=self.DEFAULT_FONT)
        script_name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(dialog_frame, text="Skript-Pfad (.bat):", font=self.DEFAULT_FONT).grid(row=1, column=0, sticky="w", pady=5)
        script_path_entry = ttk.Entry(dialog_frame, width=40, font=self.DEFAULT_FONT)
        script_path_entry.grid(row=1, column=1, sticky="ew", pady=5)

        def browse_file():
            filepath = filedialog.askopenfilename(
                title="Wählen Sie eine Batch-Datei",
                filetypes=[("Batch files", "*.bat"), ("All files", "*.*")]
            )
            if filepath:
                script_path_entry.delete(0, tk.END)
                script_path_entry.insert(0, filepath)

        browse_button = ttk.Button(dialog_frame, text=" Durchsuchen", image=self.icon_folder, compound=tk.LEFT, command=browse_file)
        browse_button.grid(row=1, column=2, padx=5, pady=5)

        autostart_var = tk.BooleanVar(value=False)
        autostart_checkbox = ttk.Checkbutton(dialog_frame, text=" Beim Start automatisch starten", variable=autostart_var, style="Autostart.TCheckbutton")
        autostart_checkbox.grid(row=2, column=0, columnspan=3, sticky="w", pady=5)

        button_frame = ttk.Frame(dialog_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)

        add_button = ttk.Button(button_frame, text=" Skript hinzufügen", image=self.icon_add, compound=tk.LEFT,
                                command=lambda: self._save_new_script(
                                    script_name_entry.get(), 
                                    script_path_entry.get(), 
                                    autostart_var.get(), 
                                    dialog
                                ))
        add_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text=" Abbrechen", command=dialog.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - dialog.winfo_width() // 2
        y = self.winfo_y() + self.winfo_height() // 2 - dialog.winfo_height() // 2
        dialog.geometry(f"+{x}+{y}")

        script_name_entry.focus_set()
        self.wait_window(dialog)
        
    def _save_new_script(self, name, path, autostart, dialog):
        name = name.strip()
        path = path.strip()

        if not name:
            messagebox.showerror("Fehler", "Skript-Name darf nicht leer sein.", parent=dialog)
            return
        if name in self.scripts:
            messagebox.showerror("Fehler", f"Ein Skript mit dem Namen '{name}' existiert bereits.", parent=dialog)
            return
        if not path or not os.path.exists(path):
            messagebox.showerror("Fehler", "Ungültiger oder nicht existierender Skript-Pfad.", parent=dialog)
            return
        if not path.lower().endswith(".bat"):
            res = messagebox.askyesno("Warnung", "Der Skript-Pfad sollte auf '.bat' enden. Fortfahren?", parent=dialog)
            if not res: return

        try:
            # Update internal scripts dictionary
            self.scripts[name] = {"path": path, "autostart": autostart}
            self._save_config_to_file() # Save the updated config to file
            
            self.logger.info(f"Skript '{name}' erfolgreich zu config.json hinzugefügt.")
            messagebox.showinfo("Erfolg", f"Skript '{name}' wurde erfolgreich hinzugefügt.", parent=dialog)
            dialog.destroy()
            self.reload_scripts_from_config() # Reload UI to show new script

        except Exception as e:
            self.logger.error(f"Fehler beim Hinzufügen des Skripts zu config.json: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern des Skripts: {e}", parent=dialog)

    def edit_script_dialog(self, old_name):
        current_data = self.scripts[old_name]
        dialog = tk.Toplevel(self)
        dialog.title(f"Skript bearbeiten: {old_name}")
        dialog.transient(self)
        dialog.grab_set()

        dialog_frame = ttk.Frame(dialog, padding="15")
        dialog_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(dialog_frame, text="Neuer Skript-Name:", font=self.DEFAULT_FONT).grid(row=0, column=0, sticky="w", pady=5)
        script_name_entry = ttk.Entry(dialog_frame, width=40, font=self.DEFAULT_FONT)
        script_name_entry.insert(0, old_name)
        script_name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(dialog_frame, text="Neuer Skript-Pfad (.bat):", font=self.DEFAULT_FONT).grid(row=1, column=0, sticky="w", pady=5)
        script_path_entry = ttk.Entry(dialog_frame, width=40, font=self.DEFAULT_FONT)
        script_path_entry.insert(0, current_data['path'])
        script_path_entry.grid(row=1, column=1, sticky="ew", pady=5)

        def browse_file():
            filepath = filedialog.askopenfilename(
                title="Wählen Sie eine Batch-Datei",
                filetypes=[("Batch files", "*.bat"), ("All files", "*.*")]
            )
            if filepath:
                script_path_entry.delete(0, tk.END)
                script_path_entry.insert(0, filepath)

        browse_button = ttk.Button(dialog_frame, text=" Durchsuchen", image=self.icon_folder, compound=tk.LEFT, command=browse_file)
        browse_button.grid(row=1, column=2, padx=5, pady=5)

        autostart_var = tk.BooleanVar(value=current_data.get('autostart', False))
        autostart_checkbox = ttk.Checkbutton(dialog_frame, text=" Beim Start automatisch starten", variable=autostart_var, style="Autostart.TCheckbutton")
        autostart_checkbox.grid(row=2, column=0, columnspan=3, sticky="w", pady=5)

        button_frame = ttk.Frame(dialog_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)

        save_button = ttk.Button(button_frame, text=" Änderungen speichern", image=self.icon_edit, compound=tk.LEFT,
                                command=lambda: self._update_script(
                                    old_name,
                                    script_name_entry.get(), 
                                    script_path_entry.get(), 
                                    autostart_var.get(), 
                                    dialog
                                ))
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text=" Abbrechen", command=dialog.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - dialog.winfo_width() // 2
        y = self.winfo_y() + self.winfo_height() // 2 - dialog.winfo_height() // 2
        dialog.geometry(f"+{x}+{y}")

        script_name_entry.focus_set()
        self.wait_window(dialog)

    def _update_script(self, old_name, new_name, new_path, new_autostart, dialog):
        new_name = new_name.strip()
        new_path = new_path.strip()

        if not new_name:
            messagebox.showerror("Fehler", "Skript-Name darf nicht leer sein.", parent=dialog)
            return
        if new_name != old_name and new_name in self.scripts:
            messagebox.showerror("Fehler", f"Ein Skript mit dem Namen '{new_name}' existiert bereits.", parent=dialog)
            return
        if not new_path or not os.path.exists(new_path):
            messagebox.showerror("Fehler", "Ungültiger oder nicht existierender Skript-Pfad.", parent=dialog)
            return
        if not new_path.lower().endswith(".bat"):
            res = messagebox.askyesno("Warnung", "Der Skript-Pfad sollte auf '.bat' enden. Fortfahren?", parent=dialog)
            if not res: return

        try:
            # Update internal scripts dictionary
            if new_name != old_name:
                del self.scripts[old_name]
            self.scripts[new_name] = {"path": new_path, "autostart": new_autostart}



            self._save_config_to_file() # Save the updated config to file
            
            self.logger.info(f"Skript '{old_name}' erfolgreich aktualisiert (Neuer Name: '{new_name}').")
            messagebox.showinfo("Erfolg", f"Skript '{old_name}' wurde erfolgreich aktualisiert.", parent=dialog)
            dialog.destroy()
            self.reload_scripts_from_config() # Reload UI to reflect changes

        except Exception as e:
            self.logger.error(f"Fehler beim Aktualisieren des Skripts '{old_name}': {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern der Änderungen: {e}", parent=dialog)

    def delete_script(self, name):
        if name in self.processes and self.processes[name].poll() is None:
            messagebox.showwarning("Warnung", f"'{name}' läuft noch. Bitte stoppen Sie es, bevor Sie es löschen.", parent=self)
            self.logger.warning(f"Versuch, laufendes Skript '{name}' zu löschen, abgelehnt.")
            return

        if messagebox.askyesno("Skript löschen", f"Möchten Sie das Skript '{name}' wirklich dauerhaft löschen? Dies kann NICHT rückgängig gemacht werden.", parent=self):
            try:
                if name in self.scripts:
                    del self.scripts[name]
                    self._save_config_to_file() # Save the updated config to file

                    self.logger.info(f"Skript '{name}' erfolgreich aus config.json gelöscht.")
                    messagebox.showinfo("Erfolg", f"Skript '{name}' wurde erfolgreich gelöscht.", parent=self)
                    self.reload_scripts_from_config() # Reload UI
                else:
                    self.logger.warning(f"Versuch, nicht existierendes Skript '{name}' zu löschen.")
                    messagebox.showwarning("Warnung", f"Skript '{name}' wurde nicht in der Konfiguration gefunden.", parent=self)
            except Exception as e:
                self.logger.error(f"Fehler beim Löschen des Skripts '{name}': {e}")
                messagebox.showerror("Fehler", f"Fehler beim Löschen des Skripts: {e}", parent=self)
        else:
            self.logger.info(f"Löschvorgang für Skript '{name}' abgebrochen.")


# --- Main Entry Point ---
if __name__ == "__main__":
    # Determine the config file path
    script_directory = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_directory, "config.json")
    
    # Load initial configuration
    scripts_config, global_delay, autostart_enabled = BatchManager._initial_config_load(config_file_path)
    
    # Create and run the application
    app = BatchManager(scripts_config, global_delay, autostart_enabled, config_file_path)
    app.mainloop()
