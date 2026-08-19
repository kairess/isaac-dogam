#!/usr/bin/env python3
"""게임 XML 에서 아이템 등급 · 등장 장소 · 종류와 충전량을 읽는다.

등급(quality), 아이템 풀, 액티브/패시브 구분은 EID 텍스트 팩에 없다.
게임이 resources 폴더에 들고 있는 items_metadata.xml / itempools.xml / items.xml 이
원본이고, 그 사본을 tools/_cache/text/ 에 받아 둔다.

단독 실행하면 요약을 출력한다:
    python3 tools/parse_gamedata.py
"""
import re
import sys
from pathlib import Path

TEXT_DIR = Path(__file__).resolve().parent / "_cache" / "text"

# 풀 이름을 XML 의 영문 키로 잇는다.
# EID 에도 한글 풀 이름 목록이 있지만 그리드 모드 풀 세 개의 차례가 게임 enum 과 어긋나 있어,
# 번호 대신 이름으로 직접 맞춰 둔다.
POOL_KO = {
    "treasure": "보물방", "shop": "상점", "boss": "보스방", "devil": "악마방",
    "angel": "천사방", "secret": "비밀방", "library": "책방", "shellGame": "야바위꾼",
    "goldenChest": "황금 상자", "redChest": "빨간 상자", "beggar": "거지",
    "demonBeggar": "악마 거지", "curse": "저주방", "keyMaster": "열쇠 거지",
    "batteryBum": "배터리 거지", "momsChest": "엄마 상자",
    "greedTreasure": "그리드 보물방", "greedBoss": "그리드 보스방",
    "greedShop": "그리드 상점", "greedCurse": "그리드 저주방",
    "greedDevil": "그리드 악마방", "greedAngel": "그리드 천사방",
    "greedSecret": "그리드 비밀방", "craneGame": "크레인 게임",
    "ultraSecret": "특급 비밀방", "bombBum": "폭탄 거지", "planetarium": "천체관",
    "oldChest": "낡은 상자", "babyShop": "패밀리어 상점", "woodenChest": "나무 상자",
    "rottenBeggar": "썩은 거지",
}


def read(name):
    path = TEXT_DIR / name
    if not path.exists():
        sys.exit(f"소스가 없습니다: {path}\n먼저 `python3 tools/fetch_sources.py` 를 실행하세요.")
    return path.read_text(encoding="utf-8")


# 변신(세트) 이름. EID 한국어 팩은 이 표만 영어로 남겨 둬서 여기서 옮긴다.
# 게임 안에서는 같은 계열 3개를 모으면 그 모습으로 바뀐다.
TRANSFORM_KO = {
    1: "구피", 2: "펀 가이", 3: "베엘제붑", 4: "콘조인드", 5: "스펀",
    6: "예스 마더?", 7: "오 크랩", 8: "밥", 9: "리바이어던", 10: "세라핌",
    11: "슈퍼 범", 12: "북웜", 13: "스파이더 베이비", 14: "어덜트", 15: "스톰피",
}
TRANSFORM_EN = {
    1: "Guppy", 2: "Fun Guy", 3: "Beelzebub", 4: "Conjoined", 5: "Spun",
    6: "Yes Mother?", 7: "Oh Crap", 8: "Bob", 9: "Leviathan", 10: "Seraphim",
    11: "Super Bum", 12: "Bookworm", 13: "Spider Baby", 14: "Adult", 15: "Stompy",
}
# 변신에 필요한 개수. 모든 변신이 3개로 같다.
TRANSFORM_NEEDED = 3


def load_transformations():
    """{아이템id: [{'ko','en'}, ...]} 를 돌려준다.

    EID 는 "5.100.<아이템id>" 형태로 적고, 값은 변신 번호다.
    두 변신에 걸친 아이템은 "2,15" 처럼 쉼표로 이어 적혀 있다.
    알약으로만 되는 변신(어덜트)도 있는데 아이템이 없으니 자연히 빠진다.
    """
    text = read("transformations.lua")
    out = {}
    for item_id, value in re.findall(r'\["5\.100\.(\d+)"\]\s*=\s*"([^"]+)"', text):
        names = []
        for one in value.split(","):
            one = one.strip()
            if one.isdigit() and int(one) in TRANSFORM_KO:
                names.append({"ko": TRANSFORM_KO[int(one)], "en": TRANSFORM_EN[int(one)]})
        if names:
            out[int(item_id)] = names
    return out


def load_transformation_stats():
    """{한글이름: {'en', 'items', 'other'}} 를 돌려준다.

    변신은 아이템만으로 채워지지 않는 것도 있다. 스톰피는 아이템 2개에 알약 1개가 붙고,
    어덜트는 알약만으로 된다. 화면에 "2개 중 3개를 모으면" 이라고 적히지 않게
    아이템 밖의 구성원 수도 세어 둔다.
    """
    text = read("transformations.lua")
    stats = {}
    for kind, _entry_id, value in re.findall(
            r'\["5\.(\d+)\.(\d+)"\]\s*=\s*"([^"]+)"', text):
        for one in value.split(","):
            one = one.strip()
            if not one.isdigit() or int(one) not in TRANSFORM_KO:
                continue
            slot = stats.setdefault(TRANSFORM_KO[int(one)],
                                    {"en": TRANSFORM_EN[int(one)], "items": 0, "other": 0})
            slot["items" if kind == "100" else "other"] += 1
    return stats


