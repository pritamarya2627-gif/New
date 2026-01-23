import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL

def truncate(text, max_len=30):
    """Splits text into two lines if it's too long."""
    words = text.split()
    lines = ["", ""]
    i = 0
    for word in words:
        if len(lines[i]) + len(word) + 1 <= max_len:
            lines[i] += (" " if lines[i] else "") + word
        elif i == 0:
            i = 1
    return lines

def add_corners(im, rad):
    """Adds rounded corners to an image."""
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

def draw_text_with_shadow(draw, pos, text, font, fill="white", shadow_color="black"):
    """Draws text with a drop shadow for better visibility."""
    x, y = pos
    # Draw shadow
    draw.text((x + 3, y + 3), text, font=font, fill=shadow_color)
    # Draw main text
    draw.text(pos, text, font=font, fill=fill)

async def gen_thumb(videoid: str, thumb_size=(1280, 720)):
    path = f"cache/{videoid}.png"
    if os.path.isfile(path):
        return path
    try:
        # --- 1. Fetch Video Data ---
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1, with_live=False)
        data = (await results.next())["result"][0]

        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        duration = data.get("duration") or "00:00"
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        channel = data.get("channel", {}).get("name", "Unknown Channel")
        thumb_url = data["thumbnails"][0]["url"].split("?")[0]

        # --- 2. Download Thumbnail ---
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                content = await resp.read()

        temp_path = f"cache/thumb_{videoid}.png"
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)

        # --- 3. Process Images ---
        base_img = Image.open(temp_path).convert("RGBA")

        # A. Create Background (Light Blur Song Image)
        # Resize to fill HD canvas
        bg = base_img.resize(thumb_size, Image.Resampling.LANCZOS)

        # Apply Light Blur (Radius 10-15 gives a frosted look, 50 is too smooth)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=15)) 

        # Darken slightly so white text pops (0.6 means 60% brightness)
        bg = ImageEnhance.Brightness(bg).enhance(0.6)

        # B. Prepare Main Album Art (Smaller Square)
        # Your reference shows the art is smaller relative to the canvas
        art_size = 380 
        art = base_img.convert("RGBA")
        art = ImageOps.fit(art, (art_size, art_size), centering=(0.5, 0.5))
        art = add_corners(art, 30) # Rounded corners

        # Create a Shadow/Glow behind the art
        shadow_size = art_size + 30
        shadow = Image.new("RGBA", (shadow_size, shadow_size), (0, 0, 0, 0))
        draw_shadow = ImageDraw.Draw(shadow)
        draw_shadow.rounded_rectangle((0, 0, shadow_size, shadow_size), radius=30, fill=(0, 0, 0, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))

        # Position Art on the Left
        art_x, art_y = 120, 170
        bg.paste(shadow, (art_x - 15, art_y - 15), shadow)
        bg.paste(art, (art_x, art_y), art)

        # --- 4. Draw Text ---
        draw = ImageDraw.Draw(bg)

        # Fonts
        # font3 is usually Bold/Header, font2 is usually Regular/Info
        font_header = ImageFont.truetype("AviaxMusic/assets/font3.ttf", 90) # Big "NOW PLAYING"
        font_title = ImageFont.truetype("AviaxMusic/assets/font3.ttf", 50)  
        font_info = ImageFont.truetype("AviaxMusic/assets/font2.ttf", 35)   
        font_footer = ImageFont.truetype("AviaxMusic/assets/font2.ttf", 25)

        text_x = 580 # Start text to the right of the image

        # A. Header "NOW PLAYING"
        draw_text_with_shadow(draw, (text_x, 140), "NOW PLAYING", font_header, fill="white")

        # B. Title
        # Add a little spacing after header
        title_y = 250
        t1, t2 = truncate(title, max_len=20) # Truncate tighter for big font
        draw_text_with_shadow(draw, (text_x, title_y), t1, font_title, fill="white")
        if t2:
             draw_text_with_shadow(draw, (text_x, title_y + 60), t2, font_title, fill="white")

        # C. Metadata
        # Adjust Y based on if title is 1 or 2 lines
        info_start_y = 380 if t2 else 320
        line_height = 45

        draw_text_with_shadow(draw, (text_x, info_start_y), f"Views : {views} views", font_info)
        draw_text_with_shadow(draw, (text_x, info_start_y + line_height), f"Duration : {duration} Mins", font_info)
        draw_text_with_shadow(draw, (text_x, info_start_y + (line_height * 2)), f"Channel : {channel}", font_info)

        # D. Footer (TgMusicBots)
        footer_text = "TgMusicBots"
        bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
        footer_w = bbox[2] - bbox[0]
        draw_text_with_shadow(draw, (1280 - footer_w - 40, 680), footer_text, font_footer)

        # --- 5. Save ---
        bg.save(path)
        os.remove(temp_path)
        return path

    except Exception as ex:
        print(f"Error generating thumbnail: {ex}")
        return YOUTUBE_IMG_URL