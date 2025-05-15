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
CONFIG_FILE = "widget_config.json"

# --- Config functions ---
def load_config():
    """
    Loads the widget configuration from file or returns default config.
    Used at startup to restore widget state and positions.
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

# --- Risk/Warning Logic ---
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

def get_risk_color(widget_name, value):
    """
    Returns the color for the usage text based on widget type and value.
    Used by each widget to color its usage dynamically.
    """
    if widget_name == "cpu":
        # CPU: red > 75, orange > 50, yellow > 25, green <= 25
        if value > 75:
            return "red"
        elif value > 50:
            return "orange"
        elif value > 25:
            return "yellow"
        else:
            return "green"
    elif widget_name == "ram" or widget_name == "disk":
        # RAM/Disk: red > 90, orange > 75, yellow > 50, green <= 50
        if value > 90:
            return "red"
        elif value > 75:
            return "orange"
        elif value > 50:
            return "yellow"
        else:
            return "green"
    elif widget_name == "battery":
        # Battery: red < 20, orange < 50, yellow < 75, green >= 75
        if value < 20:
            return "red"
        elif value < 50:
            return "orange"
        elif value < 75:
            return "yellow"
        else:
            return "green"
    else:
        return "white"

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

    def create_widget(self):
        """
        Creates the widget window, applies theme, sets position, and starts update thread.
        Called when widget is enabled or restarted.
        """
        if not self.enabled:
            return
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)  # Remove titlebar
        self.root.title(self.title)
        # Remove fixed geometry, let window size to content
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)  # Allow resizing
        # Apply dark theme
        self.root.configure(bg='#2b2b2b')
        self.label = ttk.Label(self.root, text="Initializing...", font=("Arial", 12), foreground='#ffffff', background='#2b2b2b')
        self.label.pack(padx=15, pady=15)
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
                # For widgets with percentage, extract the numeric value
                if self.name in ["cpu", "ram", "disk", "battery"]:
                    try:
                        percent = float(value.split()[0])
                    except Exception:
                        percent = 0
                    color = get_risk_color(self.name, percent)
                    text = f"{self.title}\n{value}"
                else:
                    color = "white"
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
        icon.stop()
        main_root.quit()  # Ensure main window closes
        sys.exit()

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
    Called at startup to ensure auto-launch on boot.
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
    """
    disk = psutil.disk_usage('/')
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
    Aggregates risk levels from all enabled widgets and returns a summary string.
    Used by the Risk widget.
    """
    risks = []
    if config["cpu_widget"]["enabled"]:
        cpu = float(get_cpu_usage().split()[0])
        risks.append(get_risk_level(cpu, {"medium": 70, "high": 90})[0])
    if config["ram_widget"]["enabled"]:
        ram = float(get_ram_usage().split()[0])
        risks.append(get_risk_level(ram, {"medium": 70, "high": 90})[0])
    if config["disk_widget"]["enabled"]:
        disk = float(get_disk_usage().split()[0])
        risks.append(get_risk_level(disk, {"medium": 80, "high": 90})[0])
    if config["battery_widget"]["enabled"] and get_battery_status() != "N/A":
        batt = float(get_battery_status().split()[0])
        risks.append(get_risk_level(batt, {"medium": 30, "high": 10})[0])
    return "\n".join(risks) or "No risks"

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

    def on_quit(icon, item):
        for widget in widgets:
            widget.stop()
        if icon:
            icon.stop()
        main_root.quit()
        sys.exit()

    def toggle_widget(widget_name):
        widget = next(w for w in widgets if w.name == widget_name)
        widget.toggle(not widget.enabled)

    main_root = tk.Tk()
    main_root.title("System Dashboard Control")
    main_root.geometry("300x300")
    main_root.configure(bg='#2b2b2b')

    # Apply dark theme to ttk widgets
    style = ttk.Style()
    style.theme_use('clam')  # Use 'clam' theme for customizability
    style.configure('TButton', background='#3c3c3c', foreground='#ffffff', bordercolor='#555555')
    style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')

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
    # 3. Add to Windows startup if not already present
    ##add_to_startup()
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