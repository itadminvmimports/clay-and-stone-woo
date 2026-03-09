# Re-extract the vase with background removal using OpenCV's GrabCut
import cv2
import numpy as np
from PIL import Image
import os

DATA_DIR   = "/Users/asif/Documents/Morocco/data"
OUTPUT_DIR = "/Users/asif/Documents/Morocco/outputs"
MODEL_PATH = "/Users/asif/Documents/Morocco/models/sam_vit_h_4b8939.pth"

os.makedirs(OUTPUT_DIR, exist_ok=True)

filename= "WhatsApp Image 2025-11-19 at 12.25.55 PM.jpeg"
input_path  = os.path.join(DATA_DIR, filename)
output_path = os.path.join(OUTPUT_DIR, f"cv2_{filename}")
img = cv2.imread(input_path)

# Create initial mask
mask = np.zeros(img.shape[:2], np.uint8)

# Define rectangle roughly around the vase (center area)
h, w = img.shape[:2]
rect = (int(w*0.25), int(h*0.05), int(w*0.5), int(h*0.9))

bgdModel = np.zeros((1,65), np.float64)
fgdModel = np.zeros((1,65), np.float64)

cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)

# Convert mask to binary alpha
mask2 = np.where((mask==2)|(mask==0),0,1).astype('uint8')
result = img * mask2[:,:,np.newaxis]

# Convert to RGBA
rgba = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
rgba[:,:,3] = mask2*255


Image.fromarray(rgba).save(output_path)

output_path