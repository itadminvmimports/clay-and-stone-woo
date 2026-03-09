from PIL import Image
img = Image.open('/Users/asif/Documents/Morocco/code/static/images/terracotta_urn.jpg')
# Crop to just the top 55% where the urn actually is
w, h = img.size
cropped = img.crop((0, 0, w, int(h * 0.55)))
cropped.save('/Users/asif/Documents/Morocco/code/static/images/terracotta_urn.jpg', quality=97)
print(f'Done: {cropped.size}')