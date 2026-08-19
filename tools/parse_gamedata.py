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
# 표기는 나무위키 "아이작의 번제: 리버스/시스템" 변신 세트 항목을 따랐다.
# 음차보다 뜻을 옮긴 쪽이 한국 플레이어에게 통하는 이름이다 (Fun Guy = 버섯, Oh Crap = 똥).
# 변신할 때 화면에 뜨는 느낌표는 이름의 일부가 아니라 빼고, 뜻이 담긴 물음표는 남겼다.
TRANSFORM_KO = {
    1: "구피", 2: "버섯", 3: "벨제붑", 4: "샴쌍둥이", 5: "약쟁이",
    6: "엄마?", 7: "똥", 8: "밥", 9: "레비아탄", 10: "세라핌",
    11: "슈퍼 거지", 12: "책벌레", 13: "거미", 14: "성인", 15: "쿵쿵이",
}
TRANSFORM_EN = {
    1: "Guppy", 2: "Fun Guy", 3: "Beelzebub", 4: "Conjoined", 5: "Spun",
    6: "Yes Mother?", 7: "Oh Crap", 8: "Bob", 9: "Leviathan", 10: "Seraphim",
    11: "Super Bum", 12: "Bookworm", 13: "Spider Baby", 14: "Adult", 15: "Stompy",
}
# 변신에 필요한 개수. 모든 변신이 3개로 같다.
TRANSFORM_NEEDED = 3

# 변신을 마쳤을 때 실제로 붙는 효과. Repentance(v1.7.9b) 기준으로 적었다.
# 아이템 설명과 같은 말투를 쓰고, 능력치 증감은 ↑ ↓ 로 앞을 맞춘다.
TRANSFORM_EFFECT = {
    1: ["날 수 있게 됩니다.", "피격 시 아군 파란 파리가 나옵니다."],
    2: ["↑ 최대 체력 +1"],
    3: ["날 수 있게 됩니다.", "적 파리가 아군으로 바뀝니다."],
    4: ["머리 양옆에 혹이 붙어 대각선으로 함께 공격합니다.",
        "↓ 공격력 -0.3", "↓ 연사 -0.3"],
    5: ["↑ 공격력 +2", "↑ 이동속도 +0.15", "알약을 1개 떨어뜨립니다."],
    6: ["엄마의 칼이 뒤에 꼬리처럼 따라붙습니다."],
    7: ["똥을 부술 때마다 빨간 하트를 반 칸 회복합니다."],
    8: ["지나간 자리에 초당 6의 피해를 주는 독 장판이 깔립니다."],
    9: ["날 수 있게 됩니다.", "블랙하트를 2개 얻습니다."],
    10: ["날 수 있게 됩니다.", "소울하트를 3개 얻습니다."],
    11: ["거지 패밀리어 셋이 보상을 두 배로 주는 슈퍼 거지 하나로 합쳐집니다."],
    12: ["약 25% 확률로 눈물이 하나 더 나갑니다."],
    13: ["적에게 무작위 상태 이상을 거는 거미 패밀리어가 따라다닙니다."],
    14: ["↑ 최대 체력 +1"],
    15: ["몸집이 커집니다.", "피격 시 일정 확률로 주변에 충격파가 퍼집니다.",
         "걸어다니는 것만으로 장애물을 부숩니다."],
}


# 게임은 변신을 아이템 태그로 판정한다. items_metadata.xml 의 tags 가 곧 세트 명단이다.
# EID 도 표를 들고 있지만 ab+/rep 두 층으로 나뉘고, ab+ 에는 애프터버스+ 시절 배정이 남아 있다
# (수호천사는 그때 세라핌이었지만 리펜턴스에서 샴쌍둥이로 옮겨졌다).
# 게임 파일을 기준으로 삼으면 우리가 쓰는 판(v1.7.9b)과 언제나 맞는다.
TRANSFORM_TAG = {
    1: "guppy", 2: "mushroom", 3: "fly", 4: "baby", 5: "syringe", 6: "mom",
    7: "poop", 8: "bob", 9: "devil", 10: "angel", 12: "book", 13: "spider",
}
# 태그가 없어 게임이 따로 처리하는 변신. 이건 EID 표에서 가져온다.
# 11 슈퍼 거지(거지 패밀리어 셋) · 14 성인(알약만) · 15 쿵쿵이(아이템 둘 + 알약)
TRANSFORM_UNTAGGED = (11, 14, 15)


