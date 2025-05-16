import psutil
import tkinter as tk
from tkinter import ttk
import threading
import time
import json
import os
from plyer import battery
import pystray
from PIL import Image
import win32com.client
import sys
import shutil

# =====================
# System Resource Dashboard - Main Application
# =====================
# This script creates a system resource dashboard with floating widgets for CPU, RAM, Disk, Battery, Risk summary, and Network usage.
# Each widget is a borderless, auto-resizing window that can be toggled on/off and remembers its position.
# The main window provides controls to close, restart, or kill individual widgets. Widgets are also accessible from the system tray.
#
# Main components:
# - ResourceWidget: Class for each resource widget window
# - Data functions: Get system resource usage
# - Config functions: Save/load widget state and position
# - System tray: Quick access to widget toggles and quit
# - Main window: Control panel for all widgets
# - Startup: Optionally adds app to Windows startup
# =====================

# Configuration file to store widget states and positions
def ensure_config_file():
    """
    Ensures widget_config.json exists in SysDBoard. If not, copies from project root or creates default.
    """
    config_path = os.path.join(os.path.dirname(__file__), "widget_config.json")
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "widget_config.json"))
    if not os.path.exists(config_path):
        if os.path.exists(root_path):
            shutil.copy2(root_path, config_path)
        else:
            # Create default config if not found anywhere
            default_config = {
                "cpu_widget": {"enabled": True, "x": 0, "y": 0},
                "ram_widget": {"enabled": True, "x": 0, "y": 0},
                "disk_widget": {"enabled": True, "x": 0, "y": 0},
                "battery_widget": {"enabled": True, "x": 0, "y": 0},
                "risk_widget": {"enabled": True, "x": 0, "y": 0},
                "network_widget": {"enabled": True, "x": 0, "y": 0},
                "refresh_rate": 2.0
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "widget_config.json")
ensure_config_file()

