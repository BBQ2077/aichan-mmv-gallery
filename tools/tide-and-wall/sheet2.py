import sys,glob,os
from PIL import Image,ImageDraw,ImageFont
fs=sorted(glob.glob(sys.argv[1])); out=sys.argv[2]; cols=int(sys.argv[3]); a=int(sys.argv[4]); b=int(sys.argv[5])
fs=fs[a:b]; T=300
f=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",17)
rows=(len(fs)+cols-1)//cols
S=Image.new("RGB",(cols*T,rows*(T+20)),(60,60,60)); d=ImageDraw.Draw(S)
for i,p in enumerate(fs):
    im=Image.open(p).convert("RGBA"); im.thumbnail((T,T)); bg=Image.new("RGB",(T,T),(60,60,60)); bg.paste(im,((T-im.width)//2,(T-im.height)//2),im)
    x,y=(i%cols)*T,(i//cols)*(T+20); S.paste(bg,(x,y+20)); d.text((x+3,y+1),os.path.basename(p)[:-4],fill=(255,255,0),font=f)
S.save(out,quality=82); print(out,S.size)
