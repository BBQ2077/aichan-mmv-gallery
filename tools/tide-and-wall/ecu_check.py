import sys; sys.path.insert(0, "C:/Users/user/hermes-files/ai-war-mmv/60_cut")
from PIL import Image, ImageDraw, ImageFont
import edl2
W,H=384,216
f=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",16)
items=[(k,n,v) for k,D in (("eye",edl2.EYE),("hand",edl2.HAND)) for n,v in D.items()]
cols=6; rows=(len(items)+cols-1)//cols
S=Image.new("RGB",(cols*W,rows*H),(90,90,90)); d=ImageDraw.Draw(S)
for i,(k,n,(x,y,z)) in enumerate(items):
    im=Image.open(f"C:/Users/user/hermes-files/ai-war-mmv/60_cut/cut/{n}.png").convert("RGBA")
    bg=Image.new("RGBA",im.size,(90,90,90,255)); im=Image.alpha_composite(bg,im).convert("RGB")
    s=z*W/im.width; w,h=W/s,H/s; l=x*im.width-w/2; t=y*im.height-h/2
    tile=im.crop((int(l),int(t),int(l+w),int(t+h))).resize((W,H),Image.BICUBIC)
    X,Y=(i%cols)*W,(i//cols)*H; S.paste(tile,(X,Y)); d.text((X+3,Y+2),f"{k} {n}",fill=(255,255,0),font=f,stroke_width=2,stroke_fill=(0,0,0))
S.save("C:/Users/user/hermes-files/ai-war-mmv/60_cut/review2/ecu.jpg",quality=85); print(S.size,len(items))
