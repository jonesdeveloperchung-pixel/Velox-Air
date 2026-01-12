from PIL import Image, ImageDraw, ImageFont
import os

def create_air_icon():
    # Create a base image with a cyan gradient/circle
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a rounded cyan background
    margin = 20
    draw.rounded_rectangle([margin, margin, size-margin, size-margin], radius=60, fill=(6, 182, 212, 255))
    
    # Draw the diamond emoji or similar shape
    # Using a simple polygon to represent the 💠 icon if font is missing
    center = size // 2
    points = [
        (center, margin + 40), # Top
        (size - margin - 40, center), # Right
        (center, size - margin - 40), # Bottom
        (margin + 40, center)  # Left
    ]
    draw.polygon(points, fill=(255, 255, 255, 255))
    
    # Inner small diamond
    inner_margin = 85
    draw.polygon([
        (center, inner_margin), 
        (size - inner_margin, center), 
        (center, size - inner_margin), 
        (inner_margin, center)
    ], fill=(6, 182, 212, 255))

    # Save as ICO
    icon_path = os.path.join(os.path.dirname(__file__), "air_icon.ico")
    img.save(icon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon created at: {icon_path}")

if __name__ == "__main__":
    create_air_icon()
