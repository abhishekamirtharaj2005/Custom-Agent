"""System information tool.

Gathers system metrics: CPU, RAM, disk, GPU, network, processes,
battery, and OS information. Cross-platform.
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class SystemInfoTool(ToolABC):
    """Gather system information and metrics."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system_info",
            description=(
                "Get system information. Actions: overview (OS, CPU, RAM, disk), "
                "processes (top processes by CPU/memory), network (IP, interfaces), "
                "gpu (GPU info if available), battery (laptop battery status), "
                "env (environment variables)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["overview", "processes", "network", "gpu", "battery", "env"],
                        "description": "What system info to retrieve.",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "overview")
        system = platform.system()

        try:
            if action == "overview":
                return self._overview(system)
            elif action == "processes":
                return self._processes(system)
            elif action == "network":
                return self._network(system)
            elif action == "gpu":
                return self._gpu()
            elif action == "battery":
                return self._battery(system)
            elif action == "env":
                return self._env_vars()
            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"System info error: {exc}")

    def _overview(self, system: str) -> ToolResult:
        info = [
            f"OS: {platform.system()} {platform.release()} ({platform.version()})",
            f"Architecture: {platform.machine()}",
            f"Hostname: {platform.node()}",
            f"Python: {platform.python_version()}",
            f"Processor: {platform.processor() or 'N/A'}",
        ]

        if system == "Windows":
            # Get RAM and disk via PowerShell
            try:
                ram = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB"],
                    capture_output=True, text=True, timeout=5,
                )
                if ram.returncode == 0:
                    info.append(f"Total RAM: {float(ram.stdout.strip()):.1f} GB")
            except Exception:
                pass

            try:
                disk = subprocess.run(
                    ["powershell", "-Command",
                     "Get-PSDrive C | Select-Object @{N='Used';E={[math]::Round($_.Used/1GB,1)}},@{N='Free';E={[math]::Round($_.Free/1GB,1)}} | Format-List"],
                    capture_output=True, text=True, timeout=5,
                )
                if disk.returncode == 0:
                    info.append(f"Disk (C:): {disk.stdout.strip()}")
            except Exception:
                pass
        else:
            try:
                mem = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
                if mem.returncode == 0:
                    info.append(f"\nMemory:\n{mem.stdout}")
            except Exception:
                pass

            try:
                disk = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
                if disk.returncode == 0:
                    info.append(f"\nDisk:\n{disk.stdout}")
            except Exception:
                pass

        return ToolResult(ok=True, output="\n".join(info))

    def _processes(self, system: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Sort-Object -Property CPU -Descending | Select-Object -First 15 -Property Name, Id, CPU, WorkingSet64 | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=10,
            )
        else:
            result = subprocess.run(
                ["ps", "aux", "--sort=-pcpu"],
                capture_output=True, text=True, timeout=5,
            )
        output = result.stdout
        if len(output) > 3000:
            output = output[:3000] + "\n... [truncated]"
        return ToolResult(ok=True, output=output)

    def _network(self, system: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True, text=True, timeout=10,
            )
        else:
            result = subprocess.run(
                ["ip", "addr"],
                capture_output=True, text=True, timeout=5,
            )
        output = result.stdout
        if len(output) > 3000:
            output = output[:3000] + "\n... [truncated]"
        return ToolResult(ok=True, output=output)

    def _gpu(self) -> ToolResult:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(ok=True, output=f"GPU Info (NVIDIA):\n{result.stdout}")
        except FileNotFoundError:
            pass

        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,adapterram,driverversion"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(ok=True, output=f"GPU Info:\n{result.stdout}")
        except FileNotFoundError:
            pass

        return ToolResult(ok=True, output="No GPU info available (nvidia-smi not found).")

    def _battery(self, system: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject win32_battery | Select-Object EstimatedChargeRemaining, BatteryStatus | Format-List)"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ToolResult(ok=True, output=f"Battery:\n{result.stdout}")
            return ToolResult(ok=True, output="No battery detected (desktop PC?).")
        else:
            try:
                result = subprocess.run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                                       capture_output=True, text=True, timeout=5)
                return ToolResult(ok=True, output=result.stdout)
            except FileNotFoundError:
                return ToolResult(ok=True, output="Battery info not available.")

    def _env_vars(self) -> ToolResult:
        # Show relevant env vars (not all, for security)
        relevant_keys = [
            "PATH", "HOME", "USERPROFILE", "SHELL", "TERM", "LANG",
            "HERMCLAW_HOME", "OLLAMA_HOST", "OPENAI_API_KEY",
            "PYTHONPATH", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV",
        ]
        lines = ["Environment Variables:"]
        for key in relevant_keys:
            val = os.environ.get(key)
            if val:
                # Mask API keys
                if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                    val = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
                if len(val) > 200:
                    val = val[:200] + "..."
                lines.append(f"  {key}={val}")
        return ToolResult(ok=True, output="\n".join(lines))