# --- Config functions ---
def load_config():
    """
    Loads the widget configuration from file or returns default config.
    Used at startup to restore widget state and positions.
    (YOU NEED TO DELETE THIS FILE IF YOU CHNAGE THE POSITION OF A WIDGET!!!)
    """
    default_config = {
        "cpu_widget": {"enabled": True, "x": 0, "y": 0},
        "ram_widget": {"enabled": True, "x": 0, "y": 0},
        "disk_widget": {"enabled": True, "x": 0, "y": 0},
        "battery_widget": {"enabled": True, "x": 0, "y": 0},
        "risk_widget": {"enabled": True, "x": 0, "y": 0},
        "network_widget": {"enabled": True, "x": 0, "y": 0},
        "refresh_rate": 2.0  # Seconds
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return default_config

def save_config(config):
    """
    Saves the current widget configuration to file.
    Called whenever widget position or enabled state changes.
    """
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# --- Risk/Warning Logic --- (subject to change, really)
def get_risk_level(value, thresholds):
    """
    Returns risk level and color based on value and thresholds.
    Used by widgets to display risk status.
    """
    if value >= thresholds["high"]:
        return "High Risk", "red"
    elif value >= thresholds["medium"]:
        return "Medium Risk", "orange"
    else:
        return "Low Risk", "green"

def get_risk_color(widget_name, value, theme="light"):
    """
    Returns the color for the usage text based on widget type, value, and theme.
    Used by each widget to color its usage dynamically.
    """
    # Define color sets for dark and light themes
    if theme == "dark":
        colors = {
            "red": "#ff5555",
            "orange": "#ffae42",
            "yellow": "#ffff55",
            "green": "#55ff55",
            "default": "#ffffff"
        }
    else:
        colors = {
            "red": "#b22222",
            "orange": "#ff8c00",
            "yellow": "#bdb76b",
            "green": "#228b22",
            "default": "#222222"
        }
    if widget_name == "cpu":
        if value > 75:
            return colors["red"]
        elif value > 50:
            return colors["orange"]
        elif value > 25:
            return colors["yellow"]
        else:
            return colors["green"]
    elif widget_name == "ram" or widget_name == "disk":
        if value > 90:
            return colors["red"]
        elif value > 75:
            return colors["orange"]
        elif value > 50:
            return colors["yellow"]
        else:
            return colors["green"]
    elif widget_name == "battery":
        if value < 20:
            return colors["red"]
        elif value < 50:
            return colors["orange"]
        elif value < 75:
            return colors["yellow"]
        else:
            return colors["green"]
    else:
        return colors["default"]

# --- Widget Class ---
class ResourceWidget:
    """
    Represents a floating resource widget window (CPU, RAM, Disk, Battery, Risk, Network).
    Handles creation, updating, toggling, and position saving for each widget.
    """
    def __init__(self, name, title, get_data_func, thresholds=None):
        self.name = name
        self.title = title
        self.enabled = config[f"{name}_widget"]["enabled"]
        self.x = config[f"{name}_widget"]["x"]
        self.y = config[f"{name}_widget"]["y"]
        self.root = None
        self.label = None
        self.get_data_func = get_data_func
        self.thresholds = thresholds
        self.running = False
        self.thread = None
        self.theme = None  # Will be set in create_widget

    def create_widget(self):
        """
        Creates the widget window, applies theme, sets position, and starts update thread.
        Called when widget is enabled or restarted.
        """
        if not self.enabled:
            return
        self.root = tk.Toplevel()

        self.root.overrideredirect(True)  # Remove titlebar
        self.root.attributes('-alpha', 0.9)
        self.root.title(self.title)
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)  # Prevent manual resizing

        # --- Theme Switcher (Dark/Light) --- (UNCOMMENT TO USE)
        # To switch between dark and light themes, comment/uncomment the relevant block below.

        #  --- DARK THEME ---
        self.theme = "dark"
        self.root.configure(bg='#2b2b2b')
        self.label = ttk.Label(self.root, text="Initializing...", font=("Arial", 12), foreground='#ffffff', background='#2b2b2b', justify="left", anchor="nw")

        # --- LIGHT THEME ---
        # self.theme = "light"
        # self.root.configure(bg='#f0f0f0')
        # self.label = ttk.Label(self.root, text="Initializing...", font=("Arial", 12), foreground='#2b2b2b', background='#f0f0f0', justify="left", anchor="nw")

        self.label.pack(padx=15, pady=15, fill="both", expand=True)
        self.root.update_idletasks()  # Let Tkinter calculate window size
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        self.root.geometry(f"{width}x{height}+{self.x}+{self.y}")  # Set position, keep size
        self.root.bind("<Configure>", self.save_position)
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def save_position(self, event):
        """
        Saves the current window position to config on move/resize.
        Triggered by <Configure> event.
        """
        if self.root:
            self.x = self.root.winfo_x()
            self.y = self.root.winfo_y()
            config[f"{self.name}_widget"]["x"] = self.x
            config[f"{self.name}_widget"]["y"] = self.y
            save_config(config)

    def update(self):
        """
        Periodically updates the widget's label with latest data and risk info.
        Runs in a background thread while widget is active.
        """
        while self.running and self.root:
            try:
                value = self.get_data_func()
                if self.name == "risk":
                    # For risk widget, use left/top alignment and let label auto-resize
                    color = "#222222" if getattr(self, "theme", "light") == "light" else "#ffffff"
                    text = f"{self.title}\n{value}"
                    self.root.after(0, lambda: [
                        self.label.config(text=text, foreground=color, justify="left", anchor="nw"),
                        self.label.update_idletasks(),
                        self.root.geometry("")  # Let window auto-resize to label
                    ])
                elif self.name in ["cpu", "ram", "disk", "battery"]:
                    try:
                        percent = float(value.split()[0])
                    except Exception:
                        percent = 0
                    color = get_risk_color(self.name, percent, getattr(self, "theme", "light"))
                    text = f"{self.title}\n{value}"
                    self.root.after(0, lambda: [self.label.config(text=text, foreground=color), self.root.update_idletasks(), self.root.geometry("")])
                else:
                    color = "#222222" if getattr(self, "theme", "light") == "light" else "#ffffff"
                    text = f"{self.title}\n{value}"
                    self.root.after(0, lambda: [self.label.config(text=text, foreground=color), self.root.update_idletasks(), self.root.geometry("")])
                time.sleep(config["refresh_rate"])
            except Exception as e:
                self.root.after(0, lambda: self.label.config(text=f"Error: {e}", foreground="red"))
                break

    def stop(self):
        """
        Stops the widget, destroys the window, and ends the update thread.
        Called when widget is disabled or app is quitting.
        """
        self.running = False
        if self.root:
            self.root.destroy()
            self.root = None

    def toggle(self, enable):
        """
        Enables or disables the widget, updating config and creating/destroying window as needed.
        Used by main window and system tray.
        """
        self.enabled = enable
        config[f"{self.name}_widget"]["enabled"] = enable
        save_config(config)
        if enable and not self.root:
            self.create_widget()
        elif not enable and self.root:
            self.stop()