# 충전 방식. 기본값은 방을 깨서 채우는 것이고, 나머지는 XML 에 chargetype 으로 적혀 있다.
CHARGE_KO = {
    "room": "방",       # maxcharges 만큼 방을 깨면 찬다
    "timed": "시간",    # 시간이 지나면 저절로 찬다
    "special": "특수",  # 아이템마다 채우는 조건이 따로 있다
}


def load_types():
    """{아이템id: {'type', 'charge', 'chargetype'}} 를 돌려준다.

    게임은 아이템을 passive / active / familiar 로 나눠 적는다.
    패밀리어는 자리로 보면 패시브지만 따라다니는 동료라 따로 표시할 값이 있어 남겨 둔다.
    """
    text = read("items.xml")
    out = {}
    for tag, attrs in re.findall(r"<(passive|active|familiar)\b([^>]*?)/?>", text):
        found = re.search(r'\bid="(\d+)"', attrs)
        if not found:
            continue
        entry = {"type": tag}
        if tag == "active":
            charge = re.search(r'\bmaxcharges="(\d+)"', attrs)
            kind = re.search(r'\bchargetype="(\w+)"', attrs)
            entry["chargetype"] = kind.group(1) if kind else "room"
            # 방 충전일 때만 숫자가 방 개수를 뜻한다.
            # 시간·특수 충전의 숫자는 내부 눈금이라 그대로 보여주면 오해를 부른다.
            if entry["chargetype"] == "room" and charge and int(charge.group(1)) > 0:
                entry["charge"] = int(charge.group(1))
        out[int(found.group(1))] = entry
    return out


def load_quality():
    """{'item': {id: 등급}, 'trinket': {id: 등급}} 을 돌려준다."""
    text = read("items_metadata.xml")
    out = {"item": {}, "trinket": {}}
    for tag, kind in (("item", "item"), ("trinket", "trinket")):
        for entry_id, quality in re.findall(
            rf'<{tag} id="(\d+)"[^>]*\bquality="(\d+)"', text
        ):
            out[kind][int(entry_id)] = int(quality)
    return out


def load_pools():
    """{아이템id: [한글 풀 이름, ...]} 를 돌려준다. 차례는 XML 에 적힌 순서 그대로다."""
    text = read("itempools.xml")
    pools = {}
    unknown = set()
    # <Pool Name="treasure"> ... </Pool> 덩어리를 하나씩 훑는다.
    for name, body in re.findall(r'<Pool Name="([^"]+)">(.*?)</Pool>', text, re.S):
        korean = POOL_KO.get(name)
        if korean is None:
            unknown.add(name)
            continue
        for entry_id in re.findall(r'<Item Id="(\d+)"', body):
            pools.setdefault(int(entry_id), []).append(korean)
    if unknown:
        print(f"  ! 한글 이름이 없는 풀: {', '.join(sorted(unknown))}", file=sys.stderr)
    return pools


def main():
    quality = load_quality()
    pools = load_pools()
    types = load_types()
    counts = {}
    for entry in types.values():
        counts[entry["type"]] = counts.get(entry["type"], 0) + 1
    print("종류:", "  ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    charge = {}
    for entry in types.values():
        if entry["type"] == "active":
            charge[entry["chargetype"]] = charge.get(entry["chargetype"], 0) + 1
    print("액티브 충전 방식:", "  ".join(f"{CHARGE_KO[k]} {v}" for k, v in sorted(charge.items())))
    rooms = sorted({e["charge"] for e in types.values() if "charge" in e})
    print("방 충전 칸 수 종류:", rooms)
    trans = load_transformations()
    counts = {}
    for names in trans.values():
        for n in names:
            counts[n["ko"]] = counts.get(n["ko"], 0) + 1
    print(f"변신 세트: {len(counts)}종 / 세트에 속한 아이템 {len(trans)}개")
    print("  " + "  ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))
    for kind, table in quality.items():
        counts = {}
        for value in table.values():
            counts[value] = counts.get(value, 0) + 1
        spread = " ".join(f"Q{q}:{counts[q]}" for q in sorted(counts))
        print(f"{kind} 등급: {len(table)}개  {spread}")
    print(f"등장 장소가 있는 아이템: {len(pools)}개")
    sizes = {}
    for names in pools.values():
        sizes[len(names)] = sizes.get(len(names), 0) + 1
    print("아이템당 장소 수 분포:", dict(sorted(sizes.items())))
    print("예시 1(슬픈 양파):", pools.get(1))
    print("예시 33(성경):", pools.get(33))


if __name__ == "__main__":
    main()
