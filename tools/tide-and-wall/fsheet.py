import glob,sys
from PIL import Image,ImageDraw,ImageFont
fs=sorted(glob.glob("C:/Users/user/hermes-files/ai-war-mmv/60_cut/frames2/*.jpg"))
f=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",22)
per=30
for k in range(0,len(fs),per):
    S=Image.new("RGB",(5*480,6*270)); d=ImageDraw.Draw(S)
    for i,p in enumerate(fs[k:k+per]):
        x,y=(i%5)*480,(i//5)*270; S.paste(Image.open(p).resize((480,270)),(x,y))
        d.text((x+4,y+2),p.split("f_")[-1][:-4],fill=(255,255,0),font=f,stroke_width=2,stroke_fill=(0,0,0))
    S.save(f"C:/Users/user/hermes-files/ai-war-mmv/60_cut/review2/s{k//per}.jpg",quality=80)
print(len(fs))