# --- System Tray Icon ---
def create_system_tray():
    """
    Creates a system tray icon with menu to toggle widgets and quit the app.
    Runs in a background thread. Calls widget.toggle() and on_quit as needed.
    """
    def on_quit(icon, item):
        for widget in widgets:
            widget.stop()
        if icon:
            icon.stop()
        # Use after to quit Tkinter from the main thread
        try:
            main_root.after(0, main_root.quit)
        except Exception:
            pass

    def toggle_widget(widget_name):
        widget = next(w for w in widgets if w.name == widget_name)
        widget.toggle(not widget.enabled)

    menu = (
        pystray.MenuItem("Toggle CPU Widget", lambda: toggle_widget("cpu")),
        pystray.MenuItem("Toggle RAM Widget", lambda: toggle_widget("ram")),
        pystray.MenuItem("Toggle Disk Widget", lambda: toggle_widget("disk")),
        pystray.MenuItem("Toggle Battery Widget", lambda: toggle_widget("battery")),
        pystray.MenuItem("Toggle Risk Widget", lambda: toggle_widget("risk")),
        pystray.MenuItem("Toggle Network Widget", lambda: toggle_widget("network")),
        pystray.MenuItem("Quit", on_quit)
    )
    image = Image.new('RGB', (64, 64), color='blue')  # Placeholder icon
    icon = pystray.Icon("System Dashboard", image, "System Dashboard", menu)
    icon.run()

# --- Windows Startup Shortcut ---
def add_to_startup():
    """
    Adds a shortcut to this script in the Windows Startup folder if not already present.
    """
    try:
        script_path = os.path.abspath(__file__)
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_folder, "SystemDashboard.lnk")
        if not os.path.exists(shortcut_path):
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{script_path}"'
            shortcut.WorkingDirectory = os.path.dirname(script_path)
            shortcut.save()
    except Exception as e:
        print(f"Failed to add to startup: {e}")

def remove_from_startup():
    """
    Removes the shortcut from the Windows Startup folder if it exists.
    """
    try:
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_folder, "SystemDashboard.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
    except Exception as e:
        print(f"Failed to remove from startup: {e}")

# --- Data Functions ---
def get_cpu_usage():
    """
    Returns current CPU usage as a string (e.g., '23 %'). Used by CPU widget.
    """
    return f"{psutil.cpu_percent(interval=1)} %"

def get_ram_usage():
    """
    Returns current RAM usage as a string (e.g., '45 %'). Used by RAM widget.
    """
    mem = psutil.virtual_memory()
    return f"{mem.percent} %"

def get_disk_usage():
    """
    Returns current Disk usage as a string (e.g., '67 %'). Used by Disk widget.
    Uses the system drive on Windows, '/' on other OS.
    """
    import platform
    if platform.system() == "Windows":
        drive = os.environ.get("SystemDrive", "C:") + "\\"
    else:
        drive = "/"
    disk = psutil.disk_usage(drive)
    return f"{disk.percent} %"

def get_battery_status():
    """
    Returns current battery percentage as a string (e.g., '80 %'). Used by Battery widget.
    Returns 'N/A' if battery info is unavailable.
    """
    try:
        status = battery.get_state()
        return f"{status['percentage']} %"
    except:
        return "N/A"

