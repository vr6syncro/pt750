import os
import subprocess
from operator import itemgetter

import treepoem
from PIL import Image, ImageDraw, ImageFont

from pt750.models import HAlignment, settings

_font_cache: dict[str, str] = {}

font_sizes = {"large": 1.0, "medium": 0.75, "small": 0.5}

def refresh_font_cache():
    """Refresh the font cache with system and custom fonts."""
    global _font_cache
    _font_cache.clear()
    
    # Get system fonts via fc-list
    try:
        path_lists = subprocess.check_output(["fc-list", "-f", "%{file}\n"]).decode()
        for line in path_lists.split("\n"):
            line = line.strip()
            if line:
                font = line.split("/")[-1]
                if font.endswith(".ttf") or font.endswith(".otf"):
                    _font_cache[font] = line
    except:
        pass  # fc-list might not be available
    
    # Add custom fonts from settings.font_dirs
    if settings.font_dirs:
        for fd_path in settings.font_dirs:
            if os.path.exists(fd_path):
                for font in os.listdir(fd_path):
                    if font.endswith(".ttf") or font.endswith(".otf"):
                        _font_cache[font] = os.path.join(fd_path, font)


font_map = {
    "mono": "DejaVuSansMono",
    "serif": "DejaVuSerif",
    "sans": "DejaVuSans",
}

font_map.update(settings.font_map)  # type: ignore


def get_available_fonts():
    """Get all available font names including system fonts."""
    # Start with mapped fonts
    available = set(font_map.keys())
    
    # Add all system fonts by triggering font cache refresh
    # Force cache refresh by calling path_for which rebuilds _font_cache
    try:
        path_for("mono")  # This triggers the fc-list call and populates _font_cache
    except:
        pass  # Ignore if mono font not found
    
    # Extract clean font names from cache (filtered for quality)
    for font_file in _font_cache.keys():
        if font_file.endswith('.ttf') or font_file.endswith('.otf'):
            # Remove extension and use as font name
            font_name = font_file[:-4]
            font_path = _font_cache[font_file]
            
            # Always include custom fonts from /app/custom_fonts
            if '/app/custom_fonts/' in font_path:
                available.add(font_name)
            # Include popular system fonts
            elif any(popular in font_name for popular in ['DejaVu', 'Liberation', 'Noto', 'Ubuntu']):
                available.add(font_name)
            # Skip obscure system fonts (URW, Nimbus, etc.) to keep list manageable
    
    return sorted(available)


def getsize(font, text: str):
    left, top, right, bottom = font.getbbox(text)
    return (right, bottom)


def path_for(fontname: str):
    if fontname.startswith("/"):
        return fontname

    fontname = font_map.get(fontname, fontname)

    def refresh_font_cache():
        """Refresh the font cache with system and custom fonts."""
        _font_cache.clear()
        
        # Get system fonts via fc-list
        try:
            path_lists = subprocess.check_output(["fc-list", "-f", "%{file}\n"]).decode()
            for line in path_lists.split("\n"):
                line = line.strip()
                if line:
                    font = line.split("/")[-1]
                    if font.endswith(".ttf") or font.endswith(".otf"):
                        _font_cache[font] = line
        except:
            pass  # fc-list might not be available
        
        # Add custom fonts from settings.font_dirs
        if settings.font_dirs:
            for fd_path in settings.font_dirs:
                if os.path.exists(fd_path):
                    for font in os.listdir(fd_path):
                        if font.endswith(".ttf") or font.endswith(".otf"):
                            _font_cache[font] = os.path.join(fd_path, font)
    
    # Always refresh font cache to pick up new fonts
    if not _font_cache:
        refresh_font_cache()

    path = _font_cache.get(fontname)
    if path is None:
        path = _font_cache.get(f"{fontname}.ttf")
    if path is None:
        path = _font_cache.get(f"{fontname}.otf")
    
    # Try direct TTF/OTF filename if fontname doesn't work
    if path is None:
        for cached_font, cached_path in _font_cache.items():
            if cached_font.startswith(fontname) and (cached_font.endswith('.ttf') or cached_font.endswith('.otf')):
                path = cached_path
                break

    if not path:
        raise RuntimeError(f"Bad font: {fontname}")

    return path


def find_fit(fontname: str, size: float, text: str, constrain_height: bool = True):
    fontsize = 1

    fontname = path_for(fontname)
    if not fontname:
        raise RuntimeError(f"Cannot find font {fontname}")

    font = ImageFont.truetype(fontname, fontsize)

    constraint = itemgetter(1) if constrain_height else itemgetter(0)
    if constrain_height:
        text = "bdfhkltgjpgyfz"

    while constraint(getsize(font, text)) < size:
        fontsize += 1
        font = ImageFont.truetype(fontname, fontsize)

    return fontsize - 1


def qr_code(height: int, text: str):
    img = Image.new("1", size=(height, height), color=1)

    code = treepoem.generate_barcode(barcode_type="qrcode", data=text)

    code_img = code.resize((height, height), resample=Image.Resampling.NEAREST)
    img.paste(code_img)
    return img


def vertical_text_block(width: int, height: int, fontname: str, text: str, min_count=1):
    fontpath = path_for(fontname)
    if not fontpath:
        raise RuntimeError("Cannot find font")

    # width here is "width of text", i.e. height

    # constrain width
    fs_width = find_fit(fontpath, width, text, constrain_height=False)
    fs_height = find_fit(fontpath, height / min_count, text)

    fs = min(fs_width, fs_height)

    font = ImageFont.truetype(fontpath, fs)
    img = Image.new("1", size=(width, height), color=1)
    draw = ImageDraw.Draw(img)

    line_height = getsize(font, text)[1]

    line_count = height // line_height

    for idx in range(line_count):
        draw.text((0, idx * line_height), text, font=font)

    img = img.transpose(Image.Transpose.ROTATE_270)
    return img


def horiz_text_block(
    height: int,
    fontname: str,
    fontsize: str,
    lines: list[str],
    alignment: HAlignment = HAlignment.left,
):

    fontpath = path_for(fontname)
    if not fontpath:
        raise RuntimeError(f"Cannot find font {fontname}")

    rows = len(lines)
    height_per_row = height / rows

    font_height = height_per_row * font_sizes[fontsize]

    # now, choose a font!
    fs = find_fit(fontpath, font_height, "".join(lines))

    line_ofs = (height_per_row - font_height) // 2
    font = ImageFont.truetype(fontpath, fs)

    # find max width
    width = 0
    for line in lines:
        width = max(width, getsize(font, line)[0])

    img = Image.new(mode="1", size=(width, height), color=1)

    draw = ImageDraw.Draw(img)

    for idx, line in enumerate(lines):
        line_width = getsize(font, line)[0]

        if alignment == HAlignment.left:
            xofs = 0
        elif alignment == HAlignment.center:
            xofs = (width - line_width) / 2
        else:
            xofs = width - line_width

        draw.text((xofs, (idx * height_per_row) + line_ofs), line, font=font)

    return img
