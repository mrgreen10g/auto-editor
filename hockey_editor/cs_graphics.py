"""Cyberpunk surfaces, retaining existing component dimensions and positions."""
from PIL import Image,ImageDraw

def backdrop(d,w,h):
 d.rectangle((0,0,w,h),fill='#100f25')
 for x in range(0,w,48):d.line((x,0,x,h),fill='#192139')
 for y in range(0,h,48):d.line((0,y,w,y),fill='#192139')
 d.polygon([(w*.72,0),(w*.91,0),(w*.55,h),(w*.36,h)],fill='#211438')
 d.line((w*.92,0,w*.56,h),fill='#f134ad',width=4)
 d.line((w*.96,0,w*.60,h),fill='#38e6ef',width=2)

def panel(width,height):
 im=Image.new('RGBA',(width+24,height+24));d=ImageDraw.Draw(im)
 points=[(12,28),(28,12),(width+12,12),(width+12,height-4),(width-4,height+12),(12,height+12)]
 d.polygon(points,fill=(16,15,37,248));d.line(points+[points[0]],fill='#38e6ef',width=2)
 d.line((width*.73,15,width*.85,15),fill='#f134ad',width=4)
 d.line((16,height+8,70,height+8),fill='#f6df59',width=3)
 return im
