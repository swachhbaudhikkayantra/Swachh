import sys, glob, os
from PIL import Image, ImageDraw
# grid.py indir outprefix cols per_sheet thumb_w
d, out, cols, per, tw = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
files = sorted(glob.glob(os.path.join(d, 'slide-*.png')))
for k in range(0, len(files), per):
    chunk = files[k:k+per]; ims = [Image.open(f).convert('RGB') for f in chunk]
    th = int(tw * ims[0].height / ims[0].width)
    rows = (len(ims)+cols-1)//cols
    sheet = Image.new('RGB', (cols*(tw+8)+8, rows*(th+28)+8), 'white'); dr = ImageDraw.Draw(sheet)
    for i,(f,im) in enumerate(zip(chunk,ims)):
        x = 8 + (i%cols)*(tw+8); y = 8 + (i//cols)*(th+28)
        sheet.paste(im.resize((tw,th)), (x, y+20)); dr.text((x, y+4), os.path.basename(f), fill='black')
    p = f"{out}-{k//per+1}.jpg"; sheet.save(p, quality=85); print(p)
