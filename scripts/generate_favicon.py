from PIL import Image

# Percorsi
src = "static/favicon.png"
dst = "static/favicon.ico"

img = Image.open(src)
img.save(dst, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

print("Favicon generata con successo:", dst)
