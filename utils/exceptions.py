class VeloxWarpError(Exception):
    """Base exception for Velox Warp application errors."""
    pass

class NetworkError(VeloxWarpError):
    """Exception for network-related errors."""
    pass

class CaptureError(VeloxWarpError):
    """Exception for screen capture errors."""
    pass

class EncodingError(VeloxWarpError):
    """Exception for frame encoding errors."""
    pass

class DecodingError(VeloxWarpError):
    """Exception for frame decoding errors."""
    pass

class ProtocolError(VeloxWarpError):
    """Exception for protocol-related errors (e.g., version mismatch, malformed messages)."""
    pass
