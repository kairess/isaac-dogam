/* 아이작 한글 도감 — 색깔로 묶고, 초성으로 찾는다. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const listEl = $("list");
  const chipsEl = $("chips");
  const emptyEl = $("empty");
  const searchEl = $("q");
  const clearEl = $("clear");
  const sheetEl = $("sheet");
  const backdropEl = $("backdrop");

  const KIND_KO = { item: "아이템", trinket: "장신구", card: "카드" };
  // 등급이 높을수록 밝은 금색으로. 게임 안에서 강한 아이템을 고를 때 쓰는 눈금이다.
  const QUALITY_HEX = ["#7b8291", "#5d8ac0", "#4fa06a", "#c9903a", "#e0c04a"];

  let DATA = null;
  let cards = [];          // {entry, node, section} — 화면에 올려둔 카드
  let sections = new Map(); // 색깔 -> {el, countEl, cards}
  let state = { color: "all", kind: "all", quality: "all", query: "" };

  /* ---------- 초성 검색 ----------
     한국어 사용자는 'ㅅㅍㅇㅍ' 처럼 초성만 두들겨 찾는 데 익숙하다.
     한글 음절은 유니코드에서 (초성 * 588) 규칙으로 배열돼 있어 산술로 뽑을 수 있다. */

  const CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
  ];

  function chosung(text) {
    let out = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0);
      out += code >= 0xac00 && code <= 0xd7a3
        ? CHO[Math.floor((code - 0xac00) / 588)]
        : ch;
    }
    return out;
  }

  const squeeze = (text) => text.replace(/\s+/g, "").toLowerCase();

  /* ---------- 자료 준비 ---------- */

  function indexEntry(entry) {
    entry._ko = squeeze(entry.ko);
    entry._en = squeeze(entry.en);
    entry._desc = squeeze(entry.desc.join(" "));
    entry._cho = squeeze(chosung(entry.ko));
    // 등장 장소와 등급도 검색으로 걸리게 해 둔다. "천사방", "등급4", "q4" 가 모두 통한다.
    const extras = (entry.pools || []).join(" ")
      + (entry.quality === undefined ? "" : ` 등급${entry.quality} q${entry.quality}`);
    entry._extra = squeeze(extras) + squeeze(chosung(extras));
    return entry;
  }

  function matches(entry) {
    if (state.kind !== "all" && entry.kind !== state.kind) return false;
    if (state.color !== "all" && entry.color !== state.color) return false;
    if (state.quality !== "all" && String(entry.quality) !== state.quality) return false;
    const q = state.query;
    if (!q) return true;
    return entry._ko.includes(q) || entry._en.includes(q) || entry._cho.includes(q)
        || entry._desc.includes(q) || entry._extra.includes(q);
  }

  /* ---------- 그리기 ---------- */

  /* 스프라이트 칸 번호만 넘긴다. 실제 픽셀 위치는 CSS 가 --cell 을 보고 계산한다. */
  function placeIcon(node, entry) {
    const { cols } = DATA.sprite;
    node.style.setProperty("--sx", entry.idx % cols);
    node.style.setProperty("--sy", Math.floor(entry.idx / cols));
  }

  function build() {
    const byColor = new Map(DATA.buckets.map((b) => [b.key, []]));
    for (const entry of DATA.entries) byColor.get(entry.color).push(entry);

    const frag = document.createDocumentFragment();
    for (const bucket of DATA.buckets) {
      const group = byColor.get(bucket.key);
      if (!group.length) continue;

      const section = document.createElement("section");
      section.dataset.color = bucket.key;
      const heading = document.createElement("h2");
      heading.innerHTML = `${bucket.emoji} ${bucket.ko} <span class="n"></span>`;
      const grid = document.createElement("div");
      grid.className = "grid";

      const nodes = [];
      for (const entry of group) {
        const button = document.createElement("button");
        button.type = "button";
        button.title = entry.ko;
        const icon = document.createElement("span");
        icon.className = "icon";
        placeIcon(icon, entry);
        button.append(icon);
        button.addEventListener("click", () => open(entry));
        grid.append(button);
        nodes.push(button);
        cards.push({ entry, node: button });
      }

      section.append(heading, grid);
      frag.append(section);
      sections.set(bucket.key, { el: section, countEl: heading.querySelector(".n"), nodes, group });
    }
    listEl.append(frag);
  }

  function buildChips() {
    const counts = new Map();
    for (const entry of DATA.entries) {
      counts.set(entry.color, (counts.get(entry.color) || 0) + 1);
    }
    const make = (key, label, dot, count) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.color = key;
      button.innerHTML =
        (dot ? `<span class="dot" style="background:${dot}"></span>` : "") +
        `${label}<span class="n">${count}</span>`;
      button.addEventListener("click", () => setColor(key));
      chipsEl.append(button);
    };
    make("all", "전체", "", DATA.entries.length);
    // 칩의 점 색은 그 묶음의 실제 대표색 평균이라, 화면 색과 아이콘 색이 따로 놀지 않는다.
    for (const bucket of DATA.buckets) {
      const group = DATA.entries.filter((e) => e.color === bucket.key);
      if (!group.length) continue;
      make(bucket.key, bucket.ko, averageHex(group), group.length);
    }
  }

  function buildQualityChips() {
    const counts = new Map();
    for (const entry of DATA.entries) {
      if (entry.quality === undefined) continue;
      counts.set(entry.quality, (counts.get(entry.quality) || 0) + 1);
    }
    const wrap = $("quals");
    const make = (key, label, dot, count) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.quality = key;
      button.innerHTML =
        (dot ? `<span class="dot" style="background:${dot}"></span>` : "") +
        `${label}<span class="n">${count}</span>`;
      button.addEventListener("click", () => {
        // 같은 등급을 다시 누르면 등급 조건을 푼다. 칸을 따로 두지 않아도 되게.
        state.quality = state.quality === key ? "all" : key;
        apply();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      wrap.append(button);
    };
    make("all", "등급 전체", "", DATA.entries.filter((e) => e.quality !== undefined).length);
    for (const q of [...counts.keys()].sort((a, b) => b - a)) {
      make(String(q), `Q${q}`, QUALITY_HEX[q], counts.get(q));
    }
  }

  function averageHex(group) {
    let r = 0, g = 0, b = 0;
    for (const entry of group) {
      r += parseInt(entry.hex.slice(1, 3), 16);
      g += parseInt(entry.hex.slice(3, 5), 16);
      b += parseInt(entry.hex.slice(5, 7), 16);
    }
    const n = group.length;
    const hex = (v) => Math.round(v / n).toString(16).padStart(2, "0");
    return `#${hex(r)}${hex(g)}${hex(b)}`;
  }

  /* ---------- 걸러내기 ---------- */

  function apply() {
    let shown = 0;
    for (const { entry, node } of cards) {
      const ok = matches(entry);
      node.hidden = !ok;
      if (ok) shown++;
    }
    for (const [key, section] of sections) {
      const visible = section.nodes.reduce((n, node) => n + (node.hidden ? 0 : 1), 0);
      section.el.hidden = visible === 0;
      section.countEl.textContent = visible;
    }
    emptyEl.hidden = shown > 0;

    for (const button of chipsEl.children) {
      button.classList.toggle("on", button.dataset.color === state.color);
    }
    for (const button of $("quals").children) {
      button.classList.toggle("on", button.dataset.quality === state.quality);
    }
    // 등급은 아이템에만 있다. 장신구·카드만 보는 중이면 등급 줄을 접어 둔다.
    $("quals").hidden = state.kind === "trinket" || state.kind === "card";
    for (const button of document.querySelectorAll(".seg button")) {
      button.classList.toggle("on", button.dataset.kind === state.kind);
    }
    clearEl.hidden = !state.query;
  }

  function setColor(key) {
    state.color = key;
    apply();
    writeHash();
    // 고른 색 구간이 화면 위로 오게 한다. 칩만 눌러도 바로 보이도록.
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- 상세 시트 ---------- */

  let lastFocused = null;

  function open(entry) {
    lastFocused = document.activeElement;
    placeIcon($("sheet-icon"), entry);

    $("sheet-name").textContent = entry.ko;
    $("sheet-en").textContent = entry.en;
    $("sheet-kind").textContent = KIND_KO[entry.kind];
    $("sheet-id").textContent = `ID ${entry.id}`;
    const bucket = DATA.buckets.find((b) => b.key === entry.color);
    $("sheet-color").textContent = `${bucket.emoji} ${bucket.ko}`;

    const qualityEl = $("sheet-quality");
    qualityEl.hidden = entry.quality === undefined;
    if (entry.quality !== undefined) {
      qualityEl.textContent = `등급 ${entry.quality}`;
      qualityEl.style.color = QUALITY_HEX[entry.quality];
      qualityEl.style.borderColor = QUALITY_HEX[entry.quality] + "66";
    }

    const poolsEl = $("sheet-pools");
    const poolList = $("sheet-pool-list");
    poolList.textContent = "";
    poolsEl.hidden = !entry.pools;
    for (const name of entry.pools || []) {
      const span = document.createElement("span");
      span.textContent = name;
      // 그리드 모드는 별도 모드라 눈에 덜 띄게 둔다.
      if (name.startsWith("그리드")) span.className = "greed";
      poolList.append(span);
    }

    const ul = $("sheet-desc");
    ul.textContent = "";
    for (const line of entry.desc) {
      const li = document.createElement("li");
      li.textContent = line;
      if (line.startsWith("↑")) li.className = "up";
      else if (line.startsWith("↓")) li.className = "down";
      ul.append(li);
    }
    if (!entry.desc.length) {
      const li = document.createElement("li");
      li.textContent = "설명이 아직 없습니다.";
      ul.append(li);
    }

    sheetEl.hidden = false;
    backdropEl.hidden = false;
    document.body.style.overflow = "hidden";
    $("sheet-close").focus();
    writeHash(entry);
  }

  function close() {
    if (sheetEl.hidden) return;
    sheetEl.hidden = true;
    backdropEl.hidden = true;
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
    writeHash();
  }

  /* ---------- 주소창에 상태 남기기 ----------
     색깔이나 아이템을 골랐을 때 주소가 바뀌면 링크로 공유할 수 있고,
     폰의 뒤로가기가 시트 닫기로 자연스럽게 이어진다. */

  let ignoreHash = false;

  function writeHash(entry) {
    const parts = [];
    if (entry) parts.push(`i=${entry.kind}:${entry.id}`);
    else if (state.color !== "all") parts.push(`c=${state.color}`);
    const hash = parts.length ? `#${parts.join("&")}` : " ";
    ignoreHash = true;
    if (entry) history.pushState(null, "", hash);
    else history.replaceState(null, "", hash);
    setTimeout(() => { ignoreHash = false; }, 0);
  }

  function readHash() {
    if (ignoreHash) return;
    const params = new URLSearchParams(location.hash.slice(1));
    const target = params.get("i");
    if (target) {
      const [kind, id] = target.split(":");
      const entry = DATA.entries.find((e) => e.kind === kind && String(e.id) === id);
      if (entry) { open(entry); return; }
    }
    close();
    const color = params.get("c");
    if (color && (color === "all" || DATA.buckets.some((b) => b.key === color))) {
      state.color = color;
      apply();
    }
  }

  /* ---------- 이벤트 ---------- */

  function wire() {
    let timer = 0;
    searchEl.addEventListener("input", () => {
      clearTimeout(timer);
      // 909개를 매 글자마다 훑으면 입력이 밀린다. 잠깐 모았다 한 번에 거른다.
      timer = setTimeout(() => {
        state.query = squeeze(searchEl.value);
        apply();
      }, 90);
    });
    clearEl.addEventListener("click", () => {
      searchEl.value = "";
      state.query = "";
      apply();
      searchEl.focus();
    });
    for (const button of document.querySelectorAll(".seg button")) {
      button.addEventListener("click", () => {
        state.kind = button.dataset.kind;
        apply();
      });
    }
    backdropEl.addEventListener("click", close);
    $("sheet-close").addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
      if (event.key === "/" && document.activeElement !== searchEl) {
        event.preventDefault();
        searchEl.focus();
      }
    });
    window.addEventListener("hashchange", readHash);
  }

  /* ---------- 시작 ---------- */

  fetch("assets/data/items.json")
    .then((response) => {
      if (!response.ok) throw new Error(response.status);
      return response.json();
    })
    .then((data) => {
      DATA = data;
      DATA.entries.forEach(indexEntry);
      document.documentElement.style.setProperty("--sprite-cols", DATA.sprite.cols);
      buildChips();
      buildQualityChips();
      build();
      wire();
      apply();
      readHash();
      const stamp = $("stamp");
      if (stamp) {
        const count = (kind) => DATA.entries.filter((e) => e.kind === kind).length;
        stamp.textContent =
          `아이템 ${count("item")}개 · 장신구 ${count("trinket")}개 · ` +
          `카드 ${count("card")}개 · ${DATA.generated} 기준`;
      }
    })
    .catch((error) => {
      listEl.innerHTML =
        `<p style="color:#e5686d;padding:24px 0">자료를 읽지 못했습니다 (${error.message}).<br>` +
        `<code>python3 tools/build.py</code> 를 실행했는지 확인해 주세요.</p>`;
    });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();
