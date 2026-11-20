import sys,glob,os
from PIL import Image,ImageDraw,ImageFont
pat,out=sys.argv[1],sys.argv[2]; cols=int(sys.argv[3]) if len(sys.argv)>3 else 6
fs=sorted(glob.glob(pat)); W=320
f=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",16)
tiles=[]
for p in fs:
    im=Image.open(p).convert("RGB"); h=int(im.height*W/im.width); im=im.resize((W,h))
    tiles.append((os.path.basename(p),im))
H=max(t[1].height for t in tiles)+20
rows=(len(tiles)+cols-1)//cols
S=Image.new("RGB",(cols*W,rows*H),(30,30,30)); d=ImageDraw.Draw(S)
for i,(n,im) in enumerate(tiles):
    x,y=(i%cols)*W,(i//cols)*H; S.paste(im,(x,y+20)); d.text((x+3,y+1),n[:38],fill=(255,255,0),font=f)
S.save(out,quality=85); print(out,S.size,len(tiles))
