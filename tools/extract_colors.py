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
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent

ALPHA_MIN = 128      # 반투명 가장자리는 셈에서 뺀다
OUTLINE_V = 0.18     # 이보다 어두우면 외곽선/그림자로 본다
COLOR_S = 0.25       # 이보다 흐린 픽셀은 '색이 있다'고 세지 않는다
COLOR_V = 0.25       # 이보다 어두운 픽셀도 마찬가지
MIN_SHARE = 0.18     # 아이콘의 이만큼은 덮어야 그 색으로 본다. 아니면 무채색
BROWN_V = 0.50       # 따뜻한 색이 이보다 어두우면 갈색으로 본다
RED_BROWN_V = 0.48   # 어둡고 탁한 빨강도 갈색으로 본다 (간, 똥, 가죽)
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
        return {"color": "gray", "hex": "#808080", "weight": 0.5, "value": 0.5}

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
