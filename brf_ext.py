from transparent_background import Remover
from PIL import Image
import os

# Paths
DATA_DIR   = "/Users/asif/Documents/Morocco/data"
OUTPUT_DIR = "/Users/asif/Documents/Morocco/outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# filename = "WhatsApp Image 2025-11-19 at 12.25.55 PM.jpeg"
# pad = 100  # increased to 300 to give more top room
# left   = 0.12
# top    = 0.00
# right  = 0.86
# bottom = 0.99
# output = "picasso_vase.jpg"

filename   = "WhatsApp Image 2025-11-19 at 12.26.00 PM.jpeg"
# filename   = "dark_vase.png"
# --- CROP SETTINGS ---
# Adjust these 4 values (0.0 to 1.0) to zero in on the vase you want
# left, top, right, bottom as fractions of image size
pad = 0  # increased to 300 to give more top room
left   = 0.05  # more space left
top    = 0.08  # more space top
right  = 0.92  # more space right
bottom = 0.97  # get the full base
output = "dark_vase.jpg"

# filename   = "WhatsApp Image 2025-08-23 at 9.49.23 AM.jpeg"
# # --- CROP SETTINGS ---
# # Adjust these 4 values (0.0 to 1.0) to zero in on the vase you want
# # left, top, right, bottom as fractions of image size
# pad = 300  # increased to 300 to give more top room
# left   = 0.20
# right  = 0.72
# top    = 0.42
# bottom = 0.97
# output = "terracotta_urn.jpg"

# filename = "WhatsApp Image 2025-11-19 at 12.25.54 PM.jpeg"
# pad    = 300
# left   = 0.25
# top    = 0.00
# right  = 0.75
# bottom = 0.95
# output = "white_urn.jpg"


# filename = "2fd1509c-0c04-4e2f-bc6f-f1f322a4f1ac.jpg"
# pad    = 300
# left   = 0.08
# top    = 0.10
# right  = 0.48
# bottom = 0.92
# output = "berber_vessel.jpg"

# filename = "4545684b-27bc-4480-8936-c1f798faf94e.jpg"
# filename = "terracotta_amphora 1.17.54 PM.png"
# pad    = 300
# left   = 0.02
# top    = 0.00
# right  = 0.52
# bottom = 0.98
# output = "terracotta_amphora.jpg"

# Load image
img = Image.open(os.path.join(DATA_DIR, filename))

# Add black padding so we have breathing room at edges

padded = Image.new("RGB", (img.width + pad*2, img.height + pad*2), (0, 0, 0))
padded.paste(img, (pad, pad))  # paste original INTO padded canvas

# Crop from the PADDED image (not the original!)
width, height = padded.size  # use padded dimensions


crop_box = (int(width*left), int(height*top), int(width*right), int(height*bottom))
cropped  = padded.crop(crop_box)  # crop from padded, not img

# Remove background
remover = Remover()
result = remover.process(cropped, type='rgba')

from PIL import ImageFilter

# Soften the alpha mask edges
r, g, b, a = result.split()
a = a.filter(ImageFilter.GaussianBlur(radius=1.5))
result = Image.merge("RGBA", (r, g, b, a))

# Place on black background
background = Image.new("RGB", (width, height), (255, 255, 255))
background.paste(result, mask=result.split()[3])

# Save

output_path = os.path.join(OUTPUT_DIR, f"{output}")
background.save(output_path, quality=97)
print(f"Saved to: {output_path}")