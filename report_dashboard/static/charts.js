/* 시안용 경량 SVG 차트 헬퍼 — 실제 구현은 report_common.py의 SVG 생성기가 같은 스펙을 따른다.
   스펙(dataviz): 선 2px, 끝점 r>=4 + 2px 표면 링, 격자 헤어라인, 워시 10%. */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const fmt = (n) => n.toLocaleString("ko-KR");

  function pathFor(vals, w, h, padL, padR, padT, padB) {
    const min = Math.min(...vals), max = Math.max(...vals);
    const iw = w - padL - padR, ih = h - padT - padB;
    const x = (i) => padL + (iw * i) / (vals.length - 1);
    const y = (v) => padT + ih - ((v - min) / ((max - min) || 1)) * ih;
    const p2 = vals.map((v, i) => [x(i), y(v)]);
    let d = "";
    p2.forEach(([px, py], i) => { d += (i ? " L" : "M") + px.toFixed(1) + " " + py.toFixed(1); });
    return { d, pts: p2, x, y, min, max };
  }

  function pathLength(d) {
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    const p = document.createElementNS(svgNS, "path");
    p.setAttribute("d", d); svg.appendChild(p); document.body.appendChild(svg);
    const L = p.getTotalLength(); svg.remove(); return L;
  }

  /* 영역 차트: 격자 3줄 + 워시 + 선 + 끝점 + 끝값 라벨 */
  window.areaChart = function (el, vals, opt = {}) {
    const w = opt.w || 720, h = opt.h || 200, padL = 8, padR = opt.padR ?? 60, padT = 14, padB = opt.labels ? 26 : 10;
    const { d, pts, y, min, max } = pathFor(vals, w, h, padL, padR, padT, padB);
    const base = h - padB;
    const wash = d + ` L${pts[pts.length - 1][0].toFixed(1)} ${base} L${pts[0][0].toFixed(1)} ${base} Z`;
    const L = pathLength(d);
    const ink = opt.ink ? " ink" : "";
    const gridYs = [0.0, 0.5, 1.0].map((t) => padT + (base - padT) * t);
    const last = pts[pts.length - 1];
    let labels = "";
    if (opt.labels) {
      const step = Math.max(1, Math.round(vals.length / 5));
      opt.labels.forEach((t, i) => { const lastI = vals.length - 1; if (!t) return; if ((i % step === 0 && lastI - i >= step) || i === lastI) labels += `<text class="axis-t" x="${pts[i][0].toFixed(1)}" y="${h - 6}" text-anchor="${i === vals.length - 1 ? "end" : "middle"}">${t}</text>`; });
    }
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="aspect-ratio:${w}/${h}">
      ${gridYs.map((gy) => `<line class="grid-l" x1="${padL}" x2="${w - padR}" y1="${gy.toFixed(1)}" y2="${gy.toFixed(1)}"/>`).join("")}
      <text class="axis-t" x="${w - padR + 8}" y="${(padT + 4).toFixed(1)}">${fmt(max)}</text>
      <text class="axis-t" x="${w - padR + 8}" y="${(base + 3).toFixed(1)}">${fmt(min)}</text>
      <g class="fade-late"><path class="wash" d="${wash}"/></g>
      <path class="ln draw${ink}" d="${d}" stroke-dasharray="${L.toFixed(0)}" stroke-dashoffset="${L.toFixed(0)}"/>
      <circle class="end fade-late${ink}" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4.5"/>
      ${labels}
    </svg>`;
  };

  /* 스파크라인(카드 안 소형) */
  window.sparkline = function (el, vals, opt = {}) {
    const w = opt.w || 120, h = opt.h || 32;
    const { d, pts } = pathFor(vals, w, h, 2, 6, 4, 4);
    const last = pts[pts.length - 1];
    const L = pathLength(d);
    const ink = opt.ink ? " ink" : "";
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" style="aspect-ratio:${w}/${h}">
      <path class="ln draw${ink}" d="${d}" stroke-dasharray="${L.toFixed(0)}" stroke-dashoffset="${L.toFixed(0)}"/>
      <circle class="end fade-late${ink}" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4"/>
    </svg>`;
  };

  /* 순위 차트: 위가 1위. */
  window.rankChart = function (el, ranks, opt = {}) {
    const w = opt.w || 200, h = opt.h || 60;
    const inv = ranks.map((r) => -r);
    const { d, pts } = pathFor(inv, w, h, 4, 34, 8, 8);
    const last = pts[pts.length - 1];
    const L = pathLength(d);
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" style="aspect-ratio:${w}/${h}">
      <line class="grid-l" x1="4" x2="${w - 34}" y1="${last[1].toFixed(1)}" y2="${last[1].toFixed(1)}"/>
      <path class="ln draw" d="${d}" stroke-dasharray="${L.toFixed(0)}" stroke-dashoffset="${L.toFixed(0)}"/>
      <circle class="end fade-late" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4.5"/>
      <text class="lbl" x="${(last[0] + 10).toFixed(1)}" y="${(last[1] + 4).toFixed(1)}">${ranks[ranks.length - 1]}위</text>
    </svg>`;
  };

  /* 채널 분할 링 (도넛 대신: 2px 표면 갭이 있는 세그먼트) */
  window.ring = function (el, parts, opt = {}) {
    const size = opt.size || 120, sw = opt.sw || 12, r = (size - sw) / 2, c = size / 2;
    const total = parts.reduce((a, p) => a + p.v, 0);
    const C = 2 * Math.PI * r; let off = 0; let segs = "";
    parts.forEach((p) => {
      const len = (p.v / total) * C - 3;
      segs += `<circle r="${r}" cx="${c}" cy="${c}" fill="none" stroke="var(--ch-${p.k})" stroke-width="${sw}" stroke-dasharray="${len.toFixed(1)} ${(C - len).toFixed(1)}" stroke-dashoffset="${(-off).toFixed(1)}" transform="rotate(-90 ${c} ${c})" stroke-linecap="butt"/>`;
      off += (p.v / total) * C;
    });
    el.innerHTML = `<svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px">${segs}
      <text x="${c}" y="${c - 2}" text-anchor="middle" class="lbl" style="font-size:22px;font-weight:700">${total}</text>
      <text x="${c}" y="${c + 15}" text-anchor="middle" class="axis-t">${opt.unit || "건"}</text></svg>`;
  };

  /* 테마 토글 + ?theme= 강제 */
  const q = new URLSearchParams(location.search).get("theme");
  if (q === "dark" || q === "light") document.documentElement.dataset.theme = q;
  window.toggleTheme = function () {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
  };
})();
