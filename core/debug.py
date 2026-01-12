import logging

class Debug:
    """A class for handling debugging functionalities using Python's standard logging."""

    def __init__(self, log_level: str = "INFO"):
        # Configure basic logging if not already configured
        if not logging.root.handlers:
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        self._log_level = log_level
        self._logger = logging.getLogger("Velox Warp") # Root logger for general messages

    def _get_logger(self, name: str):
        """Returns a logger for a specific module/component."""
        return logging.getLogger(name)

    def debug(self, name: str, message: str, exc_info=False):
        """Logs a debug message."""
        self._get_logger(name).debug(message, exc_info=exc_info)

    def info(self, name: str, message: str, exc_info=False):
        """Logs an info message."""
        self._get_logger(name).info(message, exc_info=exc_info)

    def warning(self, name: str, message: str, exc_info=False):
        """Logs a warning message."""
        self._get_logger(name).warning(message, exc_info=exc_info)

    def warn(self, name: str, message: str, exc_info=False):
        """Alias for warning() for backward compatibility."""
        self.warning(name, message, exc_info=exc_info)

    def error(self, name: str, message: str, exc_info=False):
        """Logs an error message."""
        self._get_logger(name).error(message, exc_info=exc_info)

    def critical(self, name: str, message: str, exc_info=False):
        """Logs a critical message."""
        self._get_logger(name).critical(message, exc_info=exc_info)

    def add_file_handler(self, file_path: str):
        """Adds a file handler to the root logger for persistent logging."""
        file_handler = logging.FileHandler(file_path)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    # Keep the original log method for backward compatibility, mapping to debug
    def log(self, name: str, message: str, exc_info=False):
        """Logs a debug message (for backward compatibility)."""
        self._get_logger(name).debug(message, exc_info=exc_info)