import tkinter as tk
import sys

try:
    root = tk.Tk()
    root.title("Test Window")
    root.geometry("200x100+100+100")
    tk.Label(root, text="Hello, Tkinter!").pack(pady=10)
    print("Window created successfully")
    root.mainloop()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)