def _eid_assignments():
    """EID 표에서 {변신번호: {'items': {아이템id}, 'other': 개수}} 를 읽는다."""
    text = read("transformations.lua")
    out = {}
    for kind, entry_id, value in re.findall(
            r'\["5\.(\d+)\.(\d+)"\]\s*=\s*"([^"]+)"', text):
        for one in value.split(","):
            one = one.strip()
            if not one.isdigit() or int(one) not in TRANSFORM_KO:
                continue
            slot = out.setdefault(int(one), {"items": set(), "other": 0})
            if kind == "100":
                slot["items"].add(int(entry_id))
            else:
                slot["other"] += 1
    return out


def _members():
    """{변신번호: {'items': {아이템id}, 'other': 개수}} 를 만든다."""
    meta = read("items_metadata.xml")
    tags = {int(i): set(t.split())
            for i, t in re.findall(r'<item id="(\d+)"[^>]*\btags="([^"]*)"', meta)}
    eid = _eid_assignments()
    out = {}
    for number, tag in TRANSFORM_TAG.items():
        out[number] = {"items": {i for i, t in tags.items() if tag in t}, "other": 0}
    for number in TRANSFORM_UNTAGGED:
        slot = eid.get(number, {"items": set(), "other": 0})
        out[number] = {"items": set(slot["items"]), "other": slot["other"]}
    return out


def transformation_drift():
    """게임 태그와 EID 표가 어긋나는 곳을 알려 준다. 한쪽이 갱신되면 여기서 먼저 드러난다."""
    eid = _eid_assignments()
    members = _members()
    report = []
    for number in TRANSFORM_TAG:
        mine = members[number]["items"]
        theirs = eid.get(number, {"items": set()})["items"]
        if theirs - mine or mine - theirs:
            report.append((TRANSFORM_KO[number], sorted(theirs - mine), sorted(mine - theirs)))
    return report


def load_transformations():
    """{아이템id: [{'ko','en'}, ...]} 를 돌려준다."""
    out = {}
    for number, slot in _members().items():
        for item_id in slot["items"]:
            out.setdefault(item_id, []).append(
                {"ko": TRANSFORM_KO[number], "en": TRANSFORM_EN[number]})
    order = {TRANSFORM_KO[n]: n for n in TRANSFORM_KO}
    for names in out.values():
        names.sort(key=lambda x: order[x["ko"]])   # 화면에 늘 같은 차례로 나오게
    return out


def load_transformation_stats():
    """{한글이름: {'en', 'items', 'other'}} 를 돌려준다.

    변신은 아이템만으로 채워지지 않는 것도 있다. 스톰피는 아이템 2개에 알약 1개가 붙고,
    어덜트는 알약만으로 된다. 화면에 "2개 중 3개를 모으면" 이라고 적히지 않게
    아이템 밖의 구성원 수도 세어 둔다.
    """
    stats = {}
    for number, slot in _members().items():
        stats[TRANSFORM_KO[number]] = {
            "en": TRANSFORM_EN[number],
            "items": len(slot["items"]),
            "other": slot["other"],
            "effect": TRANSFORM_EFFECT.get(number, []),
        }
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
    missing = [TRANSFORM_KO[i] for i in TRANSFORM_KO if not TRANSFORM_EFFECT.get(i)]
    print(f"효과 설명 없는 변신: {missing or '없음'}")
    drift = transformation_drift()
    if drift:
        print("게임 태그와 EID 표가 다른 곳 (태그를 따름):")
        for ko, only_eid, only_tag in drift:
            print(f"  {ko}: EID 에만 {only_eid} / 태그에만 {only_tag}")
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
