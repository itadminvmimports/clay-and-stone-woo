from PIL import Image, ImageOps
import os

input_dir = "/Users/asif/Documents/Morocco/code/static/images"
files = ["terracotta_urn.jpg", "terracotta_amphora.jpg", "picasso_vase.jpg", "dark_vase.jpg", "berber_vessel.jpg", "white_urn.jpg"]

for filename in files:
    path = os.path.join(input_dir, filename)
    if not os.path.exists(path):
        print(f"Skipping {filename} - not found")
        continue
    
    img = Image.open(path).convert("RGBA")
    
    # Get bounding box of non-white pixels
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    diff = Image.new("RGBA", img.size)
    
    # Find non-white pixels (with some tolerance)
    import numpy as np
    arr = np.array(img.convert("RGB"))
    # Pixels that are NOT close to white (255,255,255)
    mask = ~((arr[:,:,0] > 230) & (arr[:,:,1] > 230) & (arr[:,:,2] > 230))
    
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    # Add padding
    pad = 40
    rmin = max(0, rmin - pad)
    rmax = min(img.height, rmax + pad)
    cmin = max(0, cmin - pad)
    cmax = min(img.width, cmax + pad)
    
    cropped = img.crop((cmin, rmin, cmax, rmax))
    
    # Save back as RGB
    cropped_rgb = Image.new("RGB", cropped.size, (255, 255, 255))
    if cropped.mode == "RGBA":
        cropped_rgb.paste(cropped, mask=cropped.split()[3])
    else:
        cropped_rgb = cropped.convert("RGB")
    
    cropped_rgb.save(path)
    print(f"Cropped {filename}: {img.size} → {cropped.size}")

print("Done")