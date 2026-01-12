# core/telemetry.py

import json
import time
import platform
import os
import socket
import psutil
import uuid
from datetime import datetime
from .debug import Debug

class TelemetryManager:
    def __init__(self, program="veloxwarp", version="1.0.0", debug: Debug = Debug()):
        self.program = program
        self.version = version
        self.debug = debug
        self.log_dir = os.path.join(os.getcwd(), "logs", "telemetry")
        os.makedirs(self.log_dir, exist_ok=True)
        self.session_id = f"session-{uuid.uuid4()}"
        self.log_file = os.path.join(self.log_dir, f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        
        # Base metadata (Identity & Environment)
        self.identity = {
            "program": self.program,
            "version": self.version,
            "user": os.getlogin() if hasattr(os, 'getlogin') else "unknown",
            "host": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "runtime": f"Python {platform.python_version()}",
        }

    def log_event(self, action: str, module: str, command: str = None, args: list = None, 
                  execution_metrics: dict = None, llm_metadata: dict = None, tags: list = None):
        """
        Logs a standardized telemetry event to a JSONL file following the LLM-Aware spec.
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "telemetry_id": str(uuid.uuid4()),
            **self.identity,
            "command": command or f"{self.program} {module} {action}",
            "module": module,
            "action": action,
            "args": args or [],
            "execution": execution_metrics or {},
            "context": {
                "cwd": os.getcwd(),
                "session_id": self.session_id,
                "pid": os.getpid()
            },
            "llm": llm_metadata, # Optional LLM block
            "tags": tags or ["telemetry"]
        }
        
        # Remove None values to keep log clean
        if event["llm"] is None:
            del event["llm"]

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            self.debug.error("Telemetry", f"Failed to write telemetry: {e}")

    def capture_system_metrics(self):
        """Returns current CPU and Memory usage for execution metrics."""
        return {
            "cpu_time_ms": int(psutil.Process().cpu_times().user * 1000),
            "memory_mb": round(psutil.Process().memory_info().rss / (1024 * 1024), 2),
            "thread_count": psutil.Process().num_threads(),
            "pid": os.getpid()
        }

# Global Instance
telemetry = TelemetryManager()
