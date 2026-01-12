import subprocess
import sys
import os
import signal
import atexit
import psutil
import time
from typing import Optional
from datetime import datetime

class ServerOrchestrator:
    """
    Manages the lifecycle of the Velox Warp server process.
    Singleton-ish pattern usage is recommended in the Dashboard.
    """
    def __init__(self, log_file: str = "logs/engine_output.log"):
        self.process: Optional[subprocess.Popen] = None
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Register cleanup on exit
        atexit.register(self.stop)

    def is_running(self) -> bool:
        """Checks if the server process is currently active or if ports are busy."""
        if self.process and self.process.poll() is None:
            return True
        
        # If handle is lost, check if something is listening on 8765
        return self.check_port_active(8765)

    def check_port_active(self, port: int) -> bool:
        """Checks if a specific port is in LISTEN state."""
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    return True
        except: pass
        return False

    def _get_python_executable(self):
        """
        Determines the best Python executable to use.
        Prioritizes local virtual environments over the global/streamlit one.
        """
        cwd = os.getcwd()
        possible_venvs = [".venv312", ".venv", "venv", "env"]
        
        for venv in possible_venvs:
            if os.name == 'nt':
                python_path = os.path.join(cwd, venv, "Scripts", "python.exe")
            else:
                python_path = os.path.join(cwd, venv, "bin", "python")
            
            if os.path.exists(python_path):
                return python_path
        
        return sys.executable

    def start(self, host: str, port: int, web_port: int, 
              resolution: str, fps: int, monitor_id: int, 
              webp_quality: int, optimize_capture: bool, enable_input: bool = True):
        """
        Starts the server process with the specified configuration.
        Aggressively cleans up any existing processes on the target ports first.
        """
        if self.is_running():
            print("Server is already running.")
            return

        # 1. Aggressive Cleanup of Ports
        self._cleanup_ports([port, web_port])

        # 2. Construct Command
        # Check if we are running in a bundled PyInstaller environment
        is_frozen = hasattr(sys, 'frozen')
        base_dir = os.path.dirname(sys.executable) if is_frozen else os.getcwd()
        
        engine_exe = "velox-engine.exe" if os.name == 'nt' else "velox-engine"
        engine_path = os.path.join(base_dir, engine_exe)

        if is_frozen and os.path.exists(engine_path):
            # Use bundled standalone engine
            cmd = [engine_path]
        else:
            # Development mode: use python + main.py
            python_exe = self._get_python_executable()
            cmd = [python_exe, "main.py"]

        cmd.extend([
            "--mode", "server",
            "--host", host,
            "--port", str(port),
            "--web-port", str(web_port),
            "--resolution", resolution,
            "--frame-rate", str(fps),
            "--monitor-id", str(monitor_id)
        ])
        
        if webp_quality:
            cmd.extend(["--webp-quality", str(webp_quality)])
        if optimize_capture:
            cmd.append("--optimize-capture")
        if not enable_input:
            cmd.append("--disable-input")

        # 3. Launch Process
        # Append to log file
        with open(self.log_file, "a") as f:
            f.write(f"\n--- Session Start: {datetime.now()} ---\n")
            f.write(f"Command: {' '.join(cmd)}\n")
        
        # Open file handles for stdout/stderr to persist
        self._stdout_handle = open(self.log_file, "a")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=self._stdout_handle,
            stderr=self._stdout_handle,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        print(f"Server started with PID: {self.process.pid}")

    def stop(self):
        """Stops the server process safely."""
        if self.process:
            try:
                print(f"Stopping server (PID: {self.process.pid})...")
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], capture_output=True)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                
                self.process.wait(timeout=2)
            except Exception as e:
                print(f"Error stopping process: {e}")
            finally:
                self.process = None
                if hasattr(self, '_stdout_handle') and self._stdout_handle:
                    self._stdout_handle.close()

    def _cleanup_ports(self, ports: list[int]):
        """Kills any process listening on the specified ports."""
        try:
            for port in ports:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        if conn.pid != os.getpid():
                            try: 
                                p = psutil.Process(conn.pid)
                                p.kill()
                            except: pass
            time.sleep(0.5) # Give OS time to release ports
        except Exception: pass

    def get_log_tail(self, n: int = 50) -> list[str]:
        """Returns the last n lines of the log file."""
        if not os.path.exists(self.log_file):
            return ["Log file not found."]
        try:
            with open(self.log_file, "r") as f:
                # Efficient-ish tail for small log files
                return f.readlines()[-n:]
        except Exception as e:
            return [f"Error reading log: {e}"]