def get_risk_summary():
    """
    Aggregates risk levels from all enabled widgets and returns a detailed summary string.
    Shows which resource is at risk and why.
    Used by the Risk widget.
    """
    summary = []
    # CPU
    if config["cpu_widget"]["enabled"]:
        cpu = float(get_cpu_usage().split()[0])
        if cpu >= 90:
            summary.append(f"CPU usage is CRITICAL ({cpu:.0f}%)")
        elif cpu >= 70:
            summary.append(f"CPU usage is HIGH ({cpu:.0f}%)")
        elif cpu >= 50:
            summary.append(f"CPU usage is MODERATE ({cpu:.0f}%)")
    # RAM
    if config["ram_widget"]["enabled"]:
        ram = float(get_ram_usage().split()[0])
        if ram >= 90:
            summary.append(f"RAM usage is CRITICAL ({ram:.0f}%)")
        elif ram >= 70:
            summary.append(f"RAM usage is HIGH ({ram:.0f}%)")
        elif ram >= 50:
            summary.append(f"RAM usage is MODERATE ({ram:.0f}%)")
    # Disk
    if config["disk_widget"]["enabled"]:
        disk = float(get_disk_usage().split()[0])
        if disk >= 90:
            summary.append(f"Disk usage is CRITICAL ({disk:.0f}%)")
        elif disk >= 80:
            summary.append(f"Disk usage is HIGH ({disk:.0f}%)")
        elif disk >= 50:
            summary.append(f"Disk usage is MODERATE ({disk:.0f}%)")
    # Battery
    if config["battery_widget"]["enabled"] and get_battery_status() != "N/A":
        batt = float(get_battery_status().split()[0])
        if batt <= 10:
            summary.append(f"Battery is CRITICALLY LOW ({batt:.0f}%)")
        elif batt <= 30:
            summary.append(f"Battery is LOW ({batt:.0f}%)")
        elif batt <= 75:
            summary.append(f"Battery is MODERATE ({batt:.0f}%)")
    if not summary:
        return "All systems normal."
    return "\n".join(summary)

def get_network_usage():
    """
    Returns network usage details as a string (sent/received/total in MB and current speed).
    Used by the Network widget.
    """
    import psutil
    import time
    net1 = psutil.net_io_counters()
    time.sleep(1)
    net2 = psutil.net_io_counters()
    sent_mb = net2.bytes_sent / (1024 * 1024)
    recv_mb = net2.bytes_recv / (1024 * 1024)
    total_mb = sent_mb + recv_mb
    sent_speed = (net2.bytes_sent - net1.bytes_sent) / (1024 * 1024)
    recv_speed = (net2.bytes_recv - net1.bytes_recv) / (1024 * 1024)
    return f"Sent: {sent_mb:.2f} MB\nRecv: {recv_mb:.2f} MB\nTotal: {total_mb:.2f} MB\nUp: {sent_speed:.2f} MB/s\nDown: {recv_speed:.2f} MB/s"

# --- Widget Position Initialization ---
def initialize_grid_positions():
    """
    Sets default positions for all widgets in a 6x1 horizontal grid (single row) at the top-right of the screen.
    Only applies if widget has not been moved before (x=0, y=0).
    Called at startup.
    """
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    root.destroy()

    widget_width = 200
    widget_height = 100
    margin = 10
    # Start at top-right, move left for each widget
    # Calculate total width for all widgets (no spacing)
    total_width = 6 * widget_width
    start_x = screen_width - total_width - margin
    start_y = margin  # 10 pixels from top

    positions = [
        (start_x + i * widget_width, start_y) for i in range(6)
    ]
    widget_names = [
        "cpu_widget", "ram_widget", "disk_widget", "battery_widget", "risk_widget", "network_widget"
    ]
    for name, (x, y) in zip(widget_names, positions):
        if name in config and config[name]["x"] == 0 and config[name]["y"] == 0:
            config[name]["x"] = x
            config[name]["y"] = y
        elif name not in config:
            config[name] = {"enabled": True, "x": x, "y": y}
    save_config(config)

