from transparent_background import Remover
from PIL import Image
import os

# Paths
DATA_DIR   = "/Users/asif/Documents/Morocco/data"
OUTPUT_DIR = "/Users/asif/Documents/Morocco/outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# filename   = "WhatsApp Image 2025-11-19 at 12.26.00 PM.jpeg"
# # --- CROP SETTINGS ---
# # Adjust these 4 values (0.0 to 1.0) to zero in on the vase you want
# # left, top, right, bottom as fractions of image size
# left   = 0.28  # more space left
# top    = 0.08  # more space top
# right  = 0.92  # more space right
# bottom = 0.97  # get the full base

filename = "WhatsApp Image 2025-11-19 at 12.25.55 PM.jpeg"
img = Image.open(os.path.join(DATA_DIR, filename))

# Add padding around image first so we have room at edges
pad = 200  # pixels of black padding all around
padded = Image.new("RGB", (img.width + pad*2, img.height + pad*2), (0,0,0))
padded.paste(img, (pad, pad))

# Now crop with room to breathe
width, height = padded.size
left   = 0.12
top    = 0.00
right  = 0.86
bottom = 0.99



input_path = os.path.join(DATA_DIR, filename)

remover = Remover()
img = Image.open(input_path)
width, height = img.size


# Apply crop
crop_box = (int(width*left), int(height*top), int(width*right), int(height*bottom))
cropped  = img.crop(crop_box)

# Remove background on the cropped region
output = remover.process(cropped, type='rgba')

# Place on black background
background = Image.new("RGB", output.size, (0, 0, 0))
background.paste(output, mask=output.split()[3])

# Save with crop indicator in filename
output_path = os.path.join(OUTPUT_DIR, f"cropped_{filename.replace(' ', '_')}")
background.save(output_path, quality=97)
print(f"Saved to: {output_path}")
print(f"Crop used: left={left}, top={top}, right={right}, bottom={bottom}")
print(f"Tip: adjust the 4 crop values above and rerun to reframe")