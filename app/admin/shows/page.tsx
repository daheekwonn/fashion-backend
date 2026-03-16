'use client';

import { useEffect, useRef, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface TrendItem {
  id: number;
  rank: number;
  name: string;
  sub: string;
  score: number;
  breakdown: string;
  badge: string;
  badgeType: 'up' | 'new' | 'dn';
}

interface Post {
  kicker: string;
  title: string;
  excerpt: string;
  date: string;
}

interface ArchiveCard {
  color: string;
  pantoneLabel: string;
  pantoneTextColor: string;
  season: string;
  title: string;
}

// ─── Static data (swap these with fetch() calls to Railway once live) ─────────
const TRENDS: TrendItem[] = [
  { id: 1, rank: 1, name: 'Shearling Coat',    sub: 'Outerwear · Gucci, Bottega, Loewe',        score: 94.1, breakdown: 'R:47 · S:28 · V:19', badge: '+12.4 ↑',   badgeType: 'up'  },
  { id: 2, rank: 2, name: 'Chanel FW26',        sub: 'Show · Matthieu Blazy debut',              score: 91.2, breakdown: 'R:50 · S:27 · V:14', badge: 'Season high',badgeType: 'new' },
  { id: 3, rank: 3, name: 'Leather Bomber',     sub: 'Outerwear · +200% search post-Gucci',      score: 88.7, breakdown: 'R:44 · S:30 · V:15', badge: '+8.2 ↑',    badgeType: 'up'  },
  { id: 4, rank: 4, name: 'Dior FW26',          sub: 'Show · Jonathan Anderson era begins',      score: 87.4, breakdown: 'R:48 · S:25 · V:14', badge: 'New entry',  badgeType: 'new' },
  { id: 5, rank: 5, name: 'Prairie Silhouette', sub: 'Dress · Chloé, Zimmermann',                score: 78.6, breakdown: 'R:41 · S:22 · V:16', badge: 'New entry',  badgeType: 'new' },
  { id: 6, rank: 6, name: 'Wide-Leg Trouser',   sub: 'Trousers · Consistent across all cities', score: 74.3, breakdown: 'R:38 · S:21 · V:15', badge: '−2.1 ↓',    badgeType: 'dn'  },
];

const POSTS: Post[] = [
  { kicker: 'Data · Milan FW26',       title: 'The leather bomber is a macro trend',           excerpt: '200% search spike, 7 major shows, 3 cities. A data-driven case for the jacket of the season.',                                 date: 'Mar 6, 2026' },
  { kicker: 'Forecast · FW26',         title: 'Prairie or bust: the silhouette taking over',   excerpt: 'Chloé made it obvious but the signal started in Copenhagen. A data-driven case for the maxi dress revival.',                   date: 'Mar 4, 2026' },
  { kicker: 'Opinion · Paris FW26',    title: "Why Chanel's mushroom set was the moment",      excerpt: "The SS26 couture set predicted everything Blazy would do next. Here's what the data says.",                                    date: 'Mar 8, 2026' },
  { kicker: 'Cultural Context · FW26', title: 'Why recession dressing always brings the coat', excerpt: "Shearling at #1 isn't a coincidence. A historical pattern analysis of outerwear trends and economic anxiety.",                 date: 'Mar 2, 2026' },
];

const ARCHIVE: ArchiveCard[] = [
  { color: '#A47764', pantoneLabel: 'Mocha Mousse', pantoneTextColor: '#fff',    season: 'FW25 · Paris',    title: 'The quiet luxury correction'         },
  { color: '#FFBE98', pantoneLabel: 'Peach Fuzz',   pantoneTextColor: '#6B5040', season: 'FW24 · London',   title: 'Softening of power dressing'         },
  { color: '#BE3455', pantoneLabel: 'Viva Magenta', pantoneTextColor: '#fff',    season: 'FW23 · Milan',    title: 'Viva Magenta was never just a color' },
  { color: '#6667AB', pantoneLabel: 'Very Peri',    pantoneTextColor: '#fff',    season: 'FW22 · New York', title: 'The periwinkle moment nobody predicted' },
];

const TICKER_ITEMS = [
  'Shearling Coat  94.1', 'Chanel FW26  91.2', 'Leather Bomber  88.7',
  'Dior FW26  87.4', 'Prairie Silhouette  78.6', 'Wide-Leg Trouser  74.3',
  'Burgundy  +180%', 'Paris FW26', 'Milan FW26', 'London FW26', 'New York FW26',
];

const CITIES = ['All', 'Paris', 'Milan', 'London', 'New York', 'Copenhagen'];

// ─── Detection boxes ──────────────────────────────────────────────────────────
const DETECTIONS = [
  { id: 0, panel: 0, style: { top: '18%', left: '22%', width: '52%', height: '54%' }, label: 'Silhouette',    val: 94.1, delay: 500  },
  { id: 1, panel: 0, style: { top: '62%', left: '8%',  width: '30%', height: '26%' }, label: 'Material',      val: 74.3, delay: 1200 },
  { id: 2, panel: 1, style: { top: '14%', left: '18%', width: '56%', height: '52%' }, label: 'Outerwear',     val: 88.7, delay: 1900 },
  { id: 3, panel: 1, style: { top: '58%', left: '55%', width: '34%', height: '30%' }, label: 'Colour Signal', val: 78.6, delay: 2550 },
];

// ─── Page component ───────────────────────────────────────────────────────────
export default function HomePage() {
  const [panelsLoaded, setPanelsLoaded] = useState([false, false]);
  const [detVisible,   setDetVisible]   = useState([false, false, false, false]);
  const [detScores,    setDetScores]    = useState([0, 0, 0, 0]);
  const [titleVisible, setTitleVisible] = useState(false);
  const [detCount,     setDetCount]     = useState(0);
  const [activeCity,   setActiveCity]   = useState('All');
  const imgRefs        = useRef<(HTMLImageElement | null)[]>([null, null]);
  const sequenceStarted = useRef(false);

  function countUp(index: number, target: number, duration: number) {
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const val = parseFloat((target * (1 - Math.pow(1 - p, 3))).toFixed(1));
      setDetScores(prev => { const next = [...prev]; next[index] = val; return next; });
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function startSequence() {
    if (sequenceStarted.current) return;
    sequenceStarted.current = true;
    DETECTIONS.forEach(({ id, val, delay }) => {
      setTimeout(() => {
        setDetVisible(prev => { const next = [...prev]; next[id] = true; return next; });
        countUp(id, val, 700);
        setDetCount(c => c + 1);
      }, delay);
    });
    setTimeout(() => setTitleVisible(true), 3300);
  }

  function handleImgLoad(index: number) {
    setPanelsLoaded(prev => {
      const next = [...prev];
      next[index] = true;
      if (next.every(Boolean)) setTimeout(startSequence, 600);
      return next;
    });
  }

  useEffect(() => {
    imgRefs.current.forEach((img, i) => {
      if (img?.complete) handleImgLoad(i);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const badgeClass = (type: TrendItem['badgeType']) =>
    type === 'up' ? 'badge-up' : type === 'dn' ? 'badge-dn' : 'badge-new';

  return (
    <>
      <style>{`
        @import url('https://api.fontshare.com/v2/css?f[]=ranade@300,400,500,600,700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600;1,700&family=Geist+Mono:wght@300;400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }

        :root {
          --ink:   #0C0B09;
          --white: #FFFFFF;
          --cream: #F5F2ED;
          --warm:  #EDE9E2;
          --mid:   #5A5550;
          --light: #A09A94;
          --bd:    rgba(12,11,9,0.1);
          --f-mono:    'Geist Mono', monospace;
          --f-display: 'Ranade', sans-serif;
          --f-body:    'Lora', Georgia, serif;
        }

        body { background:#fff; color:var(--ink); -webkit-font-smoothing:antialiased; }

        /* ── Ticker ── */
        .ticker { background:var(--ink); overflow:hidden; white-space:nowrap; padding:8px 0; }
        .ticker-inner { display:inline-flex; animation:tick 48s linear infinite; }
        .ticker-inner span { font-family:var(--f-mono); font-size:9.5px; letter-spacing:0.13em; color:rgba(255,255,255,0.32); padding:0 42px; }
        @keyframes tick { from{transform:translateX(0)} to{transform:translateX(-50%)} }

        /* ── Nav ── */
        .nav { height:58px; display:flex; align-items:center; justify-content:space-between; padding:0 52px; background:#fff; border-bottom:1px solid var(--bd); position:sticky; top:0; z-index:100; }
        .nav-logo { font-family:var(--f-display); font-size:17px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--ink); text-decoration:none; }
        .nav-links { display:flex; gap:36px; list-style:none; }
        .nav-links a { font-family:var(--f-mono); font-size:9.5px; letter-spacing:0.12em; text-transform:uppercase; color:var(--light); text-decoration:none; transition:color .15s; }
        .nav-links a:hover { color:var(--ink); }
        .nav-pill { font-family:var(--f-mono); font-size:9px; letter-spacing:0.13em; text-transform:uppercase; border:1px solid var(--bd); color:var(--light); padding:5px 13px; }

        /* ── Hero ── */
        .hero { position:relative; width:100%; height:calc(100vh - 84px); min-height:600px; background:#fff; overflow:hidden; display:grid; grid-template-columns:1fr 1fr; }
        .img-panel { position:relative; overflow:hidden; opacity:0; transition:opacity 1s ease; border-right:1px solid var(--bd); }
        .img-panel:last-of-type { border-right:none; }
        .img-panel.loaded { opacity:1; }
        .img-panel img { width:100%; height:100%; object-fit:cover; object-position:top center; filter:grayscale(15%) brightness(0.86) contrast(1.04); display:block; }
        .cell-cam { position:absolute; top:14px; left:16px; font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.14em; text-transform:uppercase; color:rgba(255,255,255,0.38); z-index:5; }

        /* detection boxes */
        .det-box { position:absolute; z-index:30; opacity:0; transform:scale(1.04); transition:opacity .2s ease, transform .3s cubic-bezier(.22,1,.36,1); pointer-events:none; }
        .det-box.show { opacity:1; transform:scale(1); }
        .c { position:absolute; }
        .c-tl { top:0;left:0;  border-top:2px solid var(--ink); border-left:2px solid var(--ink);   width:16px;height:16px; }
        .c-tr { top:0;right:0; border-top:2px solid var(--ink); border-right:2px solid var(--ink);  width:16px;height:16px; }
        .c-bl { bottom:0;left:0;  border-bottom:2px solid var(--ink); border-left:2px solid var(--ink);  width:16px;height:16px; }
        .c-br { bottom:0;right:0; border-bottom:2px solid var(--ink); border-right:2px solid var(--ink); width:16px;height:16px; }
        .det-label { position:absolute; top:-28px; left:-1px; background:var(--ink); padding:4px 10px; display:flex; align-items:center; gap:10px; white-space:nowrap; }
        .det-label-text { font-family:var(--f-mono); font-size:9px; font-weight:500; letter-spacing:0.12em; text-transform:uppercase; color:#fff; }
        .det-score { font-family:var(--f-mono); font-size:11px; font-weight:500; color:rgba(255,255,255,0.55); min-width:28px; }

        /* HUD */
        .hud { position:absolute; z-index:40; pointer-events:none; }
        .hud-bl { bottom:20px; left:18px; }
        .hud-br { bottom:20px; right:18px; }
        .hud-counter { font-family:var(--f-mono); font-size:9px; letter-spacing:0.13em; text-transform:uppercase; color:rgba(12,11,9,0.28); }
        .hud-counter b { font-size:18px; font-weight:500; color:var(--ink); letter-spacing:-0.02em; }
        .rec-indicator { display:flex; align-items:center; gap:7px; font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.14em; text-transform:uppercase; color:rgba(12,11,9,0.24); }
        .rec-dot { width:6px;height:6px;border-radius:50%;background:var(--ink);opacity:.6; animation:blink 1.4s ease-in-out infinite; }
        @keyframes blink { 0%,100%{opacity:.6} 50%{opacity:.12} }

        /* hero title */
        .hero-title-wrap { position:absolute; inset:0; z-index:50; display:flex; align-items:center; justify-content:center; pointer-events:none; }
        .hero-title-inner { text-align:center; opacity:0; transform:translateY(10px); transition:opacity .65s ease, transform .65s ease; }
        .hero-title-inner.show { opacity:1; transform:translateY(0); pointer-events:all; }
        .title-backdrop { display:inline-block; background:rgba(255,255,255,0.84); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); padding:36px 52px 40px; border:1px solid rgba(12,11,9,0.07); }
        .hero-eyebrow { font-family:var(--f-mono); font-size:9.5px; letter-spacing:0.26em; text-transform:uppercase; color:var(--light); margin-bottom:10px; display:flex; align-items:center; justify-content:center; gap:12px; }
        .hero-eyebrow::before,.hero-eyebrow::after { content:''; width:18px; height:1px; background:var(--light); }
        .hero-title { font-family:var(--f-display); font-size:clamp(72px,10vw,130px); font-weight:700; line-height:0.88; letter-spacing:-0.03em; color:var(--ink); margin-bottom:14px; }
        .hero-desc { font-family:var(--f-body); font-size:15px; font-style:italic; font-weight:500; color:var(--mid); margin-bottom:26px; }
        .hero-cta { display:inline-flex; align-items:center; gap:10px; font-family:var(--f-mono); font-size:10px; letter-spacing:0.16em; text-transform:uppercase; color:#fff; background:var(--ink); padding:13px 28px; text-decoration:none; transition:opacity .2s; }
        .hero-cta:hover { opacity:.72; }
        .arr { display:inline-block; transition:transform .18s; }
        .hero-cta:hover .arr { transform:translateX(5px); }

        /* ── Season bar ── */
        .season-bar { display:flex; align-items:stretch; padding:0 52px; border-bottom:1px solid var(--bd); background:#fff; overflow-x:auto; }
        .season-lbl { font-family:var(--f-mono); font-size:9px; letter-spacing:0.14em; text-transform:uppercase; color:var(--light); display:flex; align-items:center; padding-right:22px; border-right:1px solid var(--bd); margin-right:18px; white-space:nowrap; flex-shrink:0; }
        .sbtn { font-family:var(--f-mono); font-size:10px; letter-spacing:0.1em; text-transform:uppercase; background:none; border:none; cursor:pointer; padding:14px 16px; color:var(--light); position:relative; transition:color .15s; flex-shrink:0; }
        .sbtn::after { content:''; position:absolute; bottom:0; left:16px; right:16px; height:1.5px; background:var(--ink); transform:scaleX(0); transition:transform .2s; }
        .sbtn:hover,.sbtn.active { color:var(--ink); }
        .sbtn.active::after,.sbtn:hover::after { transform:scaleX(1); }

        /* ── Leaderboard ── */
        .board { padding:56px 52px; border-bottom:1px solid var(--bd); background:#fff; }
        .section-head { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:32px; padding-bottom:18px; border-bottom:1px solid var(--bd); }
        .section-title { font-family:var(--f-display); font-size:46px; font-weight:700; letter-spacing:-0.02em; line-height:1; color:var(--ink); }
        .section-note { font-family:var(--f-mono); font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:var(--light); }
        .t-row { display:flex; align-items:center; padding:20px 0; border-bottom:1px solid var(--bd); cursor:pointer; gap:18px; transition:opacity .15s; }
        .t-row:last-child { border-bottom:none; }
        .t-row:hover { opacity:.4; }
        .t-rank { font-family:var(--f-mono); font-size:10px; font-weight:300; color:rgba(12,11,9,0.18); width:24px; flex-shrink:0; }
        .t-name { flex:1; }
        .t-name-main { font-family:var(--f-display); font-size:28px; font-weight:700; letter-spacing:-0.02em; display:block; line-height:1; color:var(--ink); }
        .t-sub { font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.08em; text-transform:uppercase; color:var(--light); display:block; margin-top:4px; }
        .t-right { display:flex; flex-direction:column; align-items:flex-end; gap:5px; flex-shrink:0; }
        .t-num { font-family:var(--f-mono); font-size:26px; font-weight:500; letter-spacing:-0.02em; color:var(--ink); line-height:1; }
        .t-track { width:72px; height:1.5px; background:rgba(12,11,9,0.08); }
        .t-fill { height:100%; background:var(--ink); }
        .t-bd { font-family:var(--f-mono); font-size:8px; color:var(--light); letter-spacing:0.06em; }
        .t-badge { font-family:var(--f-mono); font-size:8px; letter-spacing:0.06em; padding:2px 7px; }
        .badge-up  { background:rgba(30,107,60,0.09);  color:#1E6B3C; }
        .badge-new { background:rgba(12,11,9,0.05);    color:var(--ink); }
        .badge-dn  { background:rgba(160,50,40,0.07);  color:#9B3228; }

        /* ── Feature ── */
        .feature { display:grid; grid-template-columns:1fr 1fr; border-bottom:1px solid var(--bd); }
        .feature-img { position:relative; overflow:hidden; min-height:500px; background:var(--warm); }
        .feature-img img { width:100%; height:100%; object-fit:cover; object-position:top center; filter:grayscale(10%) brightness(0.88) contrast(1.03); display:block; }
        .feature-img-caption { position:absolute; bottom:20px; left:20px; font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.13em; text-transform:uppercase; color:rgba(255,255,255,0.4); }
        .feature-content { padding:52px 48px; background:#fff; display:flex; flex-direction:column; justify-content:center; border-left:1px solid var(--bd); }
        .feature-kicker { font-family:var(--f-mono); font-size:9px; letter-spacing:0.15em; text-transform:uppercase; color:var(--light); margin-bottom:18px; display:flex; align-items:center; gap:10px; }
        .feature-kicker::before { content:''; width:18px; height:1px; background:var(--light); }
        .feature-title { font-family:var(--f-display); font-size:44px; font-weight:700; line-height:1.04; letter-spacing:-0.02em; color:var(--ink); margin-bottom:18px; }
        .feature-body { font-family:var(--f-body); font-size:15.5px; font-weight:500; line-height:1.78; color:var(--ink); }
        .feature-read { font-family:var(--f-mono); font-size:9.5px; letter-spacing:0.14em; text-transform:uppercase; color:var(--ink); display:flex; align-items:center; gap:8px; text-decoration:none; margin-top:28px; transition:gap .15s; }
        .feature-read:hover { gap:14px; }

        /* ── Stats strip ── */
        .stats-strip { display:grid; grid-template-columns:repeat(4,1fr); background:var(--ink); }
        .stat-cell { padding:52px 44px 56px; border-right:1px solid rgba(255,255,255,0.08); }
        .stat-cell:last-child { border-right:none; }
        .stat-num { font-family:var(--f-display); font-size:clamp(52px,5.5vw,72px); font-weight:700; color:#fff; line-height:1; margin-bottom:16px; letter-spacing:-0.03em; }
        .stat-num .prefix { font-size:0.6em; font-weight:700; vertical-align:0.12em; letter-spacing:0; }
        .stat-num .suffix { font-size:0.75em; font-weight:700; }
        .stat-label { font-family:var(--f-mono); font-size:9px; letter-spacing:0.2em; text-transform:uppercase; color:rgba(255,255,255,0.28); margin-bottom:20px; line-height:1.6; }
        .stat-body { font-family:var(--f-body); font-size:14px; font-weight:500; color:rgba(255,255,255,0.38); line-height:1.75; }

        /* ── Latest analysis ── */
        .posts-section { padding:56px 52px; border-bottom:1px solid var(--bd); }
        .posts-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:0; margin-top:32px; }
        .p-card { padding:28px 40px 28px 0; border-bottom:1px solid var(--bd); cursor:pointer; transition:opacity .15s; }
        .p-card:nth-child(even) { padding:28px 0 28px 40px; border-left:1px solid var(--bd); }
        .p-card:hover { opacity:.45; }
        .p-card:nth-last-child(-n+2) { border-bottom:none; }
        .p-kicker { font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.14em; text-transform:uppercase; color:var(--light); margin-bottom:10px; }
        .p-title { font-family:var(--f-display); font-size:22px; font-weight:700; letter-spacing:-0.01em; line-height:1.1; color:var(--ink); margin-bottom:9px; }
        .p-excerpt { font-family:var(--f-body); font-size:14px; font-weight:500; line-height:1.7; color:var(--ink); }
        .p-foot { display:flex; justify-content:space-between; align-items:center; margin-top:12px; }
        .p-date { font-family:var(--f-mono); font-size:8.5px; letter-spacing:0.1em; text-transform:uppercase; color:var(--light); }
        .p-arr { color:var(--light); font-size:14px; display:inline-block; transition:transform .15s; }
        .p-card:hover .p-arr { transform:translateX(4px); }

        /* ── Archive ── */
        .archive { padding:56px 52px; border-bottom:1px solid var(--bd); background:#fff; }
        .archive-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:0; margin-top:32px; }
        .arc-card { padding:0 28px 0 0; border-right:1px solid var(--bd); cursor:pointer; transition:opacity .15s; }
        .arc-card:last-child { padding:0 0 0 28px; border-right:none; }
        .arc-card:nth-child(2),.arc-card:nth-child(3) { padding:0 28px; }
        .arc-card:hover { opacity:.6; }
        .arc-swatch { width:100%; height:64px; margin-bottom:14px; display:flex; align-items:flex-end; padding:8px 10px; }
        .arc-pantone { font-family:var(--f-mono); font-size:8px; letter-spacing:0.12em; text-transform:uppercase; opacity:.6; }
        .arc-season { font-family:var(--f-mono); font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:var(--light); margin-bottom:7px; display:block; }
        .arc-title { font-family:var(--f-display); font-size:18px; font-weight:700; letter-spacing:-0.01em; line-height:1.15; color:var(--ink); }
        .arc-arrow { font-family:var(--f-mono); font-size:9px; letter-spacing:0.1em; text-transform:uppercase; color:var(--light); margin-top:10px; display:flex; align-items:center; gap:6px; transition:gap .15s; }
        .arc-card:hover .arc-arrow { gap:10px; }

        /* ── Footer ── */
        footer { background:var(--ink); padding:26px 52px; display:flex; align-items:center; justify-content:space-between; }
        .f-logo { font-family:var(--f-display); font-size:16px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#fff; }
        .f-links { display:flex; gap:28px; list-style:none; }
        .f-links a { font-family:var(--f-mono); font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:rgba(255,255,255,0.3); text-decoration:none; transition:color .15s; }
        .f-links a:hover { color:rgba(255,255,255,0.7); }
        .f-copy { font-family:var(--f-mono); font-size:9px; letter-spacing:0.1em; color:rgba(255,255,255,0.2); }
      `}</style>

      {/* ── Ticker ── */}
      <div className="ticker">
        <div className="ticker-inner">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span key={i}>{item}</span>
          ))}
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="nav">
        <a href="/" className="nav-logo">Runway FYI</a>
        <ul className="nav-links">
          <li><a href="/trends">Trends</a></li>
          <li><a href="/shows">Shows</a></li>
          <li><a href="/analysis">Analysis</a></li>
          <li><a href="/archive">Archive</a></li>
        </ul>
        <span className="nav-pill">FW26</span>
      </nav>

      {/* ── Hero ── */}
      <div className="hero">
        {[0, 1].map(panelIdx => (
          <div key={panelIdx} className={`img-panel${panelsLoaded[panelIdx] ? ' loaded' : ''}`}>
            <span className="cell-cam">
              {panelIdx === 0 ? 'CAM-01 · PARIS FW26' : 'CAM-02 · MILAN FW26'}
            </span>
            <img
              ref={el => { imgRefs.current[panelIdx] = el; }}
              src={panelIdx === 0
                ? 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=900&q=80'
                : 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=900&q=80'
              }
              alt={panelIdx === 0 ? 'Paris FW26' : 'Milan FW26'}
              onLoad={() => handleImgLoad(panelIdx)}
            />
            {DETECTIONS.filter(d => d.panel === panelIdx).map(det => (
              <div
                key={det.id}
                className={`det-box${detVisible[det.id] ? ' show' : ''}`}
                style={det.style as React.CSSProperties}
              >
                <div className="det-label">
                  <span className="det-label-text">{det.label}</span>
                  <span className="det-score">{detScores[det.id].toFixed(1)}</span>
                </div>
                <span className="c c-tl" /><span className="c c-tr" />
                <span className="c c-bl" /><span className="c c-br" />
              </div>
            ))}
          </div>
        ))}

        <div className="hud hud-bl">
          <div className="hud-counter">
            Detections <b>{String(detCount).padStart(2, '0')}</b>
          </div>
        </div>
        <div className="hud hud-br">
          <div className="rec-indicator">
            <span className="rec-dot" /> Live · FW26
          </div>
        </div>

        <div className="hero-title-wrap">
          <div className={`hero-title-inner${titleVisible ? ' show' : ''}`}>
            <div className="title-backdrop">
              <div className="hero-eyebrow">Fashion Trend Intelligence</div>
              <div className="hero-title">RUNWAY<br />FYI</div>
              <p className="hero-desc">Data-driven analysis of what the season means</p>
              <a href="#trends" className="hero-cta">
                See the data <span className="arr">→</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* ── Season bar ── */}
      <div className="season-bar">
        <span className="season-lbl">FW26 Season</span>
        {CITIES.map(city => (
          <button
            key={city}
            className={`sbtn${activeCity === city ? ' active' : ''}`}
            onClick={() => setActiveCity(city)}
          >
            {city}
          </button>
        ))}
      </div>

      {/* ── Leaderboard ── */}
      <section className="board" id="trends">
        <div className="section-head">
          <h2 className="section-title">Trend Leaderboard</h2>
          <span className="section-note">FW26 Season · Composite Score</span>
        </div>
        {TRENDS.map(t => (
          <div key={t.id} className="t-row">
            <span className="t-rank">{String(t.rank).padStart(2, '0')}</span>
            <div className="t-name">
              <span className="t-name-main">{t.name}</span>
              <span className="t-sub">{t.sub}</span>
            </div>
            <div className="t-right">
              <span className="t-num">{t.score.toFixed(1)}</span>
              <div className="t-track"><div className="t-fill" style={{ width: `${t.score}%` }} /></div>
              <span className="t-bd">{t.breakdown}</span>
              <span className={`t-badge ${badgeClass(t.badgeType)}`}>{t.badge}</span>
            </div>
          </div>
        ))}
      </section>

      {/* ── Feature article ── */}
      <div className="feature">
        <div className="feature-img">
          <img
            src="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&q=80"
            alt="Dior FW26"
          />
          <div className="feature-img-caption">Dior FW26 · Paris · Placeholder</div>
        </div>
        <div className="feature-content">
          <div className="feature-kicker">Opinion · Paris FW26 · Dior</div>
          <h2 className="feature-title">Jonathan Anderson redefines what Dior means now</h2>
          <p className="feature-body">
            The data agreed before the critics did. Searches for &ldquo;Dior aesthetic&rdquo; climbed 140% in the 48 hours after the show — a signal we&rsquo;d been tracking since Anderson&rsquo;s appointment was announced in late 2025. The score of 87.4 is the highest individual show score of the season so far, driven by an unusually high runway component of 48 points out of 50. Every look was referenced somewhere within 24 hours of the final bow.
          </p>
          <a href="#" className="feature-read">Read full analysis <span className="arr">→</span></a>
        </div>
      </div>

      {/* ── Stats strip ── */}
      <div className="stats-strip">
        <div className="stat-cell">
          <div className="stat-num"><span className="prefix">+</span>200<span className="suffix">%</span></div>
          <div className="stat-label">Leather Bomber<br />Searches</div>
          <p className="stat-body">Following Gucci&rsquo;s FW26 Milan show. Peak search volume recorded 48hrs post-show.</p>
        </div>
        <div className="stat-cell">
          <div className="stat-num">34</div>
          <div className="stat-label">Collections<br />with Burgundy</div>
          <p className="stat-body">Across NYFW, LFW, MFW, and PFW. Up from 12 collections in SS26.</p>
        </div>
        <div className="stat-cell">
          <div className="stat-num">89<span className="suffix">%</span></div>
          <div className="stat-label">Prairie Trend<br />Growth</div>
          <p className="stat-body">YoY increase in search interest for prairie and romantic silhouettes.</p>
        </div>
        <div className="stat-cell">
          <div className="stat-num"><span className="prefix">#</span>1</div>
          <div className="stat-label">Most Searched<br />Show</div>
          <p className="stat-body">Chanel FW26 Paris led search volume for 11 consecutive days post-show.</p>
        </div>
      </div>

      {/* ── Latest analysis ── */}
      <section className="posts-section">
        <div className="section-head">
          <h2 className="section-title">Latest Analysis</h2>
          <span className="section-note">Opinion · Data · Forecasts</span>
        </div>
        <div className="posts-grid">
          {POSTS.map((post, i) => (
            <article key={i} className="p-card">
              <div className="p-kicker">{post.kicker}</div>
              <h3 className="p-title">{post.title}</h3>
              <p className="p-excerpt">{post.excerpt}</p>
              <div className="p-foot">
                <span className="p-date">{post.date}</span>
                <span className="p-arr">→</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* ── Archive ── */}
      <section className="archive">
        <div className="section-head">
          <h2 className="section-title">Archive</h2>
          <span className="section-note">Each season · Pantone Color of the Year</span>
        </div>
        <div className="archive-grid">
          {ARCHIVE.map((card, i) => (
            <div key={i} className="arc-card">
              <div className="arc-swatch" style={{ background: card.color }}>
                <span className="arc-pantone" style={{ color: card.pantoneTextColor }}>
                  {card.pantoneLabel}
                </span>
              </div>
              <span className="arc-season">{card.season}</span>
              <div className="arc-title">{card.title}</div>
              <div className="arc-arrow">View season <span>→</span></div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer>
        <span className="f-logo">Runway FYI</span>
        <ul className="f-links">
          <li><a href="https://instagram.com/databutmakeitfashion" target="_blank" rel="noopener noreferrer">Instagram</a></li>
          <li><a href="#">TikTok</a></li>
          <li><a href="#">Newsletter</a></li>
          <li><a href="#">About</a></li>
        </ul>
        <span className="f-copy">© 2026 runway.fyi</span>
      </footer>
    </>
  );
}
