#!/usr/bin/env python3
"""아이콘에서 대표 색과 그 색이 차지하는 비중을 뽑는다.

아이작 스프라이트는 검은 외곽선이 두꺼워서 픽셀 평균을 그냥 내면 죄다 탁한 색이 된다
(슬픈 양파의 단순 평균은 RGB(71,86,65) 로 초록이라기엔 너무 어둡다).
그래서 외곽선을 걷어낸 뒤, 남은 픽셀을 색깔 묶음별로 나눠 **면적이 가장 넓은 묶음**을
대표색으로 삼는다.

'가장 진한 색'이 아니라 '가장 넓은 색'을 고르는 게 핵심이다. 진하기로 고르면
새하얀 이혼 서류가 도장 몇 점 때문에 빨강이 된다. 넓이로 고르면 그런 일이 없다.

같이 내주는 weight 는 그 색이 아이콘을 얼마나 채우고 있는지를 0~1 로 적은 값이다.
화면에서는 이 값이 큰 것부터 늘어놓아, 묶음 앞쪽에 진짜 그 색인 아이콘이 오게 한다.

단독 실행하면 몇 개를 시험 분류해 보여준다:
    python3 tools/extract_colors.py
"""
import colorsys
import json
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent

ALPHA_MIN = 128      # 반투명 가장자리는 셈에서 뺀다
OUTLINE_V = 0.18     # 이보다 어두우면 외곽선/그림자로 본다
COLOR_S = 0.25       # 이보다 흐린 픽셀은 '색이 있다'고 세지 않는다
COLOR_V = 0.25       # 이보다 어두운 픽셀도 마찬가지
MIN_SHARE = 0.18     # 아이콘의 이만큼은 덮어야 그 색으로 본다. 아니면 무채색
BROWN_V = 0.50       # 따뜻한 색이 이보다 어두우면 갈색으로 본다
RED_BROWN_V = 0.60   # 어둡고 탁한 빨강도 갈색으로 본다 (간, 녹슨 열쇠, 나무 자루)
RED_BROWN_S = 0.70
SKIN_S = 0.45        # 따뜻한 색이 이보다 흐리고 밝으면 살구색으로 본다
SKIN_V = 0.55
WHITE_V = 0.62       # 무채색 중 이보다 밝으면 흰색
BLACK_V = 0.32       # 무채색 중 이보다 어두우면 검정

# 화면 표시 순서대로. (키, 한글 이름, 이모지)
BUCKETS = [
    ("red", "빨강", "🔴"),
    ("orange", "주황", "🟠"),
    ("yellow", "노랑", "🟡"),
    ("green", "초록", "🟢"),
    ("blue", "파랑", "🔵"),
    ("purple", "보라", "🟣"),
    ("pink", "분홍", "🩷"),
    ("skin", "살구", "🫖"),
    ("brown", "갈색", "🟤"),
    ("white", "흰색", "⚪"),
    ("gray", "회색", "🔘"),
    ("black", "검정", "⚫"),
]

# 색이 없는 묶음. 이쪽은 비중 대신 밝기로 줄을 세운다.
ACHROMATIC = ("white", "gray", "black")

# (시작각, 끝각, 버킷). 빨강은 0도를 걸치므로 두 조각으로 적는다.
HUE_RANGES = [
    (0, 15, "red"),
    (15, 40, "orange"),
    (40, 65, "yellow"),
    (65, 160, "green"),
    (160, 250, "blue"),
    (250, 290, "purple"),
    (290, 345, "pink"),
    (345, 360, "red"),
]


def hue_to_bucket(hue):
    for lo, hi, name in HUE_RANGES:
        if lo <= hue < hi:
            return name
    return "red"


def sample_pixels(path, floor=OUTLINE_V):
    """아이콘에서 외곽선을 뺀 (r, g, b, h, s, v) 목록을 만든다."""
    with Image.open(path) as img:
        pixels = list(img.convert("RGBA").getdata())
    kept = []
    for r, g, b, a in pixels:
        if a < ALPHA_MIN:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v < floor:
            continue
        kept.append((r, g, b, h * 360, s, v))
    return kept


def lab(hex_color):
    """헥스를 CIELAB 로 옮긴다. 두 색이 눈에 얼마나 달라 보이는지 재려면 이 자리가 낫다.

    RGB 에서 그냥 거리를 재면 초록만 과하게 멀어진다. 도감을 색 흐름대로
    줄 세울 때 이웃끼리 어색해 보이는 게 그 탓이다.
    """
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    r, g, b = lin
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.9505
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.089
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def gap(one, other):
    """두 CIELAB 색이 눈에 얼마나 달라 보이는지 (CIEDE2000).

    그냥 유클리드 거리(CIE76)로 재면 파랑과 진한 색에서 사람 눈과 어긋난다.
    실제로 도감을 이 척도로 바꾸자 파랑 묶음 한복판의 큰 걸음이 사라졌다.
    식이 길지만 표준이 그렇게 생겼다 — Sharma 검증표 16쌍으로 맞춰 두었다.
    """
    l1, a1, b1 = one
    l2, a2, b2 = other
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    cbar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7))) if cbar else 0.5
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    else:
        diff = h2p - h1p
        if diff > 180: diff -= 360
        elif diff < -180: diff += 360
        dhp = diff
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)

    lbar = (l1 + l2) / 2
    cbarp = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbarp = h1p + h2p
    else:
        diff = abs(h1p - h2p)
        total = h1p + h2p
        if diff <= 180: hbarp = total / 2
        elif total < 360: hbarp = (total + 360) / 2
        else: hbarp = (total - 360) / 2

    t = (1 - 0.17 * math.cos(math.radians(hbarp - 30))
         + 0.24 * math.cos(math.radians(2 * hbarp))
         + 0.32 * math.cos(math.radians(3 * hbarp + 6))
         - 0.20 * math.cos(math.radians(4 * hbarp - 63)))
    dtheta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cbarp ** 7 / (cbarp ** 7 + 25 ** 7)) if cbarp else 0.0
    sl = 1 + (0.015 * (lbar - 50) ** 2) / math.sqrt(20 + (lbar - 50) ** 2)
    sc = 1 + 0.045 * cbarp
    sh = 1 + 0.015 * cbarp * t
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dHp / sh) ** 2
                     + rt * (dcp / sc) * (dHp / sh))


