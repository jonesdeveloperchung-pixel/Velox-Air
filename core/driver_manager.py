import subprocess
import os
import platform
import logging

class DriverManager:
    """
    Manages the installation and status checking of virtual display drivers.
    """
    def __init__(self, drivers_root: str = "drivers"):
        self.system = platform.system()
        self.drivers_root = drivers_root
        self.logger = logging.getLogger("DriverManager")

    def get_status(self) -> dict:
        """Returns the status of the virtual driver for the current platform."""
        if self.system == "Windows":
            return self._check_windows_idd()
        elif self.system == "Linux":
            return self._check_linux_evdi()
        elif self.system == "Darwin": # MacOS
            return self._check_macos_dummy()
        else:
            return {"installed": False, "message": "Unsupported OS"}

    def _check_windows_idd(self) -> dict:
        """Checks for IddSampleDriver (Indirect Display Driver)."""
        # A simple check: look for the device using PnPUtil or devcon
        # Note: This requires admin rights to be accurate for all devices, 
        # but 'pnputil /enum-devices /class Display' works in user mode usually.
        try:
            # We look for a specific Hardware ID usually associated with the sample driver
            # generic ID for IddSampleDriver is often 'IddSampleDriver'
            result = subprocess.run(
                ["pnputil", "/enum-devices", "/class", "Display"], 
                capture_output=True, text=True
            )
            if "IddSampleDriver" in result.stdout:
                return {"installed": True, "message": "IddSampleDriver Detected"}
            else:
                return {"installed": False, "message": "Not Found"}
        except Exception as e:
            return {"installed": False, "message": f"Check Failed: {e}"}

    def _check_linux_evdi(self) -> dict:
        """Checks for EVDI module."""
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True)
            if "evdi" in result.stdout:
                return {"installed": True, "message": "EVDI Module Loaded"}
            else:
                return {"installed": False, "message": "EVDI Module Not Loaded"}
        except:
            return {"installed": False, "message": "Check Failed"}

    def _check_macos_dummy(self) -> dict:
        return {"installed": False, "message": "MacOS Virtual Display not yet implemented"}

    def get_install_script_path(self) -> str:
        if self.system == "Windows":
            return os.path.join(self.drivers_root, "windows", "install_idd.ps1")
        elif self.system == "Linux":
            return os.path.join(self.drivers_root, "linux", "install_evdi.sh")
        return ""

    def install_driver(self) -> str:
        """
        Executes the installation script.
        Returns a message indicating the result or instruction.
        """
        script = self.get_install_script_path()
        if not os.path.exists(script):
            return f"Script not found: {script}"

        if self.system == "Windows":
            # On Windows, we can't easily elevate from here without breaking the UI flow often.
            # Best to return the command for the user to run, or try runas.
            return f"Please run this PowerShell script as Administrator:\n{os.path.abspath(script)}"
        
        elif self.system == "Linux":
            return f"Please run: sudo bash {os.path.abspath(script)}"

        return "Installation not supported for this platform automatically."
