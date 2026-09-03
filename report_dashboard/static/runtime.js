/* report_dashboard/static/runtime.js — 리포트 iframe 런타임 (스펙 v4 §5·§6).
   순수 함수(RT.*)는 Python 정본과 같은 답을 내야 한다: reporting.delta_over_days,
   report_common.sorted_content_rows, reporting.average_participation_rate. */
(function (root) {
  function combineSeries(dates, byChannel, on) {
    const sel = on instanceof Set ? on : new Set(on);
    return dates.map((_, i) => Object.keys(byChannel).reduce((acc, ch) => acc + (sel.has(ch) ? (byChannel[ch][i] || 0) : 0), 0));
  }
  function dayNum(iso) { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d) / 86400000; }
  function deltaOverDays(dates, values, days = 7) {
    if (dates.length < 2) return null;
    const lastI = dates.length - 1, cutoff = dayNum(dates[lastI]) - days;
    let base = -1;
    for (let i = 0; i < lastI; i++) if (dayNum(dates[i]) <= cutoff) base = i;
    if (base < 0) return null;
    return { delta: values[lastI] - values[base], span: dayNum(dates[lastI]) - dayNum(dates[base]) };
  }
  function orderRows(rows, sortKey) {
    const out = rows.slice();                          // 안정 정렬 2회: 부차 키 → 값0 맨 아래
    if (sortKey === "comments") out.sort((a, b) => b.comments - a.comments);
    else if (sortKey === "recent") out.sort((a, b) => (b.release || "").localeCompare(a.release || ""));
    else if (sortKey === "rate") out.sort((a, b) => (a.rate == null) - (b.rate == null) || ((b.rate || 0) - (a.rate || 0)));
    else out.sort((a, b) => b.pv - a.pv);
    out.sort((a, b) => Number(a.empty) - Number(b.empty));
    return out;
  }
  function avgRate(rates) {
    const xs = rates.filter((r) => r != null);
    return xs.length ? Math.round((xs.reduce((a, b) => a + b, 0) / xs.length) * 10) / 10 : null;
  }
  function fmtInt(n) { return Math.round(n).toLocaleString("en-US"); }
  /* Python 포맷 재현 — 서버가 그린 문자열과 한 글자도 달라지면 로드 직후 화면이 튄다.
     fmtG = `f"{x:g}"`(inline_bar 폭), pyRound = `round()`(짝수 반올림, 채널 분포 pct). */
  function fmtG(x) { return String(+x.toPrecision(6)); }
  /* charts.js는 라벨을 `innerHTML` 템플릿에 그대로 끼워 넣는다 — payload는 서버가 만들지만
     날짜 문자열이 그 경로로 마크업이 되는 걸 여기서 끊는다. 축 라벨은 `08.31`·`9.1` 같은
     숫자·점 조합뿐이므로 그 밖은 빈 문자열(= charts.js가 그 라벨을 건너뛴다). */
  function safeLabel(t) { return /^[\d.]{0,5}$/.test(String(t == null ? "" : t)) ? String(t == null ? "" : t) : ""; }
  function pyRound(x) { const f = Math.floor(x), d = x - f; return d > 0.5 ? f + 1 : d < 0.5 ? f : (f % 2 === 0 ? f : f + 1); }
  function deltaLabel(d, pointCount) {
    if (!d) return { text: `수집 ${pointCount}일차`, dir: "flat" };
    if (d.delta > 0) return { text: `+${fmtInt(d.delta)} · ${d.span}d`, dir: "up" };
    if (d.delta < 0) return { text: `${fmtInt(d.delta)} · ${d.span}d`, dir: "down" };
    return { text: `변동 없음 · ${d.span}d`, dir: "flat" };
  }
  // `_` 접두사는 "Python 정본이 아니라 포맷 재현용"이라는 뜻 — 노출은 node 테스트가 고정하기 위해서다.
  const RT = {
    combineSeries, deltaOverDays, orderRows, avgRate, fmtInt, deltaLabel,
    _fmtG: fmtG, _pyRound: pyRound, _safeLabel: safeLabel,
  };
  root.RT = RT;
  if (typeof root.document === "undefined" || !root.frameElement) return;   // node 테스트·단독 열기 경로
  /* ================= DOM 글루(스펙 §6) — 프레임 안에서만 실행된다 ================= */
  root.__glueRan = true;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.prototype.slice.call(r.querySelectorAll(s));
  const fe = root.frameElement;

  /* 높이: 부모 뷰포트 바닥까지 늘린다(스트림릿 iframe은 고정 height로 뜬다). */
  function fit() {
    try {
      const h = Math.max(320, root.parent.innerHeight - fe.getBoundingClientRect().top);
      fe.style.height = h + "px";
      fe.style.minHeight = "0";
    } catch (e) {}   // 부모 접근이 막히면 기본 높이로 둔다 — 나머지 글루는 계속 돈다
  }
  /* 테마: 부모 body 배경 밝기 → data-theme (v3 THEME_HOOK_HTML과 같은 공식). */
  function theme() {
    try {
      const m = root.parent.getComputedStyle(root.parent.document.body).backgroundColor.match(/\d+/g);
      if (!m || m.length < 3) return;
      const l = (0.2126 * +m[0] + 0.7152 * +m[1] + 0.0722 * +m[2]) / 255;
      const t = l < 0.5 ? "dark" : "light";
      if (document.documentElement.dataset.theme !== t) document.documentElement.dataset.theme = t;
    } catch (e) {}
  }
  fit();
  theme();

  /* 목업 CSS에 없던 규칙만 여기서 심는다(스펙 §4.1) — 꺼진 칩 무음 처리, 꺼진 채널의
     `.srow.ours` 강조 무력화, 그리고 `[hidden]`.

     `[hidden]`은 UA 스타일시트의 `display:none`이라 **author 스타일이면 무조건 진다** —
     목업 mix.css/page-exposure.css가 `.ch-row`·`.serp`·`.share-grid`에 `display:grid`를,
     테이블 행에 `display:table-row`를 직접 걸어두므로 `el.hidden = true`가 아무 효과가
     없었다(꺼진 채널 행·다른 키워드 SERP·가중 점유율 그리드가 그대로 보였다). 여기서
     `!important`로 한 번에 덮는다 — 요소 종류마다 규칙을 따로 쓰지 않는다. */
  const style = document.createElement("style");
  style.id = "rt-css";
  style.textContent =
    "[hidden]{display:none!important}" +
    " .chip[data-ch]:not(.on){color:var(--muted)} .chip[data-ch]:not(.on) .dot{opacity:.25}" +
    " .srow.ours.is-off{background:transparent;margin:0;padding-left:0;padding-right:0;border-bottom-color:var(--hair)}" +
    " .srow.ours.is-off .r,.srow.ours.is-off .t,.srow.ours.is-off .src{color:var(--ink-2);font-weight:500}" +
    " .beyond.is-off{opacity:.45} .detail.is-empty{position:static;padding-left:0;border-left:0}";
  document.head.appendChild(style);

  /* Python `ui.CHANNEL_LABEL`·`ui.empty_state(...)`와 문자 단위로 같아야 한다(파이썬 패리티 테스트가 고정). */
  const CH_LABEL = { instagram: "인스타그램", blog: "블로그", cafe: "카페", community: "커뮤니티", youtube: "유튜브" };
  const EMPTY_HERO = '<div class="empty"><b>추이를 그릴 데이터가 아직 부족합니다</b>수집일이 3일 이상 쌓이면 곡선이 나타납니다.</div>';
  const EMPTY_DETAIL = '<div class="empty"><b>표시할 콘텐츠가 없습니다</b>미수집 숨기기를 해제하면 다시 표시됩니다.</div>';
  const payload = (() => { try { return JSON.parse(($("#payload") || {}).textContent || "{}"); } catch (e) { return {}; } })();
  /* 초기 상태는 서버가 그린 마크업에서 읽는다 — 그래야 첫 applyState()가 화면을 바꾸지 않는다. */
  const pick = (sel, key, dflt) => { const el = $(sel); return el ? el.dataset[key] : dflt; };
  const state = {
    on: new Set($$(".chip[data-ch]").map((c) => c.dataset.ch)),
    sort: pick(".seg span.on[data-sort]", "sort", "value"),
    hideEmpty: !!$(".chip.on[data-toggle='hide-empty']"),
    kw: pick(".kw-chips .chip.on[data-kw]", "kw", null),
    variant: pick(".seg span.on[data-variant]", "variant", "slot"),
    basis: pick(".seg span.on[data-basis]", "basis", "count"),
    selected: pick("tr.is-sel[data-cid]", "cid", null),
  };
  let booted = false;                       // 첫 applyState()는 등장 모션을 다시 재생하지 않는다
  let shownDetail = $("#detail") ? state.selected : null;   // 서버가 이미 그려둔 상세

  function rowsOf(table) {
    return $$("tbody tr[data-cid]", table).map((tr) => ({
      tr, cid: tr.dataset.cid, ch: tr.dataset.ch, pv: +tr.dataset.pv, comments: +tr.dataset.comments,
      rate: tr.dataset.rate === "" ? null : +tr.dataset.rate, release: tr.dataset.release, empty: tr.dataset.empty === "1",
    }));
  }
  function reEnter(el) { if (!el) return; el.classList.remove("enter"); void el.offsetWidth; el.classList.add("enter"); }
  function setBars(rows) {
    const max = Math.max(1, ...rows.map((r) => r.pv));
    rows.forEach((r) => {
      const i = $(".inline-bar i", r.tr);
      if (i) i.style.width = RT._fmtG(Math.max(0, Math.min(100, r.pv / max * 100))) + "%";
    });
  }
  /* `[data-stat]` 안의 단위 `<small>`(건·%)을 **키 단위로** 보존한다 — 요소 단위로 첫 호출에
     캐시하면, 값이 없어 서버가 단위 없이 그린 칸(`평균 참여율 —`)이 "단위 없음"으로 굳어
     나중에 값이 생겨도 `%`를 되찾지 못한다. 단위를 실제로 본 순간에만 캐시를 갱신하므로
     첫 렌더는 그대로다(서버가 그린 `<small>`을 떼고 같은 것을 다시 붙인다). */
  const units = new Map();
  function put(key, text, hasValue) {
    $$('[data-stat="' + key + '"]').forEach((el) => {
      const s = el.querySelector("small");
      if (s) units.set(key, s.cloneNode(true));
      el.textContent = text;
      const u = units.get(key);
      if (u && hasValue !== false) el.appendChild(u.cloneNode(true));
    });
  }
  function putMeta(key, text) { $$('[data-meta="' + key + '"]').forEach((el) => (el.textContent = text)); }

  /* 선택만 바뀌는 경로(행 클릭) — 스트립 등장 모션·차트 재렌더까지 다시 돌릴 이유가 없다.
     `#detail`은 `.detail`이고 template 안에도 `<aside class="detail">`가 통째로 들어 있으므로
     **안쪽 내용만** 옮긴다(그대로 넣으면 `.detail`이 중첩돼 패널이 40px 밀린다). */
  function applySelection() {
    $$(".list tbody tr[data-cid]").forEach((tr) => tr.classList.toggle("is-sel", tr.dataset.cid === state.selected));
    const aside = $("#detail");
    if (!aside || state.selected === shownDetail) return;
    const t = $$("template[data-detail]").filter((x) => x.dataset.detail === state.selected)[0];
    const src = t && (t.content.querySelector(".detail") || t.content.firstElementChild);
    aside.innerHTML = src ? src.innerHTML : EMPTY_DETAIL;
    aside.classList.toggle("is-empty", !src);   // 빈 상태는 sticky·왼쪽 헤어라인·패딩을 뗀다
    shownDetail = state.selected;
    reEnter(aside);
  }

  function applyState() {
    $$(".chip[data-ch]").forEach((c) => c.classList.toggle("on", state.on.has(c.dataset.ch)));
    /* --- 표: 요약 상위 8(tbl-perf) / 콘텐츠 성과 리스트(.list table) --- */
    const perf = $("table.tbl-perf"), list = $(".list table");
    let metaRows = null;
    if (perf) {
      const rows = rowsOf(perf), vis = rows.filter((r) => state.on.has(r.ch));
      rows.forEach((r) => (r.tr.hidden = true));
      vis.slice(0, 8).forEach((r) => (r.tr.hidden = false));
      setBars(vis.slice(0, 8));
      metaRows = vis;                       // 합계는 상위 8이 아니라 보이는 채널 전체 기준
    }
    if (list) {
      const rows = rowsOf(list);
      const vis = RT.orderRows(rows.filter((r) => state.on.has(r.ch) && !(state.hideEmpty && r.empty)), state.sort);
      const tb = $("tbody", list);
      rows.forEach((r) => (r.tr.hidden = true));
      vis.forEach((r) => { r.tr.hidden = false; tb.appendChild(r.tr); });
      setBars(vis);
      if (!vis.some((r) => r.cid === state.selected)) state.selected = vis.length ? vis[0].cid : null;
      applySelection();
      const hint = $("[data-hint]");
      if (hint) hint.textContent = state.hideEmpty ? "빈 데이터 숨김" : "데이터 없는 콘텐츠는 맨 아래";
      $$(".seg span[data-sort]").forEach((s) => s.classList.toggle("on", s.dataset.sort === state.sort));
      const he = $(".chip[data-toggle='hide-empty']");
      if (he) he.classList.toggle("on", state.hideEmpty);
      metaRows = vis;
    }
    /* --- 스트립·제목 메타 재계산(보이는 행 기준) --- */
    if (metaRows) {
      const nonIg = metaRows.filter((r) => r.ch !== "instagram"), ig = metaRows.filter((r) => r.ch === "instagram");
      put("contents", String(metaRows.length));                                  // Python도 콤마 없이 그린다
      put("views", RT.fmtInt(nonIg.reduce((a, r) => a + r.pv, 0)));
      put("likes", RT.fmtInt(ig.reduce((a, r) => a + r.pv, 0)));
      put("comments", String(metaRows.reduce((a, r) => a + r.comments, 0)));
      const ar = RT.avgRate(metaRows.map((r) => r.rate));
      put("rate", ar == null ? "—" : ar.toFixed(1), ar != null);                  // 없으면 단위 `%`도 떼야 한다
      putMeta("contents", String(metaRows.length));
      putMeta("channels", String(new Set(metaRows.map((r) => r.ch)).size));
      const bc = $('[data-meta="by-channel"]');
      if (bc) {
        const cnt = {};
        metaRows.forEach((r) => (cnt[r.ch] = (cnt[r.ch] || 0) + 1));
        bc.textContent = Object.keys(cnt).map((c) => [c, cnt[c]]).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
          .map((e) => (CH_LABEL[e[0]] || e[0]) + " " + e[1]).join(" · ");
      }
      if (booted) reEnter($(".strip"));
    }
    /* --- 채널 분포(요약, data-n 있음) · 채널별 네이버 노출(상위노출, data-n 없음) --- */
    const chRows = $$(".ch-row[data-ch]");
    if (chRows.length) {
      chRows.forEach((r) => (r.hidden = !state.on.has(r.dataset.ch)));
      const vis = chRows.filter((r) => state.on.has(r.dataset.ch));
      if (vis.length && vis.every((r) => r.dataset.n !== undefined)) {
        const tot = vis.reduce((a, r) => a + +r.dataset.n, 0) || 1;
        vis.forEach((r) => {
          const p = RT._pyRound(+r.dataset.n / tot * 100);
          const bar = $(".hbar i", r);
          if (bar) bar.style.width = p + "%";
          const small = $(".v small", r);
          if (small) small.textContent = p + "%";
        });
      }
    }
    /* --- 상위노출: 키워드 칩 · 점유율 변형 · 파급력 기준 · 꺼진 채널의 ours 강조 --- */
    $$(".kw-chips .chip[data-kw]").forEach((c) => c.classList.toggle("on", c.dataset.kw === state.kw));
    $$(".serp[data-kw]").forEach((b) => (b.hidden = b.dataset.kw !== state.kw));
    $$("[data-variant]").forEach((el) => {
      if (el.matches(".seg span")) el.classList.toggle("on", el.dataset.variant === state.variant);
      else el.hidden = el.dataset.variant !== state.variant;
    });
    $$("[data-basis]").forEach((el) => {
      if (el.matches(".seg span")) el.classList.toggle("on", el.dataset.basis === state.basis);
      else el.hidden = el.dataset.basis !== state.basis;
    });
    $$(".srow.ours[data-ch], .beyond[data-ch]").forEach((el) => el.classList.toggle("is-off", !state.on.has(el.dataset.ch)));
    renderCharts();
  }

  /* payload 모양은 페이지마다 다르다 — 요약 `{dates, by_channel}`(조회수 한 벌),
     콘텐츠 성과 `{views: {...}, likes: {...}}`. 상위노출은 payload 자체가 없다. */
  function series(kind) {
    const s = payload.series;
    if (!s) return null;
    if (s.dates) return kind === "views" ? s : null;
    return s[kind] || null;
  }
  function renderCharts() {
    const hero = $('[data-chart="hero"]'), sv = series("views");
    if (hero && sv) {
      const vals = RT.combineSeries(sv.dates, sv.by_channel, state.on);
      if (vals.length >= 3 && root.areaChart) {
        root.areaChart(hero, vals, {
          w: 1140, h: 230, ink: true, padR: 64,
          labels: sv.dates.map((d) => RT._safeLabel(d.slice(5).replace("-", "."))),
        });
      } else if (vals.length < 3) {
        hero.innerHTML = EMPTY_HERO;      // 남은 SVG를 두면 꺼진 채널의 곡선이 화면에 남는다(스펙 §4.2)
      }
    }
    [["views", sv], ["likes", series("likes")]].forEach((pair) => {
      const k = pair[0], s = pair[1];
      if (!s) return;
      const vals = RT.combineSeries(s.dates, s.by_channel, state.on);
      const box = $('[data-spark="' + k + '"]');
      if (box) {
        if (vals.length >= 2 && root.sparkline) root.sparkline(box, vals, { ink: true, w: 112, h: 30 });
        else if (vals.length < 2) box.innerHTML = "";
      }
      const d = $('[data-delta="' + k + '"]');
      if (d) {
        const lab = RT.deltaLabel(RT.deltaOverDays(s.dates, vals, 7), vals.length);
        d.textContent = lab.text;
        d.className = "delta " + lab.dir;
      }
    });
  }

  function bindControls() {
    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!t || !t.closest) return;
      const chip = t.closest(".chip[data-ch]");
      if (chip) {
        const ch = chip.dataset.ch;
        if (state.on.has(ch)) { if (state.on.size > 1) state.on.delete(ch); }   // 마지막 하나는 끌 수 없다(§4.1)
        else state.on.add(ch);
        return applyState();
      }
      const sort = t.closest(".seg span[data-sort]");
      if (sort) { state.sort = sort.dataset.sort; return applyState(); }
      if (t.closest(".chip[data-toggle='hide-empty']")) { state.hideEmpty = !state.hideEmpty; return applyState(); }
      const kw = t.closest(".kw-chips .chip[data-kw]");
      if (kw) { state.kw = kw.dataset.kw; return applyState(); }
      const v = t.closest(".seg span[data-variant]");
      if (v) { state.variant = v.dataset.variant; return applyState(); }
      const b = t.closest(".seg span[data-basis]");
      if (b) { state.basis = b.dataset.basis; return applyState(); }
      const tr = t.closest(".list tbody tr[data-cid]");
      if (tr) {
        if (tr.dataset.cid === state.selected) return;
        state.selected = tr.dataset.cid;
        return applySelection();
      }
      const nav = t.closest("a[data-nav]");
      if (nav) {
        e.preventDefault();
        const name = nav.dataset.nav;
        try {
          const a = $$('a[data-testid="stPageLink-NavLink"]', root.parent.document)
            .filter((x) => (x.innerText || "").trim() === name)[0];
          if (a) a.click();
          else root.parent.location.href = "/" + encodeURIComponent(name.replace(/\s+/g, ""));
        } catch (err) {}
        return;
      }
      const ex = t.closest("[data-export]");
      if (ex && !ex.hasAttribute("aria-disabled")) {
        const md = $("#export-md");
        if (!md) return;
        // frame.py가 `</`를 `<\/`로 막아 심었으므로 되돌린다.
        const blob = new Blob([md.textContent.replace(/<\\\//g, "</")], { type: "text/markdown;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = md.dataset.filename || "리포트.md";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      }
    });
  }

  bindControls();
  applyState();
  booted = true;
  /* 스트림릿 레이아웃이 늦게 자리를 잡으므로 높이를 몇 번 더 맞춘다(스펙 §6). */
  root.addEventListener("load", fit);
  try { root.parent.addEventListener("resize", fit); } catch (e) {}
  setTimeout(fit, 500);
  setTimeout(fit, 1500);
  setInterval(theme, 400);
})(typeof window !== "undefined" ? window : globalThis);
