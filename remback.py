import torch
import numpy as np
from PIL import Image, ImageFilter
from segment_anything import sam_model_registry, SamPredictor
import os
import cv2

# Paths
DATA_DIR   = "/Users/asif/Documents/Morocco/data"
OUTPUT_DIR = "/Users/asif/Documents/Morocco/outputs"
MODEL_PATH = "/Users/asif/Documents/Morocco/models/sam_vit_h_4b8939.pth"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading SAM model...")
sam = sam_model_registry["vit_h"](checkpoint=MODEL_PATH)
sam.to(device="cpu")
predictor = SamPredictor(sam)
print("Model loaded.")

def smooth_mask(alpha_array, blur_radius=3, morph_size=2):
    # Skip morphology entirely — just feather the edge
    # Step 1: Gentle blur to anti-alias
    blurred = cv2.GaussianBlur(alpha_array, (21, 21), 0)
    
    # Step 2: Blend original sharp mask with blurred version
    # This keeps the shape accurate but softens the pixel edge
    feathered = cv2.addWeighted(alpha_array, 0.7, blurred, 0.3, 0)
    
    return feathered

def process_image(filename, bg_color=(0, 0, 0)):
    input_path  = os.path.join(DATA_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"clean_{filename}")

    print(f"\nProcessing: {filename}")

    pil_img   = Image.open(input_path).convert("RGB")
    img_array = np.array(pil_img)
    height, width = img_array.shape[:2]

    # Tell SAM to use full resolution
    sam.image_encoder.img_size = 1024
    predictor.set_image(img_array)

    center_x = width  // 2
    center_y = height // 2

    input_point = np.array([[center_x, center_y]])
    input_label = np.array([1])

    print(f"Segmenting at ({center_x}, {center_y})...")
    masks, scores, _ = predictor.predict(
        point_coords=input_point,
        point_labels=input_label,
        multimask_output=True,
    )

    best_mask = masks[np.argmax(scores)]
    raw_alpha = (best_mask * 255).astype(np.uint8)

    # Smooth the jagged edges
    print("Smoothing edges...")
    smooth_alpha = smooth_mask(raw_alpha, blur_radius=2, morph_size=2)

    alpha_img  = Image.fromarray(smooth_alpha)
    background = Image.new("RGB", pil_img.size, bg_color)
    background.paste(pil_img, mask=alpha_img)

    # Tight crop
    row_idx = np.where(np.any(smooth_alpha > 128, axis=1))[0]
    col_idx = np.where(np.any(smooth_alpha > 128, axis=0))[0]
    pad    = 60
    top    = max(row_idx[0] - pad, 0)
    bottom = min(row_idx[-1] + pad, height)
    left   = max(col_idx[0] - pad, 0)
    right  = min(col_idx[-1] + pad, width)
    cropped = background.crop((left, top, right, bottom))

    final = Image.new("RGB", (cropped.width + 80, cropped.height + 80), bg_color)
    final.paste(cropped, (40, 40))
    final.save(output_path, quality=97)
    print(f"Saved to: {output_path}")


# --- Run ---
process_image("WhatsApp Image 2025-11-19 at 12.25.55 PM.jpeg")

# Batch:
# for f in os.listdir(DATA_DIR):
#     if f.lower().endswith((".jpg",".jpeg",".png",".webp")):
#         process_image(f)