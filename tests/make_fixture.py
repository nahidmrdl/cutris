"""Synthetic geometric test fixture, not a replacement for real illustration QA."""
from pathlib import Path
from PIL import Image, ImageDraw

image = Image.new("RGB",(1024,1024),"white")
draw = ImageDraw.Draw(image)
draw.ellipse((190,160,405,390),fill="#235d9d")
draw.ellipse((620,160,835,390),fill="#235d9d")
draw.ellipse((260,450,765,950),fill="#2366a6")
draw.ellipse((200,200,820,760),fill="#2366a6")
draw.ellipse((265,280,755,690),fill="#ffe4ac")
draw.ellipse((310,360,450,505),fill="white")
draw.ellipse((575,360,715,505),fill="white")
draw.ellipse((345,390,425,480),fill="#163d5b")
draw.ellipse((600,390,680,480),fill="#163d5b")
draw.ellipse((350,395,375,420),fill="white")
draw.ellipse((605,395,630,420),fill="white")
draw.ellipse((430,465,595,575),fill="#05c1bf")
draw.arc((370,495,670,650),15,160,fill="#986438",width=12)
directory = Path(__file__).resolve().parent
image.save(directory / "synthetic-character.png")
