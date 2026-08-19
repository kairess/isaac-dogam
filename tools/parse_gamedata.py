#!/usr/bin/env python3
"""게임 XML 에서 아이템 등급과 등장 장소를 읽는다.

등급(quality)과 아이템 풀은 EID 텍스트 팩에 없다. 게임이 resources 폴더에 들고 있는
items_metadata.xml / itempools.xml 이 원본이고, 그 사본을 tools/_cache/text/ 에 받아 둔다.

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
