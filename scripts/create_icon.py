"""Generate the MaazX Windows application icon."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "maazxdroid.ico"


def main():
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    background = (17, 24, 23, 255)
    accent = (212, 107, 255, 255)
    image = Image.new("RGBA", (size, size), background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, 246, 246), radius=48, fill=(27, 37, 34, 255))
    draw.rounded_rectangle((10, 10, 246, 246), radius=48, outline=(65, 83, 68, 255), width=4)
    draw.line((76, 72, 180, 184), fill=accent, width=26)
    draw.line((180, 72, 76, 184), fill=accent, width=26)
    image.save(ICON_PATH, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print(f"Created {ICON_PATH}")


if __name__ == "__main__":
    main()