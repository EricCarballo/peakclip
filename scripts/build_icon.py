"""Convert the supplied artwork to a multi-resolution Windows icon."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parent
assets = root / 'assets'
assets.mkdir(exist_ok=True)
with Image.open(r'C:\Users\shask\Downloads\herramientaicon.jpg') as source:
    artwork = source.convert('RGB')
    artwork.save(assets / 'peak-clip.ico', format='ICO', sizes=[(s,s) for s in (16,24,32,48,64,128,256)])
    artwork.resize((128,128),Image.Resampling.LANCZOS).save(assets / 'peak-clip.png')