def achromatic_bucket(value):
    """색이 없는 아이콘을 밝기로 흰색/회색/검정으로 나눈다."""
    if value >= WHITE_V:
        return "white"
    if value <= BLACK_V:
        return "black"
    return "gray"


def mean_hex(px):
    count = len(px)
    r = sum(p[0] for p in px) // count
    g = sum(p[1] for p in px) // count
    b = sum(p[2] for p in px) // count
    return f"#{r:02x}{g:02x}{b:02x}"


def dominant(path):
    """{'color', 'hex', 'weight', 'value'} 를 돌려준다.

    weight 는 묶음 안에서 줄을 세우는 값(클수록 앞). 색이 있으면 '넓이 x 진하기',
    무채색이면 밝기다. value 는 아이콘 전체 밝기로, 수동 보정이 색깔 묶음을
    무채색으로 바꿔 놓았을 때 대신 쓸 정렬값이다.
    """
    px = sample_pixels(path)
    if not px:
        # 걷어내고 나니 아무것도 안 남았다. 빈 그림이라서가 아니라 아이콘 전체가
        # 외곽선만큼 새까매서다 (유다의 그림자, 내 그림자, 철제 옷걸이).
        # 여기서 회색을 돌려주면 새까만 실루엣이 회색 묶음에 가서 앉는다.
        px = sample_pixels(path, floor=0.0)
        if not px:
            return {"color": "gray", "hex": "#808080", "weight": 0.5, "value": 0.5}
        value = sum(p[5] for p in px) / len(px)
        return {"color": "black", "hex": mean_hex(px),
                "weight": round(value, 4), "value": round(value, 4)}

    count = len(px)
    value = sum(p[5] for p in px) / count

    # 픽셀을 색깔 묶음별로 나눠 담는다. 흐리거나 어두운 픽셀은 어느 쪽에도 넣지 않는다.
    groups = {}
    for pixel in px:
        if pixel[4] < COLOR_S or pixel[5] < COLOR_V:
            continue
        groups.setdefault(hue_to_bucket(pixel[3]), []).append(pixel)

    best = max(groups, key=lambda key: len(groups[key])) if groups else None
    share = len(groups[best]) / count if best else 0.0
    if not best or share < MIN_SHARE:
        # 색이라고 할 만한 자리가 없다. 흰색/회색/검정으로 보낸다.
        return {"color": achromatic_bucket(value), "hex": mean_hex(px),
                "weight": round(value, 4), "value": round(value, 4)}

    # 대표색은 그 묶음 안에서 진한 픽셀에 무게를 실어 평균낸다.
    group = groups[best]
    weights = [p[4] * p[5] for p in group]
    total = sum(weights) or 1.0
    r = int(sum(p[0] * w for p, w in zip(group, weights)) / total)
    g = int(sum(p[1] * w for p, w in zip(group, weights)) / total)
    b = int(sum(p[2] * w for p, w in zip(group, weights)) / total)
    sat = sum(p[4] * w for p, w in zip(group, weights)) / total
    val = sum(p[5] * w for p, w in zip(group, weights)) / total

    bucket = best
    # 어두운 주황·노랑은 눈에 갈색으로 보인다. 나무, 가죽, 똥 같은 것들이 여기 걸린다.
    if bucket in ("orange", "yellow") and val < BROWN_V:
        bucket = "brown"
    # 어둡고 탁한 빨강도 마찬가지다. 간·골수·가죽처럼 적갈색으로 보이는 것들.
    # 선명한 빨강은 어두워도 피나 심장이라 여전히 빨강으로 남긴다.
    elif bucket == "red" and val < RED_BROWN_V and sat < RED_BROWN_S:
        bucket = "brown"
    # 아이작의 살빛은 색조로만 보면 빨강·주황이지만 흐리고 밝다. 아기·태아 계열이
    # 몰려 있어 빨강에 섞어두면 빨강 묶음이 너무 커져 훑어보기 어려워진다.
    elif bucket in ("red", "orange", "yellow") and sat < SKIN_S and val >= SKIN_V:
        bucket = "skin"

    return {"color": bucket, "hex": f"#{r:02x}{g:02x}{b:02x}",
            "weight": round(share * sat, 4), "value": round(value, 4)}


def load_overrides():
    path = ROOT / "color_overrides.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def main():
    icons = ROOT / "_cache" / "icons" / "item"
    checks = {1: "슬픈 양파", 12: "마법의 버섯", 33: "성경", 547: "이혼 서류", 118: "-"}
    for item_id in sorted(checks):
        path = icons / f"{item_id}.png"
        if path.exists():
            print(item_id, checks[item_id], dominant(path))


if __name__ == "__main__":
    main()
