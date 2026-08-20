#!/usr/bin/env python3
"""한글 데이터 + 아이콘 + 색상 분류를 합쳐 사이트가 읽을 파일을 만든다.

만드는 것:
    assets/data/items.json      아이템·장신구 통합 데이터
    assets/icons/sprite.webp    아이콘을 한 장으로 합친 스프라이트 시트
    assets/icons/app-*.png      홈 화면 추가용 아이콘
    tools/_report/colors.html   색상 분류 눈으로 검수하는 페이지

실행:
    python3 tools/build.py
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

import extract_colors as colors
import parse_eid
import parse_gamedata

# Pillow 10 에서 상수 위치가 바뀌었다. 둘 다 지원한다.
NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent
CACHE = ROOT / "_cache"
ITEM_ICONS = CACHE / "icons" / "item"
TRINKET_ICONS = CACHE / "icons" / "trinket"
CARD_ICONS = CACHE / "icons" / "card"
REPORT = ROOT / "_report"

CELL = 64      # 아이템 아이콘 원본 크기. 장신구(32px)는 2배로 키워 맞춘다.
COLS = 30      # 스프라이트 시트 가로 칸 수
BUCKET_ORDER = {key: i for i, (key, _ko, _emoji) in enumerate(colors.BUCKETS)}


def normalize(name):
    """영문 이름을 파일 이름과 맞춰보기 위한 형태로 낮춘다.

    위키 파일 이름은 아포스트로피와 물음표를 아예 빼고 나머지 기호는 밑줄로 바꾼 꼴이다.
    (Mom's Toenail -> Moms_Toenail)
    """
    name = name.replace("&", "and").replace("'", "").replace("?", "")
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()


def build_trinket_index():
    return {normalize(p.stem): p for p in TRINKET_ICONS.glob("*.png")}


def load_overrides(filename):
    path = ROOT / filename
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def resolve_icons(data, report):
    """각 항목에 아이콘 경로를 붙인다. 못 찾은 항목은 빼고 사유를 기록한다."""
    trinket_index = build_trinket_index()
    icon_overrides = load_overrides("icon_overrides.json")
    resolved = []

    for kind in ("item", "trinket", "card"):
        for entry_id, entry in sorted(data[kind].items()):
            key = f"{kind}:{entry_id}"
            if not entry["ko"].strip() and not entry["en"].strip():
                # 이름이 아예 없는 번호는 게임 데이터의 빈 자리다. 아이콘이 있어도 아이템이 아니다.
                report["nameless"].append(key)
                continue
            path = None
            if key in icon_overrides:
                candidate = TRINKET_ICONS / icon_overrides[key]
                path = candidate if candidate.exists() else None
                if path is None:
                    report["icon_override_missing"].append(f"{key} -> {icon_overrides[key]}")
            elif kind == "item":
                candidate = ITEM_ICONS / f"{entry_id}.png"
                path = candidate if candidate.exists() else None
            elif kind == "card":
                candidate = CARD_ICONS / f"{entry_id}.png"
                path = candidate if candidate.exists() else None
            else:
                path = trinket_index.get(normalize(entry["en"])) if entry["en"] else None

            if path is None:
                # 아이콘이 없는 ID 는 게임에서 안 쓰는 빈 번호이거나 위키에 그림이 없는 항목이다.
                report["no_icon"].append(f"{key} {entry['ko'] or entry['en'] or '?'}")
                continue
            resolved.append({"kind": kind, "id": entry_id, "path": path, **entry})
    return resolved


def classify(entries, report):
    color_overrides = load_overrides("color_overrides.json")
    for entry in entries:
        info = colors.dominant(entry["path"])
        key = f"{entry['kind']}:{entry['id']}"
        if key in color_overrides:
            info["color"] = color_overrides[key]
            if info["color"] in colors.ACHROMATIC:
                # 손으로 무채색에 보낸 항목은 비중 대신 밝기로 줄을 세워야 이웃과 눈금이 맞는다.
                info["weight"] = info["value"]
            report["color_overridden"] += 1
        entry.update(info)
    return entries


# 카드 그림이 칸 안에서 차지할 최대 크기. 카드 원본 대부분이 14x18 이라 3배 하면 42x54 가 된다.
# 위키가 크게 그려 둔 몇몇 그림도 여기에 맞춰야 나란히 놓았을 때 혼자 커 보이지 않는다.
CARD_BOX = 56


def fit_cell(icon):
    """어떤 크기의 그림이든 64px 칸에 들어가게 맞춘다.

    아이템은 64px, 장신구는 32px, 카드는 14x18 처럼 원본이 제각각이다.
    도트 그림이라 키울 때는 정수배 NEAREST 로만 늘려야 픽셀이 흐려지지 않는다.
    """
    width, height = icon.size
    if (width, height) == (CELL, CELL):
        return icon

    # 위키가 크게 렌더링해 둔 그림(룬 등)은 여백까지 넉넉해서, 투명한 가장자리를 먼저 잘라낸다.
    if max(width, height) >= CELL * 2:
        box = icon.getbbox()
        if box:
            icon = icon.crop(box)
            width, height = icon.size
        scale = CARD_BOX / max(width, height)
        # 원본이 이미 부드럽게 확대된 그림이라 여기서는 LANCZOS 가 결과가 낫다.
        return icon.resize((max(1, round(width * scale)), max(1, round(height * scale))),
                           Image.LANCZOS)

    factor = max(1, CELL // max(width, height))
    return icon.resize((width * factor, height * factor), NEAREST) if factor > 1 else icon


def attach_gamedata(entries, report):
    """등급과 등장 장소를 붙인다.

    셋 다 아이템에만 붙는다. 게임 XML 은 장신구 등급을 전부 0 으로 적어 두는데
    실제로 매긴 값이 아니라서, 그대로 보여주면 모든 장신구가 최하 등급인 것처럼 읽힌다.
    카드는 아예 해당 사항이 없다.
    """
    quality = parse_gamedata.load_quality()["item"]
    pools = parse_gamedata.load_pools()
    types = parse_gamedata.load_types()
    transforms = parse_gamedata.load_transformations()
    for entry in entries:
        if entry["kind"] != "item":
            continue
        info = types.get(entry["id"])
        if info:
            entry["type"] = info["type"]
            if "chargetype" in info:
                entry["chargetype"] = info["chargetype"]
            if "charge" in info:
                entry["charge"] = info["charge"]
        else:
            report["no_type"].append(f"item:{entry['id']} {entry['ko']}")
        if entry["id"] in quality:
            entry["quality"] = quality[entry["id"]]
        else:
            report["no_quality"].append(f"item:{entry['id']} {entry['ko']}")
        names = transforms.get(entry["id"])
        if names:
            entry["sets"] = names
        places = pools.get(entry["id"])
        if places:
            entry["pools"] = places
        else:
            report["no_pool"].append(f"item:{entry['id']} {entry['ko']}")
    return entries


def write_sprite(entries):
    """아이콘을 한 장으로 합친다. 요청 한 번이면 909개가 다 뜬다."""
    rows = (len(entries) + COLS - 1) // COLS
    sheet = Image.new("RGBA", (COLS * CELL, rows * CELL), (0, 0, 0, 0))
    for index, entry in enumerate(entries):
        with Image.open(entry["path"]) as icon:
            icon = fit_cell(icon.convert("RGBA"))
        left = (index % COLS) * CELL + (CELL - icon.width) // 2
        top = (index // COLS) * CELL + (CELL - icon.height) // 2
        sheet.paste(icon, (left, top))
        entry["idx"] = index

    out = SITE / "assets" / "icons" / "sprite.webp"
    sheet.save(out, "WEBP", lossless=True, quality=100, method=6)
    return out, sheet.size


def write_app_icons():
    """홈 화면용 아이콘. 이 사이트의 주제인 색깔 묶음을 그대로 그린다."""
    palette = ["#e5484d", "#f76b15", "#ffd23f", "#46a758", "#3b82f6",
               "#8e4ec6", "#e93d82", "#d9a07a", "#8b5e3c"]
    made = []
    for size in (192, 512):
        img = Image.new("RGBA", (size, size), (17, 18, 22, 255))
        draw = ImageDraw.Draw(img)
        pad = size // 8
        gap = size // 40
        cell = (size - pad * 2 - gap * 2) / 3
        for i, color in enumerate(palette):
            x = pad + (i % 3) * (cell + gap)
            y = pad + (i // 3) * (cell + gap)
            draw.rounded_rectangle(
                [x, y, x + cell, y + cell], radius=cell / 5, fill=color
            )
        path = SITE / "assets" / "icons" / f"app-{size}.png"
        img.save(path)
        made.append(path)
    return made


def write_report(entries):
    REPORT.mkdir(exist_ok=True)
    by_bucket = {key: [] for key, _ko, _emoji in colors.BUCKETS}
    for entry in entries:
        by_bucket[entry["color"]].append(entry)

    parts = [
        "<!doctype html><meta charset='utf-8'><title>색상 분류 검수</title>",
        "<style>body{background:#15161a;color:#eee;font:14px/1.5 system-ui;margin:24px}"
        "h2{margin:28px 0 10px;font-size:16px}"
        "div.grid{display:flex;flex-wrap:wrap;gap:6px}"
        "figure{margin:0;width:82px;text-align:center}"
        "img{width:64px;height:64px;image-rendering:pixelated;background:#000;border-radius:6px}"
        "figcaption{font-size:10px;color:#aaa;word-break:keep-all;line-height:1.2;margin-top:3px}"
        "p.hint{color:#9aa;max-width:60em}</style>",
        "<h1>색상 분류 검수</h1>",
        "<p class='hint'>묶음 안은 <b>그 색이 짙은 것부터</b> 늘어놓았습니다 "
        "(아래 숫자가 비중). 뒤로 갈수록 색이 옅어지는 건 정상이고, "
        "눈에 보이는 색과 아예 다르게 묶인 아이콘을 찾아 "
        "<code>tools/color_overrides.json</code> 에 <code>\"item:105\": \"red\"</code> 형태로 적고 "
        "<code>python3 tools/build.py</code> 를 다시 실행하세요.</p>",
    ]
    for key, ko, emoji in colors.BUCKETS:
        group = sorted(by_bucket[key], key=lambda e: -e["weight"])
        parts.append(f"<h2>{emoji} {ko} ({len(group)})</h2><div class='grid'>")
        for entry in group:
            rel = Path("..") / entry["path"].relative_to(ROOT)
            label = entry["ko"] or entry["en"]
            parts.append(
                f"<figure><img src='{rel}' alt=''>"
                f"<figcaption>{entry['kind'][0]}{entry['id']}<br>{label}"
                f"<br><b>{entry['weight']:.2f}</b></figcaption></figure>"
            )
        parts.append("</div>")
    path = REPORT / "colors.html"
    path.write_text("".join(parts), encoding="utf-8")
    return path


def main():
    report = {"no_icon": [], "nameless": [], "icon_override_missing": [],
              "no_quality": [], "no_pool": [], "no_type": [], "color_overridden": 0}

    print("[1/5] 한글 텍스트 병합")
    data = parse_eid.load()
    print(f"  아이템 {len(data['item'])} / 장신구 {len(data['trinket'])}")

    print("[2/5] 아이콘 연결")
    entries = resolve_icons(data, report)
    print(f"  연결됨 {len(entries)} / 아이콘 없어 제외 {len(report['no_icon'])}"
          f" / 이름 없어 제외 {len(report['nameless'])}")

    print("[3/5] 대표 색상 추출 · 등급 · 등장 장소")
    entries = classify(entries, report)
    entries = attach_gamedata(entries, report)
    # 색깔 묶음 순서 -> 묶음 안에서는 그 색이 짙은 것부터. 온통 빨간 아이콘이 앞에 서고
    # 빨간 점만 몇 개 찍힌 아이콘이 뒤로 밀린다. 마지막 검정 묶음 끝이 가장 어둡다.
    entries.sort(key=lambda e: (BUCKET_ORDER[e["color"]], -e["weight"], e["kind"], e["id"]))

    print("[4/5] 스프라이트 시트")
    sprite_path, sprite_size = write_sprite(entries)
    print(f"  {sprite_path.name} {sprite_size[0]}x{sprite_size[1]} "
          f"({sprite_path.stat().st_size / 1024:.0f}KB)")

    print("[5/5] items.json · 앱 아이콘 · 검수 페이지")
    payload = {
        "generated": date.today().isoformat(),
        "sprite": {"url": "assets/icons/sprite.webp", "cell": CELL, "cols": COLS},
        "buckets": [{"key": k, "ko": ko, "emoji": e} for k, ko, e in colors.BUCKETS],
        "setsNeeded": parse_gamedata.TRANSFORM_NEEDED,
        "setInfo": parse_gamedata.load_transformation_stats(),
        "kinds": [{"key": "item", "ko": "아이템"}, {"key": "trinket", "ko": "장신구"},
                  {"key": "card", "ko": "카드"}],
        "entries": [
            {
                "kind": e["kind"], "id": e["id"], "idx": e["idx"],
                "ko": e["ko"], "en": e["en"], "desc": e["desc"],
                "color": e["color"], "hex": e["hex"],
                **({"quality": e["quality"]} if "quality" in e else {}),
                **({"pools": e["pools"]} if "pools" in e else {}),
                **({"type": e["type"]} if "type" in e else {}),
                **({"chargetype": e["chargetype"]} if "chargetype" in e else {}),
                **({"charge": e["charge"]} if "charge" in e else {}),
                **({"sets": e["sets"]} if "sets" in e else {}),
            }
            for e in entries
        ],
    }
    json_path = SITE / "assets" / "data" / "items.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    write_app_icons()
    report_path = write_report(entries)
    print(f"  items.json {json_path.stat().st_size / 1024:.0f}KB")

    print("\n=== 검증 리포트 ===")
    kinds = {}
    buckets = {}
    for entry in entries:
        kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
        buckets[entry["color"]] = buckets.get(entry["color"], 0) + 1
    print(f"총 {len(entries)}개 — " + " / ".join(f"{k} {v}" for k, v in kinds.items()))
    print("색깔 분포:")
    for key, ko, emoji in colors.BUCKETS:
        count = buckets.get(key, 0)
        bar = "█" * round(count / max(buckets.values()) * 28)
        print(f"  {emoji} {ko:<4} {count:>4}  {bar}")
    if report["color_overridden"]:
        print(f"수동 색상 보정: {report['color_overridden']}건")

    qualities = {}
    for entry in entries:
        if "quality" in entry:
            qualities[entry["quality"]] = qualities.get(entry["quality"], 0) + 1
    if qualities:
        print("등급 분포: " + "  ".join(f"Q{q} {qualities[q]}" for q in sorted(qualities)))
    types = {}
    for entry in entries:
        if "type" in entry:
            types[entry["type"]] = types.get(entry["type"], 0) + 1
    if types:
        print("종류: " + "  ".join(f"{k} {v}" for k, v in sorted(types.items()))
              + f"  (종류 불명 {len(report['no_type'])})")
        charged = [e for e in entries if e.get("type") == "active"]
        rooms = sum(1 for e in charged if "charge" in e)
        print(f"액티브 {len(charged)}개 중 방 충전 {rooms}개 · "
              f"나머지 {len(charged) - rooms}개는 시간/특수 충전")
    sets = {}
    for entry in entries:
        for one in entry.get("sets", []):
            sets[one["ko"]] = sets.get(one["ko"], 0) + 1
    if sets:
        member = sum(1 for e in entries if e.get("sets"))
        print(f"변신 세트: {len(sets)}종 / 세트에 속한 아이템 {member}개")
        print("  " + "  ".join(f"{k} {v}" for k, v in sorted(sets.items(), key=lambda x: -x[1])))
    with_pool = sum(1 for e in entries if e.get("pools"))
    print(f"등장 장소 있음: {with_pool}개 / 등급 없음 {len(report['no_quality'])}개"
          f" / 어느 장소에도 안 나옴 {len(report['no_pool'])}개")

    missing_desc = [e for e in entries if not e["desc"]]
    missing_ko = [e for e in entries if not e["ko"]]
    print(f"한글 설명 없음: {len(missing_desc)}건")
    for entry in missing_desc[:10]:
        print(f"  - {entry['kind']}:{entry['id']} {entry['en']}")
    print(f"한글 이름 없음: {len(missing_ko)}건")
    if report["nameless"]:
        print(f"이름이 없어 제외한 빈 번호: {', '.join(report['nameless'])}")
    only_en = [e for e in entries if e["ko"] and e["ko"] == e["en"]]
    if only_en:
        print(f"한글명 미번역(영문 그대로): {len(only_en)}건 -> "
              + ", ".join(f"{e['kind']}:{e['id']} {e['en']}" for e in only_en[:8]))
    if report["icon_override_missing"]:
        print(f"아이콘 예외 지정 실패: {report['icon_override_missing']}")
    print(f"\n아이콘 없어 제외된 ID {len(report['no_icon'])}건 "
          f"(게임에서 안 쓰는 빈 번호): {', '.join(x.split()[0] for x in report['no_icon'][:15])}")
    print(f"\n색상 검수 페이지: open {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
