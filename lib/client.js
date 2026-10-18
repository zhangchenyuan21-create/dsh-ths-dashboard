window.__ModuleLoader__.load({
  id: "dsh-ths-dashboard",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    const React = require("react");
    const h = React.createElement;
    const { useState, useEffect, useMemo, useCallback, useRef } = React;

    const PLUGIN_ID = "dsh-ths-dashboard";
    const PANEL_ID = "ths-sim-dashboard";
    const BACKTEST_PANEL_ID = "ths-backtest-replay";
    const API = "/ths-dashboard/api";
    const DIRECT_API = "http://127.0.0.1:8766/api";
    const PERIODS = [["1", "1分"], ["5", "5分"], ["15", "15分"], ["30", "30分"], ["60", "60分"], ["day", "日线"]];
    const UP = "#e5484d";
    const DOWN = "#16a34a";

    const CSS = `
.thsd-root{height:100%;min-height:0;overflow:auto;box-sizing:border-box;padding:16px 18px 30px;background:var(--dsw-alias-bg-layer-1,#111);color:var(--dsw-alias-label-primary,#e8e8e8);font-family:var(--ds-font-family-sans,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif);font-size:13px;line-height:1.45}
.thsd-head{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.thsd-title{font-size:18px;font-weight:650;letter-spacing:.2px}
.thsd-sub{color:var(--dsw-alias-label-tertiary,#8a8a8a);font-size:12px;margin-top:3px}
.thsd-head-actions{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.thsd-input{width:110px;height:31px;box-sizing:border-box;border:1px solid var(--dsw-alias-border-l3,#333);border-radius:7px;background:var(--dsw-alias-bg-layer-2,#1b1b1b);color:inherit;padding:0 9px;font:inherit;outline:none}
.thsd-input:focus{border-color:var(--dsw-alias-state-business-primary,#4d8dff)}
.thsd-btn{height:31px;box-sizing:border-box;border:1px solid var(--dsw-alias-border-l3,#333);border-radius:7px;background:var(--dsw-alias-button-elevated-fill,#1d1d1d);color:var(--dsw-alias-label-primary,#eee);padding:0 11px;font:inherit;cursor:pointer}
.thsd-btn:hover{background:var(--dsw-alias-interactive-bg-hover,#282828)}
.thsd-btn:disabled{opacity:.5;cursor:default}
.thsd-btn.primary{border-color:var(--dsw-alias-state-business-primary,#4d8dff);background:var(--dsw-alias-state-business-primary,#4d8dff);color:#fff}
.thsd-toggle{display:inline-flex;align-items:center;gap:5px;color:var(--dsw-alias-label-secondary,#aaa);font-size:12px;user-select:none}
.thsd-ok{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 3px rgba(34,197,94,.12)}
.thsd-warn-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.12)}
.thsd-bad-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;box-shadow:0 0 0 3px rgba(239,68,68,.12)}
.thsd-cards{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin-bottom:14px}
.thsd-card{border:1px solid var(--dsw-alias-border-l3,#333);border-radius:10px;background:var(--dsw-alias-bg-layer-2,#181818);padding:10px 12px;min-width:0}
.thsd-card-label{font-size:11px;color:var(--dsw-alias-label-tertiary,#888)}
.thsd-card-value{font-size:19px;font-weight:650;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.thsd-card-sub{font-size:11px;color:var(--dsw-alias-label-tertiary,#888);margin-top:2px}
.thsd-layout{display:grid;grid-template-columns:minmax(330px,0.8fr) minmax(0,1.9fr);gap:12px;align-items:start}
.thsd-panel{border:1px solid var(--dsw-alias-border-l3,#333);border-radius:11px;background:var(--dsw-alias-bg-layer-2,#171717);min-width:0}
.thsd-panel-head{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--dsw-alias-border-l3,#2a2a2a);min-height:20px}
.thsd-panel-title{font-size:13px;font-weight:620}
.thsd-panel-meta{margin-left:auto;color:var(--dsw-alias-label-tertiary,#888);font-size:11px}
.thsd-pos-wrap{overflow:auto;max-height:410px}
.thsd-table{width:100%;border-collapse:collapse;font-size:12px}
.thsd-table th{text-align:right;color:var(--dsw-alias-label-tertiary,#888);font-weight:500;padding:7px 8px;border-bottom:1px solid var(--dsw-alias-border-l3,#2a2a2a);position:sticky;top:0;background:var(--dsw-alias-bg-layer-2,#171717);z-index:1}
.thsd-table th:first-child,.thsd-table td:first-child{text-align:left}
.thsd-table td{text-align:right;padding:7px 8px;border-bottom:1px solid rgba(127,127,127,.10);white-space:nowrap;font-variant-numeric:tabular-nums}
.thsd-table tr.row{cursor:pointer}
.thsd-table tr.row:hover td{background:var(--dsw-alias-interactive-bg-hover,#232323)}
.thsd-table tr.selected td{background:rgba(77,141,255,.12)}
.thsd-code{color:var(--dsw-alias-label-tertiary,#8b8b8b);font-size:11px;margin-left:4px}
.thsd-up{color:${UP}}
.thsd-down{color:${DOWN}}
.thsd-empty{padding:28px 16px;text-align:center;color:var(--dsw-alias-label-tertiary,#8b8b8b);font-size:12px}
.thsd-detail{min-width:0}
.thsd-quote-head{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--dsw-alias-border-l3,#2a2a2a)}
.thsd-quote-name{font-size:16px;font-weight:650}
.thsd-quote-code{font-size:11px;color:var(--dsw-alias-label-tertiary,#888);margin-left:6px}
.thsd-quote-price{font-size:25px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.05}
.thsd-quote-change{font-size:12px;font-weight:600;margin-left:2px}
.thsd-quote-stats{margin-left:auto;display:flex;gap:12px;flex-wrap:wrap;color:var(--dsw-alias-label-tertiary,#8a8a8a);font-size:11px}
.thsd-quote-stats b{display:block;color:var(--dsw-alias-label-secondary,#bdbdbd);font-weight:550;margin-top:2px;font-variant-numeric:tabular-nums}
.thsd-periods{display:flex;align-items:center;gap:5px;padding:9px 12px 0;flex-wrap:wrap}
.thsd-period{border:0;border-radius:6px;background:transparent;color:var(--dsw-alias-label-tertiary,#888);padding:4px 8px;font:inherit;font-size:11px;cursor:pointer}
.thsd-period:hover{background:var(--dsw-alias-interactive-bg-hover,#232323);color:var(--dsw-alias-label-primary,#eee)}
.thsd-period.active{background:var(--dsw-alias-state-business-primary,#3b82f6);color:#fff}
.thsd-badge{margin-left:auto;color:var(--dsw-alias-label-tertiary,#777);font-size:10px;border:1px solid var(--dsw-alias-border-l3,#333);padding:2px 6px;border-radius:20px}
.thsd-daily-strip{display:flex;gap:14px;flex-wrap:wrap;padding:5px 14px 0;color:var(--dsw-alias-label-tertiary,#888);font-size:11px}
.thsd-daily-strip b{color:var(--dsw-alias-label-secondary,#bbb);font-weight:550;font-variant-numeric:tabular-nums}
.thsd-chart{position:relative;padding:4px 8px 8px}
.thsd-chart svg{display:block;width:100%;height:auto;min-height:360px;overflow:visible}
.thsd-chart-meta{display:flex;gap:12px;flex-wrap:wrap;padding:2px 8px 0;color:var(--dsw-alias-label-tertiary,#888);font-size:11px}
.thsd-chart-meta b{color:var(--dsw-alias-label-secondary,#bbb);font-weight:550}
.thsd-tip{position:absolute;top:8px;transform:translateX(-50%);background:rgba(20,20,20,.96);border:1px solid rgba(127,127,127,.32);border-radius:7px;padding:6px 8px;font-size:11px;line-height:1.55;color:#e8e8e8;pointer-events:none;white-space:nowrap;z-index:3;box-shadow:0 8px 24px rgba(0,0,0,.28)}
.thsd-bottom{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(250px,.8fr);gap:12px;padding:0 12px 12px}
.thsd-box{border:1px solid var(--dsw-alias-border-l3,#2e2e2e);border-radius:9px;background:rgba(127,127,127,.035);padding:10px;min-width:0}
.thsd-box-title{font-size:12px;font-weight:620;margin-bottom:7px;display:flex;align-items:center;gap:6px}
.thsd-box-title span{margin-left:auto;color:var(--dsw-alias-label-tertiary,#777);font-size:10px;font-weight:400}
.thsd-flow-row{display:grid;grid-template-columns:58px 1fr 76px 76px;gap:7px;align-items:center;font-size:11px;margin:4px 0;font-variant-numeric:tabular-nums}
.thsd-flow-name{color:var(--dsw-alias-label-secondary,#aaa)}
.thsd-flow-bar{height:7px;border-radius:4px;background:rgba(127,127,127,.12);overflow:hidden;display:flex}
.thsd-flow-fill{height:100%;border-radius:4px;min-width:2px}
.thsd-flow-num{text-align:right;font-weight:550}
.thsd-flow-head{color:var(--dsw-alias-label-tertiary,#777);font-size:10px}
.thsd-flow-days{display:flex;gap:5px;align-items:flex-end;height:46px;margin-top:8px;padding-top:5px;border-top:1px solid rgba(127,127,127,.12)}
.thsd-flow-day{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:2px;color:var(--dsw-alias-label-tertiary,#777);font-size:9px}
.thsd-flow-day i{display:block;width:70%;min-height:2px;border-radius:2px 2px 0 0}
.thsd-book{font-size:11px;font-variant-numeric:tabular-nums}
.thsd-book-row{display:grid;grid-template-columns:32px 72px 1fr 54px;gap:5px;align-items:center;padding:1.5px 0;position:relative}
.thsd-book-row .depth{position:absolute;right:0;top:1px;bottom:1px;border-radius:2px;opacity:.12}
.thsd-book-label{color:var(--dsw-alias-label-tertiary,#888);z-index:1}
.thsd-book-price{text-align:right;z-index:1}
.thsd-book-qty{text-align:right;color:var(--dsw-alias-label-secondary,#b0b0b0);z-index:1}
.thsd-book-mid{display:flex;align-items:center;justify-content:space-between;padding:5px 2px;margin:3px 0;border-top:1px solid rgba(127,127,127,.16);border-bottom:1px solid rgba(127,127,127,.16);font-weight:650}
.thsd-book-mid span{font-size:10px;color:var(--dsw-alias-label-tertiary,#888);font-weight:400}
.thsd-note{color:var(--dsw-alias-label-tertiary,#777);font-size:10px;margin-top:6px;line-height:1.5}
.thsd-error{margin:0 0 12px;border:1px solid rgba(239,68,68,.35);background:rgba(239,68,68,.08);color:#fca5a5;border-radius:8px;padding:9px 11px;font-size:12px}
.thsd-loading{color:var(--dsw-alias-label-tertiary,#888);font-size:12px;padding:18px;text-align:center}
.thsd-foot{margin-top:12px;display:flex;justify-content:space-between;gap:12px;color:var(--dsw-alias-label-tertiary,#777);font-size:10px;flex-wrap:wrap}
.thsd-tools{display:grid;grid-template-columns:minmax(220px,1.4fr) minmax(150px,1fr) 120px 120px minmax(180px,1.2fr);gap:8px;align-items:end;margin-bottom:12px}
.thsd-field{display:flex;flex-direction:column;gap:4px;min-width:0}
.thsd-field label{font-size:10px;color:var(--dsw-alias-label-tertiary,#888)}
.thsd-select,.thsd-input.wide{width:100%;height:31px;box-sizing:border-box;border:1px solid var(--dsw-alias-border-l3,#333);border-radius:7px;background:var(--dsw-alias-bg-layer-2,#1b1b1b);color:inherit;padding:0 8px;font:inherit;outline:none}
.thsd-select:focus,.thsd-input.wide:focus{border-color:var(--dsw-alias-state-business-primary,#4d8dff)}
.thsd-slider-wrap{display:flex;align-items:center;gap:8px;min-width:0}
.thsd-slider{width:100%;accent-color:var(--dsw-alias-state-business-primary,#4d8dff)}
.thsd-slider-date{font-size:10px;color:var(--dsw-alias-label-tertiary,#888);white-space:nowrap}
.thsd-equity{position:relative;padding:4px 8px 8px}
.thsd-equity svg{display:block;width:100%;height:auto;min-height:220px}
.thsd-trade-wrap{overflow:auto;max-height:390px}
.thsd-trade-table th:first-child,.thsd-trade-table td:first-child{text-align:left}
.thsd-trade-table td{font-size:11px}
.thsd-side-buy{color:${UP};font-weight:650}
.thsd-side-sell{color:${DOWN};font-weight:650}
.thsd-run-note{font-size:10px;color:var(--dsw-alias-label-tertiary,#777);margin-left:8px;font-weight:400}
.thsd-chart-small .thsd-chart-meta{font-size:10px}
.thsd-chart-small svg{min-height:300px}
.thsd-backtest-note{padding:0 14px 12px;color:var(--dsw-alias-label-tertiary,#777);font-size:10px}
@media(max-width:1300px){.thsd-tools{grid-template-columns:repeat(3,minmax(140px,1fr))}}@media(max-width:1100px){.thsd-layout{grid-template-columns:1fr}.thsd-cards{grid-template-columns:repeat(2,minmax(120px,1fr))}.thsd-pos-wrap{max-height:240px}}
@media(max-width:720px){.thsd-bottom{grid-template-columns:1fr}.thsd-quote-stats{width:100%;margin-left:0}.thsd-root{padding:12px}.thsd-cards{grid-template-columns:1fr 1fr}}
`;
    function injectStyles() {
      if (typeof document === "undefined") return;
      if (document.querySelector('style[data-plugin="' + PLUGIN_ID + '"]')) return;
      const style = document.createElement("style");
      style.dataset.plugin = PLUGIN_ID;
      style.textContent = CSS;
      document.head.appendChild(style);
    }

    function num(value) {
      if (value === null || value === undefined || value === "") return null;
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    }
    function fmtMoney(value) {
      const n = num(value);
      if (n === null) return "--";
      const a = Math.abs(n);
      if (a >= 1e8) return (n / 1e8).toFixed(2) + "亿";
      if (a >= 1e4) return (n / 1e4).toFixed(2) + "万";
      return n.toFixed(0);
    }
    function fmtPrice(value) {
      const n = num(value);
      return n === null ? "--" : n.toFixed(2);
    }
    function fmtPct(value) {
      const n = num(value);
      if (n === null) return "--";
      return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
    }
    function fmtSigned(value) {
      const n = num(value);
      if (n === null) return "--";
      return (n > 0 ? "+" : "") + fmtMoney(n);
    }
    function tone(value) {
      const n = num(value);
      if (n === null || n === 0) return "";
      return n > 0 ? "thsd-up" : "thsd-down";
    }
    function periodLabel(p) {
      const found = PERIODS.find(x => x[0] === p);
      return found ? found[1] : p;
    }
    function shortTime(value) {
      const s = String(value || "");
      if (s.includes(" ")) return s.split(" ")[1].slice(0, 5);
      if (s.length >= 10) return s.slice(5, 10);
      return s;
    }
    function axisTime(value, multiDay) {
      const s = String(value || "");
      if (s.includes(" ")) return multiDay ? s.slice(5, 16) : s.split(" ")[1].slice(0, 5);
      if (s.length >= 10) return s.slice(5, 10);
      return s;
    }

    function PanelIcon(props) {
      const size = props && props.size ? props.size : 18;
      const active = !!(props && props.active);
      const color = active ? "currentColor" : "currentColor";
      return h("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", "aria-hidden": "true" },
        h("rect", { x: 3.2, y: 5.0, width: 17.6, height: 14.2, rx: 2.2, stroke: color, strokeWidth: 1.6, opacity: 0.85 }),
        h("path", { d: "M7 15.8V11.2M10 15.8V8.8M13 15.8V12.4M16.7 15.8V9.8", stroke: color, strokeWidth: 1.7, strokeLinecap: "round" }),
        h("path", { d: "M5.2 5.2h4.1M14.7 5.2h4.1", stroke: color, strokeWidth: 1.5, strokeLinecap: "round" })
      );
    }    function KLineChart(props) {
      const chart = props && props.chart ? props.chart : null;
      const bars = chart && Array.isArray(chart.bars) ? chart.bars : [];
      const [hover, setHover] = useState(null);
      if (!bars.length) {
        return h("div", { className: "thsd-loading" }, "暂无K线数据，等待行情服务返回");
      }
      const W = 1000;
      const H = 540;
      const left = 58;
      const right = 70;
      const top = 18;
      const priceH = 286;
      const volTop = 338;
      const volH = 58;
      const macdTop = 426;
      const macdH = 92;
      const plotW = W - left - right;
      const step = plotW / bars.length;
      const rawLo = Math.min.apply(null, bars.map(b => Number(b.low) || 0));
      const rawHi = Math.max.apply(null, bars.map(b => Number(b.high) || 0));
      const pad = Math.max(0.01, (rawHi - rawLo) * 0.06);
      const lo = rawLo - pad;
      const hi = rawHi + pad;
      const priceY = v => top + (hi - v) / Math.max(1e-9, hi - lo) * priceH;
      const xAt = i => left + (i + 0.5) * step;
      const volMax = Math.max(1, Math.max.apply(null, bars.map(b => Number(b.volume) || 0)));
      const macd = chart.macd || {};
      const dif = Array.isArray(macd.dif) ? macd.dif : [];
      const dea = Array.isArray(macd.dea) ? macd.dea : [];
      const hist = Array.isArray(macd.hist) ? macd.hist : [];
      const macdVals = dif.concat(dea, hist).map(Number).filter(Number.isFinite);
      let macdLo = macdVals.length ? Math.min.apply(null, macdVals) : -1;
      let macdHi = macdVals.length ? Math.max.apply(null, macdVals) : 1;
      const macdPad = Math.max(0.0001, (macdHi - macdLo) * 0.15);
      macdLo -= macdPad;
      macdHi += macdPad;
      const macdY = v => macdTop + (macdHi - v) / Math.max(1e-9, macdHi - macdLo) * macdH;
      const linePoints = values => {
        const pts = [];
        (values || []).forEach((v, i) => {
          const n = num(v);
          if (n !== null && i < bars.length) pts.push(xAt(i) + "," + priceY(n));
        });
        return pts.join(" ");
      };
      const macdPoints = values => {
        const pts = [];
        (values || []).forEach((v, i) => {
          const n = num(v);
          if (n !== null && i < bars.length) pts.push(xAt(i) + "," + macdY(n));
        });
        return pts.join(" ");
      };
      const grid = [0, 0.25, 0.5, 0.75, 1];
      const xLabelEvery = Math.max(1, Math.ceil(bars.length / 7));
      const last = bars[bars.length - 1];
      const multiDay = String(bars[0].time || "").slice(0, 10) !== String(last.time || "").slice(0, 10);
      const shown = hover !== null ? bars[hover] : last;
      const shownIndex = hover !== null ? hover : bars.length - 1;
      const onMove = event => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (!rect.width) return;
        const svgX = (event.clientX - rect.left) / rect.width * W;
        let idx = Math.floor((svgX - left) / step);
        idx = Math.max(0, Math.min(bars.length - 1, idx));
        setHover(idx);
      };
      const candleNodes = bars.map((b, i) => {
        const up = Number(b.close) >= Number(b.open);
        const color = up ? UP : DOWN;
        const bodyTop = priceY(Math.max(Number(b.open), Number(b.close)));
        const bodyBottom = priceY(Math.min(Number(b.open), Number(b.close)));
        const bodyH = Math.max(1, bodyBottom - bodyTop);
        const bw = Math.max(1, step * 0.62);
        return h("g", { key: "c" + i },
          h("line", { x1: xAt(i), y1: priceY(Number(b.high)), x2: xAt(i), y2: priceY(Number(b.low)), stroke: color, strokeWidth: 1 }),
          h("rect", { x: xAt(i) - bw / 2, y: bodyTop, width: bw, height: bodyH, fill: color, opacity: 0.92 })
        );
      });
      const volNodes = bars.map((b, i) => {
        const up = Number(b.close) >= Number(b.open);
        const hgt = Math.max(1, (Number(b.volume) || 0) / volMax * volH);
        return h("rect", { key: "v" + i, x: xAt(i) - Math.max(1, step * 0.58) / 2,
          y: volTop + volH - hgt, width: Math.max(1, step * 0.58), height: hgt,
          fill: up ? UP : DOWN, opacity: 0.52 });
      });
      const histNodes = bars.map((b, i) => {
        const v = num(hist[i]);
        if (v === null) return null;
        const zero = macdY(0);
        const y = Math.min(zero, macdY(v));
        const hgt = Math.max(1, Math.abs(macdY(v) - zero));
        return h("rect", { key: "h" + i, x: xAt(i) - Math.max(1, step * 0.52) / 2,
          y: y, width: Math.max(1, step * 0.52), height: hgt,
          fill: v >= 0 ? UP : DOWN, opacity: 0.55 });
      });
      const xLabels = [];
      for (let i = 0; i < bars.length; i += xLabelEvery) {
        xLabels.push(h("text", { key: "x" + i, x: xAt(i), y: H - 5, textAnchor: "middle",
          fontSize: multiDay ? 9 : 10, fill: "var(--dsw-alias-label-tertiary,#777)" }, axisTime(bars[i].time, multiDay)));
      }
      const priceGrid = grid.map((f, i) => {
        const price = hi - (hi - lo) * f;
        const y = priceY(price);
        return h("g", { key: "pg" + i },
          h("line", { x1: left, x2: W - right, y1: y, y2: y,
            stroke: "var(--dsw-alias-border-l3,#2e2e2e)", strokeWidth: 0.7,
            strokeDasharray: i === 0 || i === grid.length - 1 ? "0" : "3 4", opacity: 0.55 }),
          h("text", { x: left - 7, y: y + 3.5, textAnchor: "end", fontSize: 10,
            fill: "var(--dsw-alias-label-tertiary,#777)" }, price.toFixed(2))
        );
      });
      return h("div", { className: "thsd-chart" },
        h("div", { className: "thsd-chart-meta" },
          h("span", null, h("b", null, chart.name || ""), " ", chart.symbol || ""),
          h("span", null, "开 ", h("b", null, fmtPrice(shown.open))),
          h("span", null, "高 ", h("b", null, fmtPrice(shown.high))),
          h("span", null, "低 ", h("b", null, fmtPrice(shown.low))),
          h("span", null, "收 ", h("b", { className: tone(Number(shown.close) - Number(shown.open)) }, fmtPrice(shown.close))),
          h("span", null, "量 ", h("b", null, fmtMoney(shown.volume))),
          h("span", { className: "thsd-badge" }, "K线 ", chart.source || "")
        ),
        h("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none",
          onMouseMove: onMove, onMouseLeave: () => setHover(null), role: "img",
          "aria-label": "K线图 " + (chart.symbol || "") },
          priceGrid,
          candleNodes,
          h("polyline", { points: linePoints(chart.ma5), fill: "none", stroke: "#f59e0b", strokeWidth: 1.4, opacity: 0.96 }),
          h("polyline", { points: linePoints(chart.ma10), fill: "none", stroke: "#3b82f6", strokeWidth: 1.4, opacity: 0.96 }),
          h("line", { x1: left, x2: W - right, y1: priceY(Number(last.close)), y2: priceY(Number(last.close)),
            stroke: "var(--dsw-alias-state-business-primary,#4d8dff)", strokeWidth: 0.8, strokeDasharray: "5 4", opacity: 0.85 }),
          h("text", { x: W - right + 5, y: priceY(Number(last.close)) + 3.5, fontSize: 10,
            fill: "var(--dsw-alias-state-business-primary,#4d8dff)" }, fmtPrice(last.close)),
          h("text", { x: left, y: volTop - 7, fontSize: 10, fill: "var(--dsw-alias-label-tertiary,#777)" }, "成交量"),
          volNodes,
          h("text", { x: left, y: macdTop - 7, fontSize: 10, fill: "var(--dsw-alias-label-tertiary,#777)" }, "MACD(12,26,9)"),
          h("line", { x1: left, x2: W - right, y1: macdY(0), y2: macdY(0),
            stroke: "var(--dsw-alias-border-l3,#2e2e2e)", strokeWidth: 0.7, opacity: 0.7 }),
          histNodes,
          h("polyline", { points: macdPoints(dif), fill: "none", stroke: "#f59e0b", strokeWidth: 1.2 }),
          h("polyline", { points: macdPoints(dea), fill: "none", stroke: "#3b82f6", strokeWidth: 1.2 }),
          xLabels,
          hover !== null ? h("line", { x1: xAt(shownIndex), x2: xAt(shownIndex), y1: top, y2: H - 14,
            stroke: "rgba(200,200,200,.5)", strokeWidth: 0.8, strokeDasharray: "3 3" }) : null
        ),
        hover !== null ? h("div", { className: "thsd-tip", style: { left: Math.max(8, Math.min(88, xAt(shownIndex) / W * 100)) + "%" } },
          h("div", null, shown.time || ""),
          h("div", null, "O " + fmtPrice(shown.open) + "  H " + fmtPrice(shown.high)),
          h("div", null, "L " + fmtPrice(shown.low) + "  C " + fmtPrice(shown.close)),
          h("div", null, "量 " + fmtMoney(shown.volume) + "  额 " + fmtMoney(shown.amount))
        ) : null
      );
    }

    function FlowPanel(props) {
      const flow = props && props.flow ? props.flow : null;
      const caption = props && props.caption ? props.caption : "今日 / 5日";
      const heading = props && props.heading ? props.heading : "资金流向";
      if (!flow) return h("div", { className: "thsd-box" }, h("div", { className: "thsd-box-title" }, "资金流向"), h("div", { className: "thsd-empty" }, "暂无资金流数据"));
      const today = flow.today || {};
      const five = flow.five_day || {};
      const rows = [
        ["主力净流入", "main", "thsd-flow-main"],
        ["超大单", "super", ""],
        ["大单", "large", ""],
        ["中单", "medium", ""],
        ["小单", "small", ""]
      ];
      const maxAbs = Math.max(1, Math.max.apply(null, rows.map(x => Math.abs(num(today[x[1]]) || 0))));
      const dayRows = (flow.daily || []).slice(-5);
      const dayMax = Math.max(1, Math.max.apply(null, dayRows.map(x => Math.abs(num(x.main) || 0))));
      return h("div", { className: "thsd-box" },
        h("div", { className: "thsd-box-title" }, heading, h("span", null, (flow.source || "public") + " · " + caption)),
        h("div", { className: "thsd-flow-row thsd-flow-head" },
          h("span", null, "口径"), h("span", null, "今日强度"), h("span", { style: { textAlign: "right" } }, "今日"),
          h("span", { style: { textAlign: "right" } }, "近5日")),
        rows.map(row => {
          const v = num(today[row[1]]);
          const f = num(five[row[1]]);
          const w = Math.max(2, Math.abs(v || 0) / maxAbs * 100);
          const col = v === null ? "rgba(127,127,127,.45)" : (v >= 0 ? UP : DOWN);
          return h("div", { className: "thsd-flow-row", key: row[1] },
            h("span", { className: "thsd-flow-name" }, row[0]),
            h("span", { className: "thsd-flow-bar" }, h("i", { className: "thsd-flow-fill", style: { width: w + "%", background: col } })),
            h("span", { className: "thsd-flow-num " + tone(v) }, fmtSigned(v)),
            h("span", { className: "thsd-flow-num " + tone(f) }, f === null ? "--" : fmtSigned(f))
          );
        }),
        h("div", { className: "thsd-flow-days" },
          dayRows.map((x, i) => {
            const v = num(x.main) || 0;
            const hgt = Math.max(2, Math.abs(v) / dayMax * 38);
            return h("div", { className: "thsd-flow-day", key: "fd" + i, title: fmtSigned(v) },
              h("i", { style: { height: hgt + "px", background: v >= 0 ? UP : DOWN, opacity: 0.72 } }),
              h("span", null, shortTime(x.time))
            );
          })
        ),
        h("div", { className: "thsd-note" }, "主力/超大单为公开资金流口径；不是逐笔 L2 成交。")
      );
    }

    function OrderBook(props) {
      const quote = props && props.quote ? props.quote : null;
      if (!quote) return h("div", { className: "thsd-box" }, h("div", { className: "thsd-box-title" }, "五档盘口"), h("div", { className: "thsd-empty" }, "暂无盘口数据"));
      const bids = Array.isArray(quote.bids) ? quote.bids : [];
      const asks = Array.isArray(quote.asks) ? quote.asks : [];
      const maxQty = Math.max(1, Math.max.apply(null, bids.concat(asks).map(x => Number(x[1]) || 0)));
      const row = (level, i, side, label) => {
        const price = Number(level[0]) || 0;
        const qty = Number(level[1]) || 0;
        return h("div", { className: "thsd-book-row", key: side + i },
          h("span", { className: "depth", style: { width: Math.max(2, qty / maxQty * 100) + "%", background: side === "ask" ? UP : DOWN } }),
          h("span", { className: "thsd-book-label" }, label),
          h("span", { className: "thsd-book-price " + (side === "ask" ? "thsd-down" : "thsd-up") }, fmtPrice(price)),
          h("span", { className: "thsd-book-qty" }, fmtMoney(qty))
        );
      };
      const askNodes = asks.slice().reverse().map((x, i) => row(x, i, "ask", "卖" + (asks.length - i)));
      const bidNodes = bids.map((x, i) => row(x, i, "bid", "买" + (i + 1)));
      const bid1 = bids.length ? Number(bids[0][0]) : 0;
      const ask1 = asks.length ? Number(asks[0][0]) : 0;
      return h("div", { className: "thsd-box" },
        h("div", { className: "thsd-box-title" }, "五档盘口", h("span", null, quote.source === "ths" ? "同花顺模拟" : (quote.source || "public"))),
        h("div", { className: "thsd-book" }, askNodes,
          h("div", { className: "thsd-book-mid" }, h("b", { className: tone(Number(quote.last_price) - Number(quote.pre_close)) }, fmtPrice(quote.last_price)), h("span", null, "价差 " + fmtPrice(ask1 - bid1))),
          bidNodes,
          h("div", { className: "thsd-note" }, "五档报价与挂单量；当前数据源不含逐笔委托/十档 L2。")
        )
      );
    }
    async function fetchDashboard(action, params, signal) {
      const query = new URLSearchParams({ action: action });
      Object.keys(params || {}).forEach(k => {
        if (params[k] !== undefined && params[k] !== null && params[k] !== "") query.set(k, String(params[k]));
      });
      let firstError = null;
      let response = null;
      try {
        response = await fetch(API + "?" + query.toString(), {
          signal: signal, headers: { Accept: "application/json" }
        });
        if (!response.ok) {
          let text = await response.text();
          let body = null;
          try { body = JSON.parse(text); } catch (err) {}
          throw new Error(body && body.error ? body.error : "HTTP " + response.status);
        }
      } catch (err) {
        if (err && err.name === "AbortError") throw err;
        firstError = err;
        response = null;
      }
      if (!response) {
        const direct = new URLSearchParams();
        Object.keys(params || {}).forEach(k => {
          if (params[k] !== undefined && params[k] !== null && params[k] !== "") direct.set(k, String(params[k]));
        });
        response = await fetch(DIRECT_API + "/" + action + "?" + direct.toString(), {
          signal: signal, headers: { Accept: "application/json" }
        });
      }
      const text = await response.text();
      let body = null;
      try { body = JSON.parse(text); } catch (err) {
        throw new Error("行情服务返回非 JSON: " + text.slice(0, 120));
      }
      if (!response.ok || body.ok === false) {
        throw new Error(body && body.error ? body.error : (firstError ? String(firstError) : "HTTP " + response.status));
      }
      return body;
    }

    function Dashboard() {
      const previewParams = (() => {
        try { return new URLSearchParams(location.search); } catch (err) { return new URLSearchParams(); }
      })();
      const initial = (() => {
        try { return previewParams.get("thsd_symbol") || localStorage.getItem("thsd.symbol") || "600519"; }
        catch (err) { return "600519"; }
      })();
      const initialPeriod = previewParams.get("thsd_period") === "day" ? "day" : "5";
      const [symbol, setSymbol] = useState(initial);
      const [input, setInput] = useState(initial);
      const [period, setPeriod] = useState(initialPeriod);
      const [data, setData] = useState(null);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState("");
      const [auto, setAuto] = useState(true);
      const [lastUpdated, setLastUpdated] = useState(null);
      const abortRef = useRef(null);

      const load = useCallback(async (background) => {
        if (!background) setLoading(true);
        setError("");
        if (abortRef.current) abortRef.current.abort();
        const ctrl = new AbortController();
        abortRef.current = ctrl;
        try {
          const apiPeriod = period === "day" ? "5" : period;
          const body = await fetchDashboard("overview", { symbol: symbol, period: apiPeriod }, ctrl.signal);
          setData(body);
          setLastUpdated(new Date());
        } catch (err) {
          if (err && err.name === "AbortError") return;
          const raw = String(err && err.message ? err.message : err);
          setError(raw.includes("Failed to fetch")
            ? "本地行情服务未连接。请重启 DSH，或手动运行 python -m ths_sim.dashboard_server --port 8766"
            : raw);
        } finally {
          if (!background) setLoading(false);
        }
      }, [symbol, period]);

      useEffect(() => {
        try { localStorage.setItem("thsd.symbol", symbol); } catch (err) {}
        load(false);
        return () => { if (abortRef.current) abortRef.current.abort(); };
      }, [load, symbol]);

      useEffect(() => {
        if (!auto) return undefined;
        const id = setInterval(() => load(true), 10000);
        return () => clearInterval(id);
      }, [auto, load]);

      const submit = () => {
        const clean = String(input || "").replace(/\D/g, "").slice(-6);
        if (clean.length !== 6) {
          setError("请输入 6 位 A 股代码");
          return;
        }
        setInput(clean);
        if (clean === symbol) load(false);
        else setSymbol(clean);
      };
      const positions = (data && data.account && data.account.positions) || [];
      const account = (data && data.account) || {};
      const quote = (data && data.quote) || {};
      const held = (data && data.held) || positions.find(p => p.symbol === symbol) || null;
      const pnl = positions.reduce((sum, p) => sum + (Number(p.pnl) || 0), 0);
      const daily = data && data.daily ? data.daily : null;
      const dIdx = daily && Array.isArray(daily.bars) ? daily.bars.length - 1 : -1;
      const dMa5 = dIdx >= 0 && daily.ma5 ? daily.ma5[dIdx] : null;
      const dMa10 = dIdx >= 0 && daily.ma10 ? daily.ma10[dIdx] : null;
      const dHist = dIdx >= 0 && daily.macd && daily.macd.hist ? daily.macd.hist[dIdx] : null;
      const chartData = data ? (period === "day" ? daily : data.chart) : null;
      const partialErrors = data && data.errors ? Object.keys(data.errors).map(k => k + ": " + data.errors[k]).join(" | ") : "";
      const statusText = loading ? "载入中" : error ? "服务异常" : data ? "已连接" : "未连接";
      const statusClass = loading ? "thsd-warn-dot" : error ? "thsd-bad-dot" : "thsd-ok";
      const changePct = quote.change_pct !== undefined && quote.change_pct !== null
        ? Number(quote.change_pct)
        : (Number(quote.last_price) && Number(quote.pre_close)
          ? (Number(quote.last_price) / Number(quote.pre_close) - 1) * 100 : null);

      return h("div", { className: "thsd-root" },
        h("div", { className: "thsd-head" },
          h("div", null,
            h("div", { className: "thsd-title" }, "模拟持仓 · 行情监控"),
            h("div", { className: "thsd-sub" }, "同花顺模拟账户 · 分钟K线 · MA5/MA10 · MACD · 资金流 · 五档盘口")
          ),
          h("div", { className: "thsd-head-actions" },
            h("span", { style: { display: "inline-flex", alignItems: "center", gap: "6px", color: "var(--dsw-alias-label-tertiary,#888)", fontSize: "11px" } },
              h("i", { className: statusClass }), statusText),
            h("input", { className: "thsd-input", value: input, placeholder: "股票代码",
              onChange: e => setInput(e.target.value), onKeyDown: e => { if (e.key === "Enter") submit(); } }),
            h("button", { className: "thsd-btn primary", onClick: submit }, "查看"),
            h("button", { className: "thsd-btn", onClick: () => load(false), disabled: loading }, loading ? "刷新中" : "刷新"),
            h("label", { className: "thsd-toggle" },
              h("input", { type: "checkbox", checked: auto, onChange: e => setAuto(e.target.checked) }), "自动 10s")
          )
        ),
        (error || partialErrors) ? h("div", { className: "thsd-error" }, error || partialErrors) : null,
        h("div", { className: "thsd-cards" },
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "总资产"), h("div", { className: "thsd-card-value" }, fmtMoney(account.total_assets)), h("div", { className: "thsd-card-sub" }, "同花顺模拟账户")),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "可用资金"), h("div", { className: "thsd-card-value" }, fmtMoney(account.available_cash)), h("div", { className: "thsd-card-sub" }, "可买资金")),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "持仓市值"), h("div", { className: "thsd-card-value" }, fmtMoney(account.market_value)), h("div", { className: "thsd-card-sub" }, positions.length + " 个持仓")),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "持仓浮盈"), h("div", { className: "thsd-card-value " + tone(pnl) }, fmtSigned(pnl)), h("div", { className: "thsd-card-sub" }, pnl === 0 ? "暂无持仓" : "按持仓汇总"))
        ),
        h("div", { className: "thsd-layout" },
          h("section", { className: "thsd-panel" },
            h("div", { className: "thsd-panel-head" },
              h("span", { className: "thsd-panel-title" }, "模拟持仓"),
              h("span", { className: "thsd-panel-meta" }, account.error ? "账户读取失败" : (lastUpdated ? "更新 " + lastUpdated.toLocaleTimeString() : "等待数据"))
            ),
            h("div", { className: "thsd-pos-wrap" },
              positions.length === 0
                ? h("div", { className: "thsd-empty" }, ["当前无持仓。", h("br", { key: "br" }), "输入代码查看行情，策略确认后再开始模拟交易。"])
                : h("table", { className: "thsd-table" },
                    h("thead", null, h("tr", null,
                      h("th", null, "股票"), h("th", null, "持仓/可用"), h("th", null, "成本/现价"),
                      h("th", null, "市值"), h("th", null, "浮盈"))),
                    h("tbody", null, positions.map(p => h("tr", {
                      key: p.symbol, className: "row" + (p.symbol === symbol ? " selected" : ""),
                      onClick: () => { setSymbol(p.symbol); setInput(p.symbol); }
                    },
                      h("td", null, h("b", null, p.name || p.symbol), h("span", { className: "thsd-code" }, p.symbol)),
                      h("td", null, String(p.quantity || p.balance || 0), h("span", { className: "thsd-code" }, "/" + String(p.available || 0))),
                      h("td", null, fmtPrice(p.cost_price), h("span", { className: "thsd-code" }, "/" + fmtPrice(p.market_price || p.last_price))),
                      h("td", null, fmtMoney(p.value)),
                      h("td", { className: tone(p.pnl) }, fmtSigned(p.pnl), h("span", { className: "thsd-code" }, fmtPct(p.pnl_pct)))
                    )))
                  )
            )
          ),
          h("section", { className: "thsd-panel thsd-detail" },
            h("div", { className: "thsd-quote-head" },
              h("div", null,
                h("div", { className: "thsd-quote-name" }, quote.name || (held && held.name) || symbol,
                  h("span", { className: "thsd-quote-code" }, symbol)),
                h("div", { className: "thsd-sub" }, held ? "当前持仓标的" : "观察标的")
              ),
              h("div", { className: "thsd-quote-price " + tone(changePct) }, fmtPrice(quote.last_price),
                h("span", { className: "thsd-quote-change" }, fmtPct(changePct))),
              h("div", { className: "thsd-quote-stats" },
                h("span", null, "今开", h("b", null, fmtPrice(quote.open))),
                h("span", null, "最高", h("b", null, fmtPrice(quote.high))),
                h("span", null, "最低", h("b", null, fmtPrice(quote.low))),
                h("span", null, "昨收", h("b", null, fmtPrice(quote.pre_close))),
                h("span", null, "成交额", h("b", null, fmtMoney(quote.amount)))
              )
            ),
            h("div", { className: "thsd-periods" },
              PERIODS.map(p => h("button", { key: p[0], className: "thsd-period" + (period === p[0] ? " active" : ""), onClick: () => setPeriod(p[0]) }, p[1])),
              h("span", { className: "thsd-badge" }, period === "day" ? "日线 · MA5/MA10 · MACD" : periodLabel(period) + " · MA5/MA10 · MACD")
            ),
            h("div", { className: "thsd-daily-strip" },
              h("span", null, "日线 MA5 ", h("b", null, fmtPrice(dMa5))),
              h("span", null, "日线 MA10 ", h("b", null, fmtPrice(dMa10))),
              h("span", null, "日线 MACD ", h("b", { className: tone(dHist) }, fmtSigned(dHist)))
            ),
            h(KLineChart, { chart: chartData }),
            h("div", { className: "thsd-bottom" },
              h(FlowPanel, { flow: data && data.flow }),
              h(OrderBook, { quote: quote })
            )
          )
        ),
        h("div", { className: "thsd-foot" },
          h("span", null, "数据源: ", (data && data.chart && data.chart.source) || "--", " · ", (data && data.flow && data.flow.source) || "--", " · 盘口 ", (quote && quote.source) || "--"),
          h("span", null, "行情仅供研究；真实交易前请核对策略、仓位和风控。")
        )
      );
    }

    function BacktestIcon(props) {
      const size = props && props.size ? props.size : 18;
      return h("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", "aria-hidden": "true" },
        h("circle", { cx: 12, cy: 12, r: 8.1, stroke: "currentColor", strokeWidth: 1.6, opacity: 0.9 }),
        h("path", { d: "M12 7.5V12l3.1 1.9", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" }),
        h("path", { d: "M4.6 8.5 3.3 5.9M19.4 8.5l1.3-2.6", stroke: "currentColor", strokeWidth: 1.4, strokeLinecap: "round", opacity: 0.75 })
      );
    }

    function dateShift(value, days) {
      const s = String(value || "").slice(0, 10);
      const parts = s.split("-").map(Number);
      if (parts.length !== 3 || parts.some(n => !Number.isFinite(n))) return s;
      const d = new Date(parts[0], parts[1] - 1, parts[2]);
      d.setDate(d.getDate() + Number(days || 0));
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return y + "-" + m + "-" + day;
    }

    function reconstructPositions(trades, cutoff) {
      const book = new Map();
      (trades || []).forEach(t => {
        if (!t || !t.date || t.date > cutoff) return;
        const code = String(t.code || "");
        const qty = Number(t.quantity) || 0;
        const price = Number(t.price) || 0;
        const fee = Number(t.fee) || 0;
        if (!code || qty <= 0 || price <= 0) return;
        let row = book.get(code);
        if (!row) {
          row = { symbol: code, quantity: 0, avg_cost: 0, last_price: price, realized_pnl: 0 };
          book.set(code, row);
        }
        row.last_price = price;
        if (t.side === "buy") {
          const newQty = row.quantity + qty;
          row.avg_cost = ((row.quantity * row.avg_cost) + qty * price + fee) / newQty;
          row.quantity = newQty;
        } else if (t.side === "sell") {
          const sold = Math.min(qty, row.quantity);
          row.realized_pnl += (price - row.avg_cost) * sold - fee;
          row.quantity -= sold;
          if (row.quantity <= 0) book.delete(code);
        }
      });
      return Array.from(book.values()).map(p => ({
        ...p,
        market_value: p.quantity * p.last_price,
        cost_value: p.quantity * p.avg_cost,
        pnl: p.quantity * (p.last_price - p.avg_cost),
      })).sort((a, b) => a.symbol.localeCompare(b.symbol));
    }

    function EquityChart(props) {
      const equity = props && Array.isArray(props.equity) ? props.equity : [];
      const asOf = props && props.asOf ? props.asOf : "";
      const selectedTrade = props && props.selectedTrade ? props.selectedTrade : null;
      const [hover, setHover] = useState(null);
      if (equity.length < 2) {
        return h("div", { className: "thsd-loading" }, "暂无权益曲线");
      }
      const W = 1000;
      const H = 278;
      const left = 62;
      const right = 18;
      const top = 18;
      const bottom = 28;
      const plotW = W - left - right;
      const plotH = H - top - bottom;
      const values = equity.map(x => Number(x.total_value) || 0);
      let lo = Math.min.apply(null, values);
      let hi = Math.max.apply(null, values);
      const pad = Math.max(1, (hi - lo) * 0.08);
      lo -= pad;
      hi += pad;
      const xAt = i => left + (equity.length === 1 ? 0 : i / (equity.length - 1)) * plotW;
      const yAt = v => top + (hi - v) / Math.max(1e-9, hi - lo) * plotH;
      let asOfIndex = equity.findIndex(x => x.date >= asOf);
      if (asOfIndex < 0) asOfIndex = equity.length - 1;
      let selectedIndex = selectedTrade ? equity.findIndex(x => x.date >= selectedTrade.date) : -1;
      if (selectedIndex < 0) selectedIndex = -1;
      const line = equity.map((x, i) => xAt(i) + "," + yAt(Number(x.total_value) || 0)).join(" ");
      const area = left + "," + (top + plotH) + " " + line + " " + xAt(equity.length - 1) + "," + (top + plotH);
      const grid = [0, 0.25, 0.5, 0.75, 1];
      const labelEvery = Math.max(1, Math.ceil(equity.length / 7));
      const multiYear = String(equity[0].date || "").slice(0, 4) !== String(equity[equity.length - 1].date || "").slice(0, 4);
      const xLabels = [];
      for (let i = 0; i < equity.length; i += labelEvery) {
        const label = multiYear ? String(equity[i].date).slice(0, 7) : shortTime(equity[i].date);
        xLabels.push(h("text", { key: "eqx" + i, x: xAt(i), y: H - 5, textAnchor: "middle",
          fontSize: multiYear ? 9 : 10, fill: "var(--dsw-alias-label-tertiary,#777)" }, label));
      }
      const gridNodes = grid.map((f, i) => {
        const value = hi - (hi - lo) * f;
        const y = yAt(value);
        return h("g", { key: "eqg" + i },
          h("line", { x1: left, x2: W - right, y1: y, y2: y,
            stroke: "var(--dsw-alias-border-l3,#2e2e2e)", strokeWidth: 0.7, opacity: 0.55,
            strokeDasharray: i === 0 || i === grid.length - 1 ? "0" : "3 4" }),
          h("text", { x: left - 7, y: y + 3.5, textAnchor: "end", fontSize: 10,
            fill: "var(--dsw-alias-label-tertiary,#777)" }, fmtMoney(value))
        );
      });
      const onMove = event => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (!rect.width) return;
        const svgX = (event.clientX - rect.left) / rect.width * W;
        let idx = Math.round((svgX - left) / Math.max(1e-9, plotW) * (equity.length - 1));
        idx = Math.max(0, Math.min(equity.length - 1, idx));
        setHover(idx);
      };
      const onPick = event => {
        if (!props.onPick) return;
        const rect = event.currentTarget.getBoundingClientRect();
        if (!rect.width) return;
        const svgX = (event.clientX - rect.left) / rect.width * W;
        let idx = Math.round((svgX - left) / Math.max(1e-9, plotW) * (equity.length - 1));
        idx = Math.max(0, Math.min(equity.length - 1, idx));
        props.onPick(equity[idx].date);
      };
      const shown = hover !== null ? equity[hover] : equity[Math.max(0, asOfIndex)];
      return h("div", { className: "thsd-equity" },
        h("div", { className: "thsd-chart-meta" },
          h("span", null, "回放权益 ", h("b", null, fmtMoney(shown.total_value))),
          h("span", null, "现金 ", h("b", null, fmtMoney(shown.cash))),
          h("span", null, "持仓数 ", h("b", null, String(shown.n_pos || 0))),
          h("span", { className: "thsd-badge" }, "点击曲线选择日期")
        ),
        h("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none", role: "img",
          "aria-label": "回测权益曲线", onMouseMove: onMove, onMouseLeave: () => setHover(null), onClick: onPick },
          h("defs", null, h("linearGradient", { id: "thsd-equity-fill", x1: "0", y1: "0", x2: "0", y2: "1" },
            h("stop", { offset: "0%", stopColor: "#4d8dff", stopOpacity: 0.26 }),
            h("stop", { offset: "100%", stopColor: "#4d8dff", stopOpacity: 0.02 }))),
          gridNodes,
          h("polygon", { points: area, fill: "url(#thsd-equity-fill)" }),
          h("polyline", { points: line, fill: "none", stroke: "#60a5fa", strokeWidth: 1.7 }),
          h("line", { x1: xAt(asOfIndex), x2: xAt(asOfIndex), y1: top, y2: top + plotH,
            stroke: "#f59e0b", strokeWidth: 1.1, strokeDasharray: "4 3" }),
          h("circle", { cx: xAt(asOfIndex), cy: yAt(Number(equity[asOfIndex].total_value) || 0),
            r: 4, fill: "#f59e0b", stroke: "#111", strokeWidth: 1 }),
          selectedTrade && selectedIndex >= 0 ? h("g", null,
            h("line", { x1: xAt(selectedIndex), x2: xAt(selectedIndex), y1: top, y2: top + plotH,
              stroke: selectedTrade.side === "buy" ? UP : DOWN, strokeWidth: 0.9, opacity: 0.55 }),
            h("circle", { cx: xAt(selectedIndex), cy: yAt(Number(equity[selectedIndex].total_value) || 0),
              r: 3.5, fill: selectedTrade.side === "buy" ? UP : DOWN, stroke: "#111", strokeWidth: 1 })
          ) : null,
          xLabels
        ),
        hover !== null ? h("div", { className: "thsd-tip", style: { left: Math.max(8, Math.min(88, xAt(hover) / W * 100)) + "%" } },
          h("div", null, equity[hover].date),
          h("div", null, "权益 " + fmtMoney(equity[hover].total_value)),
          h("div", null, "现金 " + fmtMoney(equity[hover].cash))
        ) : null
      );
    }

    function pickDefaultRun(runs) {
      const list = Array.isArray(runs) ? runs : [];
      return list.find(r => Number(r.days) >= 300 && Number(r.trades) > 20)
        || list.find(r => Number(r.trades) > 0)
        || list[0]
        || null;
    }

    function BacktestPanel() {
      const [runs, setRuns] = useState([]);
      const [runSearch, setRunSearch] = useState("");
      const [runId, setRunId] = useState("");
      const [dataset, setDataset] = useState(null);
      const [loadingRuns, setLoadingRuns] = useState(true);
      const [loadingData, setLoadingData] = useState(false);
      const [error, setError] = useState("");
      const [historyError, setHistoryError] = useState("");
      const [rangeStart, setRangeStart] = useState("");
      const [rangeEnd, setRangeEnd] = useState("");
      const [asOf, setAsOf] = useState("");
      const [selectedTrade, setSelectedTrade] = useState(null);
      const [history, setHistory] = useState(null);
      const [historyLoading, setHistoryLoading] = useState(false);
      const [flow, setFlow] = useState(null);
      const [flowLoading, setFlowLoading] = useState(false);
      const [flowError, setFlowError] = useState("");
      const [tradeQuery, setTradeQuery] = useState("");
      const dataAbort = useRef(null);
      const historyAbort = useRef(null);
      const flowAbort = useRef(null);

      const loadRuns = useCallback(async () => {
        setLoadingRuns(true);
        setError("");
        try {
          const body = await fetchDashboard("backtests", {}, undefined);
          const list = Array.isArray(body.runs) ? body.runs : [];
          setRuns(list);
          setRunId(current => {
            if (current && list.some(r => r.id === current)) return current;
            const pick = pickDefaultRun(list);
            return pick ? pick.id : "";
          });
        } catch (err) {
          setError(String(err && err.message ? err.message : err));
        } finally {
          setLoadingRuns(false);
        }
      }, []);

      useEffect(() => { loadRuns(); }, [loadRuns]);

      useEffect(() => {
        if (!runId) {
          setDataset(null);
          return undefined;
        }
        if (dataAbort.current) dataAbort.current.abort();
        const ctrl = new AbortController();
        dataAbort.current = ctrl;
        setLoadingData(true);
        setError("");
        setDataset(null);
        setHistory(null);
        setSelectedTrade(null);
        fetchDashboard("backtest", { run: runId }, ctrl.signal).then(body => {
          setDataset(body);
          const start = body.summary && body.summary.start ? body.summary.start : "";
          const end = body.summary && body.summary.end ? body.summary.end : "";
          setRangeStart(start);
          setRangeEnd(end);
          setAsOf(end);
          const trades = Array.isArray(body.trades) ? body.trades : [];
          setSelectedTrade(trades.length ? trades[trades.length - 1] : null);
        }).catch(err => {
          if (err && err.name === "AbortError") return;
          setError(String(err && err.message ? err.message : err));
        }).finally(() => setLoadingData(false));
        return () => ctrl.abort();
      }, [runId]);

      useEffect(() => {
        if (!dataset) return;
        if (rangeStart && rangeEnd && rangeStart > rangeEnd) {
          setRangeEnd(rangeStart);
        }
        if (rangeStart && asOf && asOf < rangeStart) setAsOf(rangeStart);
        if (rangeEnd && asOf && asOf > rangeEnd) setAsOf(rangeEnd);
      }, [dataset, rangeStart, rangeEnd, asOf]);

      useEffect(() => {
        if (!dataset || !selectedTrade) {
          setHistory(null);
          return undefined;
        }
        if (historyAbort.current) historyAbort.current.abort();
        const ctrl = new AbortController();
        historyAbort.current = ctrl;
        setHistoryLoading(true);
        setHistoryError("");
        const start = dateShift(selectedTrade.date, -65);
        const end = dateShift(selectedTrade.date, 20);
        fetchDashboard("history", {
          symbol: selectedTrade.code,
          start: start,
          end: end,
        }, ctrl.signal).then(body => {
          setHistory(body);
        }).catch(err => {
          if (err && err.name === "AbortError") return;
          setHistory(null);
          setHistoryError(String(err && err.message ? err.message : err));
        }).finally(() => setHistoryLoading(false));
        return () => ctrl.abort();
      }, [dataset, selectedTrade]);

      useEffect(() => {
        if (!dataset || !selectedTrade) {
          setFlow(null);
          return undefined;
        }
        if (flowAbort.current) flowAbort.current.abort();
        const ctrl = new AbortController();
        flowAbort.current = ctrl;
        setFlowLoading(true);
        setFlowError("");
        fetchDashboard("backtest_flow", {
          symbol: selectedTrade.code,
          date: selectedTrade.date,
        }, ctrl.signal).then(body => {
          setFlow(body);
        }).catch(err => {
          if (err && err.name === "AbortError") return;
          setFlow(null);
          setFlowError(String(err && err.message ? err.message : err));
        }).finally(() => setFlowLoading(false));
        return () => ctrl.abort();
      }, [dataset, selectedTrade]);

      const summary = (dataset && dataset.summary) || {};
      const equity = dataset && Array.isArray(dataset.equity) ? dataset.equity : [];
      const trades = dataset && Array.isArray(dataset.trades) ? dataset.trades : [];
      const rangeEquity = equity.filter(x => (!rangeStart || x.date >= rangeStart) && (!rangeEnd || x.date <= rangeEnd));
      let asOfIndex = rangeEquity.findIndex(x => x.date >= asOf);
      if (asOfIndex < 0) asOfIndex = Math.max(0, rangeEquity.length - 1);
      const currentPoint = rangeEquity[asOfIndex] || null;
      const replayDate = currentPoint ? currentPoint.date : asOf;
      const startValue = rangeEquity.length ? Number(rangeEquity[0].total_value) || 0 : 0;
      const currentValue = currentPoint ? Number(currentPoint.total_value) || 0 : 0;
      const replayReturn = startValue ? currentValue / startValue - 1 : 0;
      let peak = startValue;
      let maxDrawdown = 0;
      rangeEquity.slice(0, asOfIndex + 1).forEach(x => {
        const v = Number(x.total_value) || 0;
        peak = Math.max(peak, v);
        if (peak > 0) maxDrawdown = Math.min(maxDrawdown, v / peak - 1);
      });
      const rangeTrades = trades.filter(t => (!rangeStart || t.date >= rangeStart) && (!rangeEnd || t.date <= rangeEnd));
      const replayTrades = rangeTrades.filter(t => t.date <= replayDate);
      const reconstructed = reconstructPositions(trades, replayDate);
      const positions = currentPoint && Number(currentPoint.n_pos) === 0 ? [] : reconstructed;
      const reconstructedValue = reconstructed.reduce((sum, p) => sum + (Number(p.market_value) || 0), 0);
      const positionMismatch = !!currentPoint && (
        Number(currentPoint.n_pos || 0) !== positions.length ||
        Math.abs(reconstructedValue - Number(currentPoint.positions_value || 0)) > Math.max(100, Number(currentPoint.positions_value || 0) * 0.05)
      );
      const normalizedQuery = tradeQuery.trim().toLowerCase();
      const filteredTrades = rangeTrades.filter(t => {
        if (!normalizedQuery) return true;
        return (t.code + " " + t.side + " " + t.date).toLowerCase().includes(normalizedQuery);
      });
      const shownTrades = filteredTrades.slice(-500).reverse();

      useEffect(() => {
        if (!dataset || !selectedTrade || selectedTrade.date <= replayDate) return;
        const prior = trades.filter(t => t.date <= replayDate).slice(-1)[0] || null;
        if (prior) setSelectedTrade(prior);
      }, [replayDate, dataset, selectedTrade, trades]);

      const currentRun = runs.find(r => r.id === runId) || null;
      let runOptions = runs.filter(r => {
        if (!runSearch.trim()) return true;
        const q = runSearch.trim().toLowerCase();
        return (r.id + " " + r.name + " " + (r.strategy || "")).toLowerCase().includes(q);
      });
      if (currentRun && !runOptions.some(r => r.id === currentRun.id)) runOptions = [currentRun, ...runOptions];
      const runLabel = r => r.name + " · " + r.start + "~" + r.end + " · " + r.trades + "笔";

      return h("div", { className: "thsd-root" },
        h("div", { className: "thsd-head" },
          h("div", null,
            h("div", { className: "thsd-title" }, "回测回放 · 交易复盘"),
            h("div", { className: "thsd-sub" }, "选择回测与时期 · 查看权益曲线、回放持仓和逐笔交易记录")
          ),
          h("div", { className: "thsd-head-actions" },
            h("button", { className: "thsd-btn", onClick: loadRuns, disabled: loadingRuns }, loadingRuns ? "载入中" : "刷新回测列表")
          )
        ),
        error ? h("div", { className: "thsd-error" }, error) : null,
        h("div", { className: "thsd-tools" },
          h("div", { className: "thsd-field" },
            h("label", null, "回测 · " + runs.length + " 个"),
            h("select", { className: "thsd-select", value: runId, onChange: e => setRunId(e.target.value) },
              runOptions.map(r => h("option", { key: r.id, value: r.id }, runLabel(r))))
          ),
          h("div", { className: "thsd-field" },
            h("label", null, "搜索回测"),
            h("input", { className: "thsd-input wide", value: runSearch, placeholder: "名称 / 策略 / 日期",
              onChange: e => setRunSearch(e.target.value) })
          ),
          h("div", { className: "thsd-field" },
            h("label", null, "开始日期"),
            h("input", { className: "thsd-input wide", type: "date", value: rangeStart,
              min: summary.start || "", max: rangeEnd || summary.end || "",
              onChange: e => setRangeStart(e.target.value) })
          ),
          h("div", { className: "thsd-field" },
            h("label", null, "结束日期"),
            h("input", { className: "thsd-input wide", type: "date", value: rangeEnd,
              min: rangeStart || summary.start || "", max: summary.end || "",
              onChange: e => setRangeEnd(e.target.value) })
          ),
          h("div", { className: "thsd-field" },
            h("label", null, "回放日期 " + replayDate),
            h("div", { className: "thsd-slider-wrap" },
              h("input", { className: "thsd-slider", type: "range", min: 0,
                max: Math.max(0, rangeEquity.length - 1), value: Math.min(asOfIndex, Math.max(0, rangeEquity.length - 1)),
                onChange: e => { const point = rangeEquity[Number(e.target.value)]; if (point) setAsOf(point.date); } }),
              h("span", { className: "thsd-slider-date" }, replayDate)
            )
          )
        ),
        currentRun ? h("div", { className: "thsd-run-note", style: { marginBottom: "10px" } },
          "策略: " + (currentRun.strategy || "--") + " · 全区间收益 " + fmtPct(currentRun.total_return * 100) +
          " · 全区间回撤 " + fmtPct(currentRun.max_drawdown * 100) + " · " + currentRun.trades + " 笔交易"
        ) : null,
        loadingData ? h("div", { className: "thsd-loading" }, "正在读取回测数据…") : null,
        h("div", { className: "thsd-cards" },
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "回放区间收益"), h("div", { className: "thsd-card-value " + tone(replayReturn) }, fmtPct(replayReturn * 100)), h("div", { className: "thsd-card-sub" }, rangeStart + " ~ " + replayDate)),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "区间最大回撤"), h("div", { className: "thsd-card-value thsd-down" }, fmtPct(maxDrawdown * 100)), h("div", { className: "thsd-card-sub" }, "截至回放日期")),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "交易笔数"), h("div", { className: "thsd-card-value" }, String(replayTrades.length)), h("div", { className: "thsd-card-sub" }, "区间内已发生")),
          h("div", { className: "thsd-card" }, h("div", { className: "thsd-card-label" }, "回放权益"), h("div", { className: "thsd-card-value" }, fmtMoney(currentValue)), h("div", { className: "thsd-card-sub" }, "现金 " + fmtMoney(currentPoint && currentPoint.cash)))
        ),
        h("div", { className: "thsd-layout" },
          h("div", null,
            h("section", { className: "thsd-panel" },
              h("div", { className: "thsd-panel-head" },
                h("span", { className: "thsd-panel-title" }, "回放持仓"),
                h("span", { className: "thsd-panel-meta" }, replayDate + " · " + positions.length + " 个")
              ),
              h("div", { className: "thsd-pos-wrap" },
                positions.length === 0 ? h("div", { className: "thsd-empty" }, "该日期无持仓") :
                  h("table", { className: "thsd-table" },
                    h("thead", null, h("tr", null, h("th", null, "代码"), h("th", null, "数量"), h("th", null, "均价"), h("th", null, "现价"), h("th", null, "市值"), h("th", null, "浮盈"))),
                    h("tbody", null, positions.map(p => h("tr", { key: p.symbol },
                      h("td", null, h("b", null, p.symbol)),
                      h("td", null, String(p.quantity)),
                      h("td", null, fmtPrice(p.avg_cost)),
                      h("td", null, fmtPrice(p.last_price)),
                      h("td", null, fmtMoney(p.market_value)),
                      h("td", { className: tone(p.pnl) }, fmtSigned(p.pnl))
                    )))
                  )
              ),
              positionMismatch ? h("div", { className: "thsd-backtest-note" }, "成交记录与权益快照不完全一致，持仓为按成交重放的估算值。") : null
            ),
            h("section", { className: "thsd-panel", style: { marginTop: "12px" } },
              h("div", { className: "thsd-panel-head" },
                h("span", { className: "thsd-panel-title" }, "交易记录"),
                h("input", { className: "thsd-input", value: tradeQuery, placeholder: "代码 / 方向 / 日期",
                  style: { marginLeft: "auto", width: "150px" }, onChange: e => setTradeQuery(e.target.value) }),
                h("span", { className: "thsd-panel-meta" }, filteredTrades.length + " 笔")
              ),
              h("div", { className: "thsd-trade-wrap" },
                shownTrades.length === 0 ? h("div", { className: "thsd-empty" }, "当前筛选无交易") :
                  h("table", { className: "thsd-table thsd-trade-table" },
                    h("thead", null, h("tr", null, h("th", null, "日期"), h("th", null, "代码"), h("th", null, "方向"), h("th", null, "价格"), h("th", null, "数量"), h("th", null, "金额"), h("th", null, "费用"))),
                    h("tbody", null, shownTrades.map((t, i) => h("tr", {
                      key: t.date + t.code + t.side + i,
                      className: "row" + (selectedTrade && selectedTrade.date === t.date && selectedTrade.code === t.code && selectedTrade.side === t.side ? " selected" : ""),
                      onClick: () => { setSelectedTrade(t); if (t.date < rangeStart) setAsOf(rangeStart); else if (t.date > rangeEnd) setAsOf(rangeEnd); else setAsOf(t.date); }
                    },
                      h("td", null, t.date), h("td", null, t.code),
                      h("td", { className: t.side === "buy" ? "thsd-side-buy" : "thsd-side-sell" }, t.side === "buy" ? "买入" : "卖出"),
                      h("td", null, fmtPrice(t.price)), h("td", null, String(t.quantity)),
                      h("td", null, fmtMoney(t.value)), h("td", null, fmtPrice(t.fee))
                    )))
                  )
              ),
              filteredTrades.length > shownTrades.length ? h("div", { className: "thsd-backtest-note" }, "仅显示最近 500 笔；可使用筛选缩小范围。") : null
            )
          ),
          h("div", null,
            h("section", { className: "thsd-panel" },
              h("div", { className: "thsd-panel-head" },
                h("span", { className: "thsd-panel-title" }, "权益曲线"),
                h("span", { className: "thsd-panel-meta" }, "点击曲线定位回放日期")
              ),
              h(EquityChart, { equity: rangeEquity, asOf: replayDate, selectedTrade: selectedTrade,
                onPick: date => setAsOf(date) })
            ),
            h("section", { className: "thsd-panel", style: { marginTop: "12px" } },
              h("div", { className: "thsd-panel-head" },
                h("span", { className: "thsd-panel-title" }, selectedTrade ? "个股回放 · " + selectedTrade.code : "个股回放"),
                h("span", { className: "thsd-panel-meta" }, selectedTrade ? selectedTrade.date + " · " + (selectedTrade.side === "buy" ? "买入" : "卖出") + " " + fmtPrice(selectedTrade.price) : "点击交易记录")
              ),
              historyLoading ? h("div", { className: "thsd-loading" }, "正在读取历史 K 线…") :
                historyError ? h("div", { className: "thsd-error", style: { margin: "10px 12px" } }, historyError) :
                  history ? h("div", { className: "thsd-chart-small" }, h(KLineChart, { chart: history })) :
                    h("div", { className: "thsd-empty" }, "选择一笔交易查看其前后日线 K 线")
            ),
            h("div", { style: { marginTop: "12px" } },
              flowLoading ? h("div", { className: "thsd-loading" }, "正在读取历史资金流…") :
                flowError ? h("div", { className: "thsd-error", style: { margin: "10px 12px" } }, flowError) :
                  flow ? h(FlowPanel, { flow: flow, heading: "历史资金流", caption: "当日 / 近5日" }) :
                    h("div", { className: "thsd-empty" }, "选择交易后显示历史资金流")
            )
          )
        ),
        h("div", { className: "thsd-backtest-note" },
          "回测回放使用历史日线与成交记录；历史分钟 K、逐笔盘口/L2 无法复原。资金曲线与持仓为按成交记录重放结果，仅用于研究复盘。"
        ),
        h("div", { className: "thsd-foot" },
          h("span", null, "回测目录: ", (dataset && dataset.root) || "未配置"),
          h("span", null, "数据仅来自本地回测产物，不会触发模拟盘下单。")
        )
      );
    }
    exports.__components = { Dashboard, BacktestPanel, KLineChart, EquityChart, FlowPanel, OrderBook, PanelIcon, BacktestIcon };

    exports.inject = ["slots"];
    exports.apply = function apply(ctx) {
      injectStyles();
      ctx.slots.inject("main", () => ctx.slots.register({
        name: "main",
        key: PANEL_ID
      }, () => h(Dashboard)));
      ctx.slots.inject("sidebar.panellist", () => ctx.slots.register({
        name: "sidebar.panellist",
        id: PANEL_ID,
        order: 15,
        label: () => "模拟持仓"
      }, props => h(PanelIcon, { size: props && props.size ? props.size : 18, active: props && props.active })));
      ctx.slots.inject("main", () => ctx.slots.register({
        name: "main",
        key: BACKTEST_PANEL_ID
      }, () => h(BacktestPanel)));
      ctx.slots.inject("sidebar.panellist", () => ctx.slots.register({
        name: "sidebar.panellist",
        id: BACKTEST_PANEL_ID,
        order: 16,
        label: () => "回测回放"
      }, props => h(BacktestIcon, { size: props && props.size ? props.size : 18, active: props && props.active })));
    };

    return module.exports;
  }
});
