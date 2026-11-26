"""Build assets/icon.ico (all Windows sizes) and assets/icon.svg. Dev tool only: needs Pillow, the app does not."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets"
RAINBOW = [(255, 79, 163), (255, 138, 61), (255, 210, 63), (79, 214, 122), (63, 182, 255), (143, 107, 255)]
DOTS = [(255, 79, 163), (255, 160, 40), (40, 160, 255)]
S = 1024  # draw big, downscale with LANCZOS


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    n = len(RAINBOW) - 1
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1)) * n
            i = min(int(t), n - 1)
            px[x, y] = lerp(RAINBOW[i], RAINBOW[i + 1], t - i)
    return img


def star(cx, cy, r, inner):
    import math
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else inner
        a = math.pi / 4 * k - math.pi / 2
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def draw():
    u = S / 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([8 * u, 8 * u, 248 * u, 248 * u], radius=58 * u, fill=255)
    img.paste(gradient(S), (0, 0), mask)
    d = ImageDraw.Draw(img)
    # soft gloss on the top half
    gloss = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gloss).rounded_rectangle([8 * u, 8 * u, 248 * u, 128 * u], radius=58 * u, fill=34)
    img.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), Image.composite(gloss, Image.new("L", (S, S), 0), mask))
    # chat bubble with tail
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([44 * u, 70 * u, 212 * u, 184 * u], radius=30 * u, fill=(60, 20, 90, 60))
    sd.polygon([(84 * u, 178 * u), (84 * u, 218 * u), (126 * u, 178 * u)], fill=(60, 20, 90, 60))
    img.alpha_composite(shadow, (0, int(5 * u)))
    d.rounded_rectangle([44 * u, 66 * u, 212 * u, 180 * u], radius=30 * u, fill="white")
    d.polygon([(84 * u, 172 * u), (84 * u, 212 * u), (128 * u, 172 * u)], fill="white")
    for i, c in enumerate(DOTS):
        cx = (92 + 36 * i) * u
        d.ellipse([cx - 15 * u, 123 * u - 15 * u, cx + 15 * u, 123 * u + 15 * u], fill=c)
    # sparkle
    d.polygon(star(206 * u, 56 * u, 30 * u, 8 * u), fill="white")
    d.polygon(star(206 * u, 56 * u, 30 * u, 8 * u), outline=(255, 255, 255))
    return img


def main():
    OUT.mkdir(exist_ok=True)
    big = draw()
    # every size Windows asks for at 100/125/150/200% scaling, so it never has to stretch one (that is what blurs)
    sizes = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256]
    imgs = [big.resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[-1].save(OUT / "icon.ico", sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon-256.png")
    big.resize((512, 512), Image.LANCZOS).save(OUT / "icon-512.png")
    stops = "".join(f"<stop offset='{i / 5:.2f}' stop-color='rgb{c}'/>" for i, c in enumerate(RAINBOW))
    dots = "".join(f"<circle cx='{92 + 36 * i}' cy='123' r='15' fill='rgb{c}'/>" for i, c in enumerate(DOTS))
    pts = " ".join(f"{x / (S / 256):.1f},{y / (S / 256):.1f}" for x, y in star(206 * S / 256, 56 * S / 256, 30 * S / 256, 8 * S / 256))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256'>"
           f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>{stops}</linearGradient></defs>"
           "<rect x='8' y='8' width='240' height='240' rx='58' fill='url(#g)'/>"
           "<rect x='44' y='71' width='168' height='114' rx='30' fill='rgb(60,20,90)' opacity='.24'/>"
           "<rect x='44' y='66' width='168' height='114' rx='30' fill='#fff'/>"
           "<path d='M84 172 V212 L128 172 Z' fill='#fff'/>"
           f"{dots}<polygon points='{pts}' fill='#fff'/></svg>\n")
    (OUT / "icon.svg").write_text(svg, encoding="utf-8")
    print("ok:", ", ".join(p.name for p in sorted(OUT.iterdir())))


if __name__ == "__main__":
    main()
