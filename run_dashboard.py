#!/usr/bin/env python3
"""Hermclaw Web Dashboard Launcher.

Start with:
    python run_dashboard.py
or:
    hermclaw dashboard
"""

import sys
import webbrowser
import threading
import time
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import uvicorn
from rich.console import Console

from hermclaw.dashboard.server import create_dashboard_app
from hermclaw.config import default_config_path

console = Console()

def main():
    host = "127.0.0.1"
    port = 18790
    url = f"http://{host}:{port}"
    config_path = default_config_path()

    console.print(r"""[bold cyan]
    __  __                       ________                
   / / / /__  _________ ___  ____/ / ____/ /___ __      __
  / /_/ / _ \/ ___/ __ `__ \/ __  / /   / / __ `/ | /| / /
 / __  /  __/ /  / / / / / / /_/ / /___/ / /_/ /| |/ |/ / 
/_/ /_/\___/_/  /_/ /_/ /_/\__,_/\____/_/\__,_/ |__/|__/  
    [/bold cyan]""")
    console.print("[bold green]🦞 HermClaw Unified Web Dashboard[/bold green]")
    console.print(f"👉 Opening: [bold underline cyan]{url}[/bold underline cyan]")
    console.print(f"⚙️  Config:  [dim]{config_path}[/dim]")
    console.print("[dim]Press Ctrl+C to stop the dashboard server.[/dim]\n")

    app = create_dashboard_app(config_path=config_path, profile="default")

    def _open_browser():
        time.sleep(1.0)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
