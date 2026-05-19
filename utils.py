import threading
import traceback
import json
import time
import os

from datetime import datetime
from rich.console import Console
from rich.panel import Panel

console = Console()

id_neonutil = 851436490415931422
id_owo = 408785106942164992

def load(file):
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def is_termux():
    termux_prefix = os.environ.get("PREFIX")
    termux_home = os.environ.get("HOME")

    if termux_prefix and "com.termux" in termux_prefix:
        return True
    elif termux_home and "com.termux" in termux_home:
        return True
    else:
        return os.path.isdir("/data/data/com.termux")

if not is_termux():
    from plyer import notification

def run_system_command(command, timeout, retry=False, delay=5):
    def target():
        try:
            os.system(command)
        except Exception as e:
            print(f"Error executing command: {command} - {e}")

    # Create and start a thread to execute the command
    thread = threading.Thread(target=target)
    thread.start()

    # Wait for the thread to finish, with a timeout
    thread.join(timeout)

    # If the thread is still alive after the timeout, terminate it
    if thread.is_alive():
        print(f"Error: {command} command failed! (captcha)")
        if retry:
            print(f"Retrying '{command}' after {delay}s")
            time.sleep(delay)
            run_system_command(command, timeout)

def notify(content, title):
        if is_termux():
            run_system_command(
                f"termux-notification -t '{title}' -c '{content}' --led-color '#a575ff' --priority 'high'",
                timeout=5,
                retry=True,
            )
        else:
            notification.notify(title=title, message=content, app_icon=None, timeout=15)

def printBox(text, color, title=None):
    text = text.center(console.width - 2)
    test_panel = Panel(text, style=color, title=title)
    console.print(test_panel)

def log(text, color):
    time = datetime.now().strftime("%H:%M:%S")
    frame_info = traceback.extract_stack()[-2]
    lineno = frame_info.lineno

    content_to_print = f"[#676585]❲{time}❳[/#676585] {text} | [#676585]❲line:{lineno}❳[/#676585]"
    console.print(content_to_print, style=color)