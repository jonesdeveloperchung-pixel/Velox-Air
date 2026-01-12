from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Union, Optional
from PIL import Image
import numpy as np

class Streamable(ABC):
    """An interface for streamable data types."""

    @abstractmethod
    def get_data(self) -> Any:
        """Get the data to be streamed."""
        pass

class Tile:
    """Represents a small rectangular region of the screen.
    Contains its coordinates, dimensions, and image data.
    """
    def __init__(self, x: int, y: int, width: int, height: int, image_data: Optional[Image.Image] = None, np_data: Optional[np.ndarray] = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._image_data = image_data
        self._np_data = np_data
        
        if self._image_data is None and self._np_data is None:
             raise ValueError("Tile must be initialized with either image_data or np_data")

    @property
    def image_data(self) -> Image.Image:
        """Returns the PIL Image representation of the tile."""
        if self._image_data is None:
            self._image_data = Image.fromarray(self._np_data)
        return self._image_data
        
    @property
    def np_data(self) -> np.ndarray:
        """Returns the NumPy array representation of the tile."""
        if self._np_data is None:
            self._np_data = np.array(self._image_data)
        return self._np_data

    def get_hash(self) -> int:
        """Calculates a simple hash for the tile's image data.
        A more robust hashing algorithm might be needed for production.
        """
        # Hash the bytes of the numpy array for speed if available
        if self._np_data is not None:
             return hash(self._np_data.tobytes())
        return hash(self._image_data.tobytes())

class ScreenFrame(Streamable):
    """A class to represent a screen frame.
    Can provide access to its image data and extract tiles.
    """
    def __init__(self, frame_data: Union[Image.Image, np.ndarray]):
        self._frame_image: Optional[Image.Image] = None
        self._np_array: Optional[np.ndarray] = None
        
        if isinstance(frame_data, np.ndarray):
            self._np_array = frame_data
            # Shape is (height, width, channels)
            self.height, self.width = frame_data.shape[:2]
        else:
            self._frame_image = frame_data
            self.width = frame_data.width
            self.height = frame_data.height

    def get_data(self) -> Image.Image: # Return PIL.Image
        if self._frame_image is None:
            self._frame_image = Image.fromarray(self._np_array)
        return self._frame_image

    def get_pil_image(self) -> Image.Image:
        """Returns the PIL Image representation of the frame."""
        return self.get_data()

    def get_np_array(self) -> np.ndarray:
        """Returns the frame as a NumPy array (RGB)."""
        if self._np_array is None:
            self._np_array = np.array(self._frame_image)
        return self._np_array

    def get_tile(self, x: int, y: int, width: int, height: int) -> Tile:
        """Extracts a tile from the screen frame.
        Uses NumPy slicing if available for performance.
        """
        if self._np_array is not None:
             # Fast numpy slicing
             tile_np = self._np_array[y:y+height, x:x+width]
             return Tile(x, y, width, height, np_data=tile_np)
        else:
            # Legacy PIL cropping
            cropped_image = self._frame_image.crop((x, y, x + width, y + height))
            return Tile(x, y, width, height, image_data=cropped_image)

class DeltaFrame(Streamable):
    """Represents a frame containing only changed tiles.
    """
    def __init__(self, frame_number: int, changed_tiles: List[Tile], full_frame_fallback: bool = False):
        self.frame_number = frame_number
        self.changed_tiles = changed_tiles
        self.full_frame_fallback = full_frame_fallback

    def get_data(self) -> Any:
        # For DeltaFrame, the 'data' is the list of changed tiles itself
        return self.changed_tiles

    def is_full_frame_fallback(self) -> bool:
        return self.full_frame_fallback
