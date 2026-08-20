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
  const TYPE_KO = { active: "액티브", passive: "패시브", familiar: "패밀리어" };
  const CHARGE_KO = { timed: "시간 충전", special: "특수 충전" };
  // 등급이 높을수록 밝은 금색으로. 게임 안에서 강한 아이템을 고를 때 쓰는 눈금이다.
  const QUALITY_HEX = ["#7b8291", "#5d8ac0", "#4fa06a", "#c9903a", "#e0c04a"];

  let DATA = null;
  let cards = [];          // {entry, node, section} — 화면에 올려둔 카드
  let sections = new Map(); // 색깔 -> {el, countEl, cards}
  let state = { color: "all", kind: "all", quality: "all", query: "" };
  let setMembers = new Map();   // 세트 이름 -> 그 세트에 드는 항목들

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
    // 등장 장소·등급·종류도 검색으로 걸리게 해 둔다.
    // "천사방", "등급4", "q4", "액티브" 가 모두 통한다.
    const extras = (entry.pools || []).join(" ")
      + (entry.quality === undefined ? "" : ` 등급${entry.quality} q${entry.quality}`)
      + (entry.type ? " " + TYPE_KO[entry.type] : "")
      // 패밀리어도 자리로 보면 패시브라 그 말로도 찾을 수 있어야 한다.
      + (entry.type === "familiar" ? " 패시브" : "")
      + (entry.charge ? ` 충전${entry.charge}` : "")
      + (entry.sets || []).map((t) => ` ${t.ko} ${t.en} 변신 세트`).join("");
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

  function groupSets() {
    for (const entry of DATA.entries) {
      for (const one of entry.sets || []) {
        if (!setMembers.has(one.ko)) setMembers.set(one.ko, []);
        setMembers.get(one.ko).push(entry);
      }
    }
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

    /* 머리말 태그. 등급을 맨 앞에 두고, 그 다음이 액티브인지 패시브인지다.
       게임 중에 알고 싶은 순서가 그렇다. */
    const meta = $("sheet-meta");
    meta.textContent = "";
    const chip = (text, tone) => {
      const span = document.createElement("span");
      span.textContent = text;
      if (tone) span.className = tone;
      meta.append(span);
      return span;
    };

    if (entry.quality !== undefined) {
      const span = chip(`등급 ${entry.quality}`, "strong");
      span.style.color = QUALITY_HEX[entry.quality];
      span.style.borderColor = QUALITY_HEX[entry.quality] + "66";
    }

    if (entry.type) {
      // 패밀리어는 패시브 자리에 붙는 동료다. 둘 다 적어야 오해가 없다.
      const passive = entry.type !== "active";
      chip(passive ? "패시브" : "액티브", entry.type === "active" ? "active" : null);
      if (entry.type === "familiar") chip(TYPE_KO.familiar);
      if (entry.charge) chip(`충전 ${entry.charge}칸`, "active");
      else if (entry.chargetype && CHARGE_KO[entry.chargetype]) {
        chip(CHARGE_KO[entry.chargetype], "active");
      }
    } else {
      chip(KIND_KO[entry.kind]);
    }

    for (const one of entry.sets || []) chip(one.ko, "set");

    chip(`ID ${entry.id}`);
    const bucket = DATA.buckets.find((b) => b.key === entry.color);
    chip(`${bucket.emoji} ${bucket.ko}`);

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

    /* 같은 세트의 아이템을 아이콘으로 늘어놓는다.
       이름만 적어 두면 "그래서 뭘 더 먹어야 하는데" 가 남는다. */
    const setsEl = $("sheet-sets");
    setsEl.textContent = "";
    setsEl.hidden = !entry.sets;
    for (const one of entry.sets || []) {
      const members = setMembers.get(one.ko) || [];
      const info = (DATA.setInfo || {})[one.ko] || {};
      const need = DATA.setsNeeded;
      /* 스톰피처럼 아이템만으로는 수가 모자란 세트가 있다.
         "2개 중 3개를 모으면" 이라고 적히면 말이 안 되니 구성을 밝혀 준다. */
      const note = info.other
        ? `${need}개를 모으면 변신 · 아이템 ${info.items}개 + 알약 ${info.other}개`
        : `${members.length}개 중 ${need}개를 모으면 변신`;
      const box = document.createElement("div");
      const head = document.createElement("h3");
      head.innerHTML = `세트 · ${one.ko} <span>${one.en} · ${note}</span>`;
      box.append(head);

      /* 모으면 뭐가 좋은지가 사실 제일 궁금한 부분이다. */
      if (info.effect && info.effect.length) {
        const effects = document.createElement("ul");
        effects.className = "set-effect";
        for (const line of info.effect) {
          const li = document.createElement("li");
          li.textContent = line;
          if (line.startsWith("↑")) li.className = "up";
          else if (line.startsWith("↓")) li.className = "down";
          effects.append(li);
        }
        box.append(effects);
      }

      const row = document.createElement("div");
      row.className = "set-row";
      for (const member of members) {
        const button = document.createElement("button");
        button.type = "button";
        button.title = member.ko;
        button.className = member.id === entry.id && member.kind === entry.kind ? "self" : "";
        const icon = document.createElement("span");
        icon.className = "icon sm";
        placeIcon(icon, member);
        button.append(icon);
        button.addEventListener("click", () => open(member));
        row.append(button);
      }
      box.append(row);
      setsEl.append(box);
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

    resetDrag();
    sheetEl.hidden = false;
    backdropEl.hidden = false;
    sheetEl.scrollTop = 0;
    document.body.style.overflow = "hidden";
    $("sheet-close").focus();
    writeHash(entry);
  }

  function close() {
    if (sheetEl.hidden) return;
    sheetEl.hidden = true;
    backdropEl.hidden = true;
    resetDrag();
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
    writeHash();
  }

  /* ---------- 아래로 밀어서 닫기 ----------
     시트는 화면 아래에 붙어 있는데 닫는 자리(배경·손잡이)는 위에 있다.
     한 손으로 폰을 쥔 채 엄지를 위로 뻗는 게 은근히 번거롭다.
     손잡이가 이미 "잡아 끌 수 있게" 생겼으니 진짜로 끌리게 만든다.
     손가락을 따라 내려오다가, 충분히 내렸거나 툭 튕기면 닫힌다. */

  const wide = window.matchMedia("(min-width: 720px)");
  const CLOSE_DIST = 96;   // 이만큼 내리면 닫는다
  const CLOSE_FLICK = 0.5; // px/ms. 짧게 튕겨도 닫히게

  let drag = null;
  let dragged = false; // 방금 끝난 손짓이 끌기였는지 (손잡이 클릭과 구분)

  function resetDrag() {
    drag = null;
    sheetEl.classList.remove("dragging");
    sheetEl.style.transition = "";
    sheetEl.style.transform = "";
    backdropEl.style.transition = "";
    backdropEl.style.opacity = "";
  }

  function dragStart(event) {
    // 데스크톱은 Esc 와 배경 클릭이 이미 편하다. 마우스 드래그는 글자 선택을 방해한다.
    if (event.pointerType === "mouse" || wide.matches) return;
    // 손잡이는 언제나 끌 수 있고, 나머지 부분은 이미 맨 위까지 올라와 있을 때만.
    // 내용을 읽으려고 위로 올리는 손짓이 닫기로 오해받으면 안 된다.
    const fromGrab = event.target.closest(".grab");
    if (!fromGrab && sheetEl.scrollTop > 0) return;
    dragged = false;
    drag = {
      x: event.clientX, y: event.clientY, dy: 0, on: false, down: false,
      // 속도는 마지막 한 순간만 본다. 천천히 끌다가 마지막에 툭 튕기는
      // 손짓도 제대로 잡으려면 시작점부터의 평균으로는 안 된다.
      vy: event.clientY, vt: event.timeStamp,
    };
  }

  function dragMove(event) {
    if (!drag) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    drag.down = dy > 0; // touchmove 에서 브라우저 스크롤을 막을지 판단하는 근거

    if (!drag.on) {
      // 아래로 내려가는 손짓인지 확실해질 때까지 기다린다.
      if (dy < -6 || Math.abs(dx) > Math.abs(dy) + 4) { drag = null; return; }
      if (dy < 8) return;
      drag.on = true;
      dragged = true;
      sheetEl.classList.add("dragging");
      sheetEl.style.transition = "none";
      backdropEl.style.transition = "none";
      try { sheetEl.setPointerCapture(event.pointerId); } catch (_) {}
    }

    if (event.timeStamp - drag.vt > 60) { drag.vy = event.clientY; drag.vt = event.timeStamp; }
    drag.dy = dy > 0 ? dy : dy / 5; // 위로는 살짝만 따라와 고무줄처럼 버틴다
    sheetEl.style.transform = `translateY(${drag.dy}px)`;
    backdropEl.style.opacity = String(Math.max(0, 1 - drag.dy / 400));
  }

  function dragEnd(event) {
    if (!drag) return;
    const { on, dy, vy, vt } = drag;
    drag = null;
    if (!on) return;

    const speed = (event.clientY - vy) / Math.max(1, event.timeStamp - vt);
    sheetEl.classList.remove("dragging");

    if (dy > CLOSE_DIST || (speed > CLOSE_FLICK && dy > 24)) {
      // 손을 뗀 자리에서 그대로 미끄러져 내려가게 둔다. 툭 끊기면 어색하다.
      sheetEl.style.transition = "transform .16s ease-in";
      backdropEl.style.transition = "opacity .16s ease-in";
      sheetEl.style.transform = "translateY(100%)";
      backdropEl.style.opacity = "0";
      setTimeout(close, 150);
      return;
    }

    sheetEl.style.transition = "transform .2s cubic-bezier(.2, .8, .3, 1)";
    backdropEl.style.transition = "opacity .2s ease";
    sheetEl.style.transform = "";
    backdropEl.style.opacity = "";
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
    $("sheet-close").addEventListener("click", () => {
      // 끌어내리다 되돌아온 손짓이 클릭으로 새어 나오면 엉뚱하게 닫힌다.
      if (dragged) { dragged = false; return; }
      close();
    });
    sheetEl.addEventListener("pointerdown", dragStart);
    sheetEl.addEventListener("pointermove", dragMove);
    /* pointermove 를 막아 봐야 스크롤은 안 멈춘다. 브라우저가 손짓을 스크롤로
       가져가 버리면 pointercancel 이 날아오고 끌기가 중간에 끊긴다.
       실제로 스크롤을 붙잡아 두는 건 touchmove 쪽이다. */
    sheetEl.addEventListener("touchmove", (event) => {
      if (drag && drag.down && event.cancelable) event.preventDefault();
    }, { passive: false });
    sheetEl.addEventListener("pointerup", dragEnd);
    sheetEl.addEventListener("pointercancel", () => { drag = null; resetDrag(); });
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
      groupSets();
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