# --- Main Window (Control Panel) ---
def create_main_window():
    """
    Creates the main control window with buttons to close, restart, or kill widgets.
    Allows user to control all widgets from one place.
    """
    global main_root
    global startup_var

    def on_quit(icon, item):
        for widget in widgets:
            widget.stop()
        if icon:
            icon.stop()
        main_root.quit()

    def toggle_widget(widget_name):
        widget = next(w for w in widgets if w.name == widget_name)
        widget.toggle(not widget.enabled)

    def on_startup_toggle():
        if startup_var.get():
            add_to_startup()
        else:
            remove_from_startup()

    main_root = tk.Tk()
    main_root.title("System Dashboard Control")
    main_root.geometry("300x400")
    main_root.configure(bg='#2b2b2b')

    # Apply dark theme to ttk widgets
    style = ttk.Style()
    style.theme_use('clam')  # Use 'clam' theme for customizability
    style.configure('TButton', background='#3c3c3c', foreground='#ffffff', bordercolor='#555555')
    style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')

    # Startup toggle
    startup_var = tk.BooleanVar()
    # Check if shortcut exists
    startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
    shortcut_path = os.path.join(startup_folder, "SystemDashboard.lnk")
    startup_var.set(os.path.exists(shortcut_path))
    ttk.Checkbutton(main_root, text="Start at Windows Startup", variable=startup_var, command=on_startup_toggle).pack(pady=5)

    # Buttons
    ttk.Button(main_root, text="Close All", command=lambda: on_quit(None, None)).pack(pady=5)
    ttk.Button(main_root, text="Restart All", command=restart_all).pack(pady=5)
    ttk.Button(main_root, text="Kill CPU Widget", command=lambda: toggle_widget("cpu")).pack(pady=5)
    ttk.Button(main_root, text="Kill RAM Widget", command=lambda: toggle_widget("ram")).pack(pady=5)
    ttk.Button(main_root, text="Kill Disk Widget", command=lambda: toggle_widget("disk")).pack(pady=5)
    ttk.Button(main_root, text="Kill Battery Widget", command=lambda: toggle_widget("battery")).pack(pady=5)
    ttk.Button(main_root, text="Kill Risk Widget", command=lambda: toggle_widget("risk")).pack(pady=5)
    ttk.Button(main_root, text="Kill Network Widget", command=lambda: toggle_widget("network")).pack(pady=5)

def restart_all():
    """
    Stops and restarts all widgets that are enabled.
    Used by the 'Restart All' button in the main window.
    """
    for widget in widgets:
        widget.stop()
        if widget.enabled:
            widget.create_widget()
            if widget.root:
                widget.root.overrideredirect(True)  # Remove titlebar

# --- Main Application Entry Point ---
if __name__ == "__main__":
    # --- Auto-install required libraries if missing ---
    import subprocess
    import importlib
    required = [
        ("psutil", "psutil"),
        ("tkinter", "tk"),
        ("plyer", "plyer"),
        ("pystray", "pystray"),
        ("PIL", "Pillow"),
        ("win32com.client", "pywin32"),
    ]
    for mod, pipname in required:
        try:
            importlib.import_module(mod)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pipname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 1. Load config (widget state/positions)
    config = load_config()
    # 2. Set default widget positions if needed
    initialize_grid_positions()
    # 3. Startup shortcut is now user-controlled, do not auto-add/remove
    # 4. Create all widget objects (but only show if enabled)
    widgets = [
        ResourceWidget("cpu", "CPU Usage", get_cpu_usage, {"medium": 70, "high": 90}),
        ResourceWidget("ram", "RAM Usage", get_ram_usage, {"medium": 70, "high": 90}),
        ResourceWidget("disk", "Disk Usage", get_disk_usage, {"medium": 80, "high": 90}),
        ResourceWidget("battery", "Battery Status", get_battery_status, {"medium": 30, "high": 10}),
        ResourceWidget("risk", "Risk Summary", get_risk_summary),
        ResourceWidget("network", "Network Usage", get_network_usage)
    ]
    # 5. Create the main control window
    create_main_window()
    # Hide main window from taskbar
    try:
        main_root.attributes('-toolwindow', True)
        main_root.overrideredirect(True)
    except Exception:
        pass
    # 6. Show all enabled widgets
    for widget in widgets:
        if widget.enabled:
            widget.create_widget()
    # 7. Start the system tray icon in a background thread
    tray_thread = threading.Thread(target=create_system_tray, daemon=True)
    tray_thread.start()
    # 8. Start the Tkinter main loop (blocks until app closes)
    main_root.mainloop()
    # After mainloop ends, force exit to ensure all threads/processes are killed
    import os
    os._exit(0)

"""
Workflow of the Script:

1. Initialization:
   - The script sets up necessary imports, configurations, and initializes required objects (such as widgets and the main Tkinter root window).

2. Widget Handling:
   - It iterates through all available widgets.
   - For each widget that is enabled (`widget.enabled` is True), it calls `widget.create_widget()` to add it to the GUI.

3. System Tray Icon:
   - A separate background thread is started to handle the system tray icon using `threading.Thread`.
   - This allows the tray icon to function independently without blocking the main GUI.

4. Main Event Loop:
   - The Tkinter main loop (`main_root.mainloop()`) is started.
   - This loop keeps the GUI responsive and running until the user closes the application.

Key Points:
- Widgets are only created if they are enabled.
- The system tray icon runs in a background thread to avoid freezing the GUI.
- The main loop is blocking, so all setup must be done before calling it.
"""

