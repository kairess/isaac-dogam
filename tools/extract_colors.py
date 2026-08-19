#!/usr/bin/env python3
"""아이콘 스프라이트에서 대표 색상을 뽑아 색깔 버킷으로 분류한다.

아이작 스프라이트는 검은 외곽선이 두꺼워서 픽셀 평균을 그냥 내면 죄다 탁한 색이 된다
(슬픈 양파의 단순 평균은 RGB(71,86,65) 로 초록이라기엔 너무 어둡다).
그래서 외곽선을 걷어낸 뒤 '진한 색일수록 무겁게' 세는 색상환 히스토그램으로 대표 색조를 찾는다.

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
MONO_S = 0.18        # 이보다 채도가 낮으면 색이 없는 것으로 본다
BROWN_V = 0.50       # 따뜻한 색이 이보다 어두우면 갈색으로 본다
SKIN_S = 0.42        # 따뜻한 색이 이보다 흐리고 밝으면 살구색으로 본다
SKIN_HUE = (8, 45)   # 살구색으로 볼 색조 범위
WHITE_V = 0.62       # 무채색 중 이보다 밝으면 흰색
BLACK_V = 0.32       # 무채색 중 이보다 어두우면 검정
BINS = 36            # 색상환을 10도씩 나눈다

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


def sample_pixels(path):
    """아이콘에서 외곽선을 뺀 (r, g, b, h, s, v) 목록을 만든다."""
    with Image.open(path) as img:
        pixels = list(img.convert("RGBA").getdata())
    kept = []
    for r, g, b, a in pixels:
        if a < ALPHA_MIN:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v < OUTLINE_V:
            continue
        kept.append((r, g, b, h * 360, s, v))
    return kept


def achromatic_bucket(value):
    """색이 없는 아이콘을 밝기로 흰색/회색/검정으로 나눈다."""
    if value >= WHITE_V:
        return "white"
    if value <= BLACK_V:
        return "black"
    return "gray"


def dominant(path):
    """{'color', 'hex', 'hue'} 를 돌려준다. 빈 아이콘이면 회색으로 떨어진다."""
    px = sample_pixels(path)
    if not px:
        return {"color": "gray", "hex": "#808080", "hue": 0.0}

    # 진한 색(채도x명도)일수록 큰 표를 준다. 흐린 배경색이 대표를 차지하지 못하게 하는 장치다.
    weights = [s * v for *_rgb, _h, s, v in px]
    total_weight = sum(weights)
    mean_sat = sum(s * w for (*_rgb, _h, s, _v), w in zip(px, weights)) / total_weight if total_weight else 0.0

    if total_weight < 1e-6 or mean_sat < MONO_S:
        count = len(px)
        r = sum(p[0] for p in px) // count
        g = sum(p[1] for p in px) // count
        b = sum(p[2] for p in px) // count
        mean_val = sum(p[5] for p in px) / count
        # 회색끼리는 색조가 없으니 밝은 쪽이 앞에 오도록 정렬값을 밝기로 대신한다.
        return {
            "color": achromatic_bucket(mean_val),
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "hue": round(mean_val * 360, 1),
        }

    # 색상환 히스토그램. 인접 칸까지 번지게 해서 경계에 걸친 색이 표를 잃지 않게 한다.
    hist = [0.0] * BINS
    for (_r, _g, _b, h, _s, _v), w in zip(px, weights):
        hist[int(h // 10) % BINS] += w
    smoothed = [
        hist[(i - 1) % BINS] * 0.5 + hist[i] + hist[(i + 1) % BINS] * 0.5
        for i in range(BINS)
    ]
    peak = max(range(BINS), key=lambda i: smoothed[i])

    # 최빈 색조 주변(±25도)만 모아 대표색을 낸다. 각도는 원형이라 벡터로 평균낸다.
    center = peak * 10 + 5
    near = [
        (p, w)
        for p, w in zip(px, weights)
        if min((p[3] - center) % 360, (center - p[3]) % 360) <= 25
    ]
    if not near:
        near = list(zip(px, weights))
    near_weight = sum(w for _p, w in near)
    r = int(sum(p[0] * w for p, w in near) / near_weight)
    g = int(sum(p[1] * w for p, w in near) / near_weight)
    b = int(sum(p[2] * w for p, w in near) / near_weight)
    x = sum(math.cos(math.radians(p[3])) * w for p, w in near)
    y = sum(math.sin(math.radians(p[3])) * w for p, w in near)
    hue = math.degrees(math.atan2(y, x)) % 360
    mean_val = sum(p[5] * w for p, w in near) / near_weight
    near_sat = sum(p[4] * w for p, w in near) / near_weight

    bucket = hue_to_bucket(hue)
    # 어두운 주황·노랑은 눈에 갈색으로 보인다. 나무, 가죽, 똥 같은 것들이 여기 걸린다.
    # 빨강은 여기서 제외한다. 어두운 빨강은 피나 심장이라 여전히 빨강으로 보인다.
    if bucket in ("orange", "yellow") and mean_val < BROWN_V:
        bucket = "brown"
    # 아이작의 살빛은 색조로만 보면 주황이지만 흐리고 밝다. 아기·태아 계열이 몰려 있어
    # 빨강에 섞어두면 빨강 묶음이 너무 커져 훑어보기 어려워진다.
    elif bucket in ("red", "orange", "yellow") and near_sat < SKIN_S \
            and SKIN_HUE[0] <= hue < SKIN_HUE[1]:
        bucket = "skin"

    return {"color": bucket, "hex": f"#{r:02x}{g:02x}{b:02x}", "hue": round(hue, 1)}


def load_overrides():
    path = ROOT / "color_overrides.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def main():
    icons = ROOT / "_cache" / "icons" / "item"
    checks = {1: "슬픈 양파", 12: "마법의 버섯", 105: "-", 33: "성경", 118: "-"}
    for item_id in sorted(checks):
        path = icons / f"{item_id}.png"
        if path.exists():
            print(item_id, checks[item_id], dominant(path))


if __name__ == "__main__":
    main()
