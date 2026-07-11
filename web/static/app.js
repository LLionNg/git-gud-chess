const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const colorEl = document.getElementById('color');

let state = null;
let selected = null;
let busy = false;
let flipped = false;
let drag = null;

const squareEls = new Map();   // square name -> highlight layer div
const pieceEls = new Map();    // square name -> piece div

// ---------- geometry ----------

function coordsOf(square) {
  const f = FILES.indexOf(square[0]);
  const r = Number(square[1]) - 1;
  return [flipped ? 7 - f : f, flipped ? r : 7 - r];
}

function squareAtPoint(x, y) {
  const rect = boardEl.getBoundingClientRect();
  const cx = Math.floor(((x - rect.left) / rect.width) * 8);
  const cy = Math.floor(((y - rect.top) / rect.height) * 8);
  if (cx < 0 || cx > 7 || cy < 0 || cy > 7) return null;
  const f = flipped ? 7 - cx : cx;
  const r = flipped ? cy : 7 - cy;
  return FILES[f] + (r + 1);
}

function place(el, square) {
  const [x, y] = coordsOf(square);
  el.style.transform = 'translate(' + x * 100 + '%, ' + y * 100 + '%)';
}

function placeInstant(el, square) {
  el.classList.add('no-anim');
  place(el, square);
  el.offsetWidth;  // flush styles so the jump is not transitioned
  el.classList.remove('no-anim');
}

// ---------- board squares (built once, reused for highlights) ----------

function buildSquares() {
  for (const file of FILES) {
    for (let rank = 1; rank <= 8; rank += 1) {
      const square = file + rank;
      const el = document.createElement('div');
      el.className = 'square';
      el.dataset.square = square;
      boardEl.appendChild(el);
      squareEls.set(square, el);
    }
  }
  layoutSquares();
}

function layoutSquares() {
  for (const [square, el] of squareEls) {
    place(el, square);
    el.innerHTML = '';
    const [x, y] = coordsOf(square);
    const light = (FILES.indexOf(square[0]) + Number(square[1])) % 2 === 1;
    if (x === 0) el.appendChild(coordLabel(square[1], 'rank', light));
    if (y === 7) el.appendChild(coordLabel(square[0], 'file', light));
  }
  // Orientation changed, so every piece needs its transform recomputed.
  for (const [square, el] of pieceEls) placeInstant(el, square);
}

function coordLabel(text, kind, light) {
  const span = document.createElement('span');
  span.className = 'coord ' + kind + (light ? ' on-light' : ' on-dark');
  span.textContent = text;
  return span;
}

// ---------- pieces ----------

function pieceUrl(code) {
  const color = code === code.toUpperCase() ? 'w' : 'b';
  return 'url(/pieces/' + color + code.toUpperCase() + '.svg)';
}

function createPiece(code, square, fadeIn) {
  const el = document.createElement('div');
  el.className = 'piece';
  el.dataset.code = code;
  el.style.backgroundImage = pieceUrl(code);
  placeInstant(el, square);
  if (fadeIn) {
    el.classList.add('entering');
    requestAnimationFrame(() => el.classList.remove('entering'));
  }
  boardEl.appendChild(el);
  return el;
}

function setPieceCode(el, code) {
  el.dataset.code = code;
  el.style.backgroundImage = pieceUrl(code);
}

function fadeOut(el) {
  if (!el) return;
  el.classList.add('fading');
  setTimeout(() => el.remove(), 200);
}

function raiseWhileMoving(el) {
  el.classList.add('moving');
  setTimeout(() => el.classList.remove('moving'), 220);
}

function parseFen(fen) {
  const pieces = {};
  fen.split(' ')[0].split('/').forEach((row, index) => {
    const rank = 8 - index;
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) file += Number(ch);
      else { pieces[FILES[file] + rank] = ch; file += 1; }
    }
  });
  return pieces;
}

// Diff the rendered pieces against a target position; moved pieces glide,
// captures fade, new pieces (promotions) fade in.
function reconcile(target, instant) {
  const stays = new Map();
  const missing = [];
  for (const [square, code] of Object.entries(target)) {
    const el = pieceEls.get(square);
    if (el && el.dataset.code === code) stays.set(square, el);
    else missing.push([square, code]);
  }
  const pool = [];
  for (const [square, el] of pieceEls) {
    if (stays.get(square) !== el) pool.push({ square, el });
  }
  pieceEls.clear();
  for (const [square, el] of stays) pieceEls.set(square, el);
  for (const [square, code] of missing) {
    let best = -1;
    let bestDist = Infinity;
    pool.forEach((item, i) => {
      if (!item || item.el.dataset.code !== code) return;
      const [ax, ay] = coordsOf(item.square);
      const [bx, by] = coordsOf(square);
      const d = Math.hypot(ax - bx, ay - by);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    if (best >= 0) {
      const el = pool[best].el;
      pool[best] = null;
      if (instant) placeInstant(el, square);
      else { raiseWhileMoving(el); place(el, square); }
      pieceEls.set(square, el);
    } else {
      pieceEls.set(square, createPiece(code, square, !instant));
    }
  }
  for (const item of pool) if (item) fadeOut(item.el);
}

// ---------- highlights ----------

function targetsFrom(square) {
  if (!square) return [];
  return state.legal.filter(uci => uci.slice(0, 2) === square).map(uci => uci.slice(2, 4));
}

function updateHighlights(lastOverride) {
  const last = lastOverride || (state && state.last_move);
  const targets = targetsFrom(selected);
  for (const [square, el] of squareEls) {
    el.classList.toggle('selected', square === selected);
    el.classList.toggle('last', Boolean(last) && (square === last.slice(0, 2) || square === last.slice(2, 4)));
    el.classList.toggle('check', Boolean(state) && square === state.check_square);
    const isTarget = targets.includes(square);
    el.classList.toggle('dest', isTarget && !pieceEls.has(square));
    el.classList.toggle('capture', isTarget && pieceEls.has(square));
    if (!drag) el.classList.remove('hover');
  }
}

function clearSelection() {
  selected = null;
  updateHighlights();
}

// ---------- sounds (lichess standard set, decoded via WebAudio for low latency) ----------

const soundFiles = { move: '/sounds/Move.mp3', capture: '/sounds/Capture.mp3', end: '/sounds/GenericNotify.mp3' };
const soundData = {};
const soundBuffers = {};
let audioCtx = null;

for (const [name, url] of Object.entries(soundFiles)) {
  fetch(url).then(r => r.arrayBuffer()).then(buf => { soundData[name] = buf; }).catch(() => {});
}

function unlockAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();
  for (const [name, buf] of Object.entries(soundData)) {
    if (soundBuffers[name] || !buf) continue;
    audioCtx.decodeAudioData(buf.slice(0), decoded => { soundBuffers[name] = decoded; });
  }
}

function play(name) {
  if (!audioCtx || !soundBuffers[name]) return;
  const source = audioCtx.createBufferSource();
  source.buffer = soundBuffers[name];
  source.connect(audioCtx.destination);
  source.start();
}

// ---------- move handling ----------

function isHumanCode(code) {
  return (code === code.toUpperCase()) === (state.human_color === 'white');
}

// Apply the human move to the rendered pieces (captures, en passant,
// castling rook, promotion); the mover itself is placed by the caller.
function applyLocalMove(uci) {
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const el = pieceEls.get(from);
  const code = el.dataset.code;
  let capture = pieceEls.has(to);
  if (capture) fadeOut(pieceEls.get(to));
  if (code.toLowerCase() === 'p' && from[0] !== to[0] && !capture) {
    const epSquare = to[0] + from[1];
    fadeOut(pieceEls.get(epSquare));
    pieceEls.delete(epSquare);
    capture = true;
  }
  pieceEls.delete(from);
  pieceEls.set(to, el);
  if (code.toLowerCase() === 'k' && Math.abs(FILES.indexOf(from[0]) - FILES.indexOf(to[0])) === 2) {
    const rank = from[1];
    const [rookFrom, rookTo] = to[0] === 'g' ? ['h' + rank, 'f' + rank] : ['a' + rank, 'd' + rank];
    const rook = pieceEls.get(rookFrom);
    if (rook) {
      pieceEls.delete(rookFrom);
      pieceEls.set(rookTo, rook);
      raiseWhileMoving(rook);
      place(rook, rookTo);
    }
  }
  if (uci[4]) setPieceCode(el, state.human_color === 'white' ? uci[4].toUpperCase() : uci[4]);
  return capture;
}

async function commitMove(from, to, instant) {
  const promotions = state.legal
    .filter(uci => uci.slice(0, 4) === from + to && uci.length === 5)
    .map(uci => uci[4]);
  let uci = from + to;
  if (promotions.length) {
    const choice = await askPromotion(to, promotions);
    if (!choice) {
      clearSelection();
      reconcile(parseFen(state.fen), false);
      return;
    }
    uci += choice;
  }
  selected = null;
  const el = pieceEls.get(from);
  const capture = applyLocalMove(uci);
  if (instant) placeInstant(el, to);
  else { raiseWhileMoving(el); place(el, to); }
  updateHighlights(uci);
  await sendMove(uci, capture);
}

async function sendMove(uci, capture) {
  busy = true;
  play(capture ? 'capture' : 'move');
  setStatus('thinking');
  try {
    const next = await post('/move', { uci });
    let engineCapture = false;
    if (next.engine_move) {
      const target = next.engine_move.slice(2, 4);
      const mover = pieceEls.get(next.engine_move.slice(0, 2));
      engineCapture = pieceEls.has(target)
        || Boolean(mover && mover.dataset.code.toLowerCase() === 'p' && next.engine_move[0] !== target[0]);
    }
    state = next;
    reconcile(parseFen(next.fen), false);
    updateHighlights();
    setStatus();
    if (next.engine_move) play(engineCapture ? 'capture' : 'move');
    if (next.is_over) setTimeout(() => play('end'), 200);
  } catch (error) {
    setStatus('error', error.message);
    await loadState();
  } finally {
    busy = false;
  }
}

// ---------- promotion (popover anchored to the promotion square) ----------

function askPromotion(square, promotions) {
  return new Promise(resolve => {
    const backdrop = document.createElement('div');
    backdrop.className = 'promo-backdrop';
    const panel = document.createElement('div');
    panel.className = 'promo-panel';
    const [x, y] = coordsOf(square);
    panel.style.left = x * 12.5 + '%';
    if (y === 0) panel.style.top = '0';
    else panel.style.bottom = '0';
    const order = ['q', 'n', 'r', 'b'].filter(p => promotions.includes(p));
    const white = state.human_color === 'white';
    for (const piece of (y === 0 ? order : [...order].reverse())) {
      const button = document.createElement('button');
      button.className = 'promo-piece';
      button.style.backgroundImage = pieceUrl(white ? piece.toUpperCase() : piece);
      button.addEventListener('pointerdown', event => {
        event.stopPropagation();
        finish(piece);
      });
      panel.appendChild(button);
    }
    backdrop.addEventListener('pointerdown', () => finish(null));
    function finish(choice) {
      backdrop.remove();
      panel.remove();
      resolve(choice);
    }
    boardEl.appendChild(backdrop);
    boardEl.appendChild(panel);
  });
}

// ---------- pointer input (click-move and drag share one path) ----------

boardEl.addEventListener('pointerdown', event => {
  unlockAudio();
  if (busy || !state || state.is_over || state.turn !== state.human_color) return;
  const square = squareAtPoint(event.clientX, event.clientY);
  if (!square) return;
  if (selected && targetsFrom(selected).includes(square)) {
    event.preventDefault();
    commitMove(selected, square, false);
    return;
  }
  const el = pieceEls.get(square);
  if (!el || !isHumanCode(el.dataset.code)) {
    clearSelection();
    return;
  }
  event.preventDefault();
  const reclick = selected === square;
  selected = square;
  updateHighlights();
  drag = { from: square, el, started: false, reclick, startX: event.clientX, startY: event.clientY, hover: null };
  boardEl.setPointerCapture(event.pointerId);
});

boardEl.addEventListener('pointermove', event => {
  if (drag && drag.started === false) {
    if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 4) return;
    drag.started = true;
    drag.el.classList.add('dragging');
  }
  if (drag && drag.started) {
    const rect = boardEl.getBoundingClientRect();
    const size = rect.width / 8;
    drag.el.style.transform = 'translate('
      + (event.clientX - rect.left - size / 2) + 'px, '
      + (event.clientY - rect.top - size / 2) + 'px)';
    const over = squareAtPoint(event.clientX, event.clientY);
    if (over !== drag.hover) {
      if (drag.hover) squareEls.get(drag.hover).classList.remove('hover');
      drag.hover = over && targetsFrom(drag.from).includes(over) ? over : null;
      if (drag.hover) squareEls.get(drag.hover).classList.add('hover');
    }
    return;
  }
  // Grab cursor over pickable pieces when idle.
  if (busy || !state || state.is_over || state.turn !== state.human_color) {
    boardEl.style.cursor = 'default';
    return;
  }
  const square = squareAtPoint(event.clientX, event.clientY);
  const el = square && pieceEls.get(square);
  const canPick = (el && isHumanCode(el.dataset.code)) || (selected && targetsFrom(selected).includes(square));
  boardEl.style.cursor = canPick ? 'grab' : 'default';
});

boardEl.addEventListener('pointerup', event => {
  if (!drag) return;
  const { from, el, started, reclick, hover } = drag;
  drag = null;
  if (hover) squareEls.get(hover).classList.remove('hover');
  if (!started) {
    if (reclick) clearSelection();
    return;
  }
  el.classList.remove('dragging');
  const target = squareAtPoint(event.clientX, event.clientY);
  if (target && targetsFrom(from).includes(target)) {
    commitMove(from, target, true);
  } else {
    placeInstant(el, from) || place(el, from);
    clearSelection();
  }
});

boardEl.addEventListener('pointercancel', () => {
  if (!drag) return;
  const { from, el, started, hover } = drag;
  drag = null;
  if (hover) squareEls.get(hover).classList.remove('hover');
  if (started) {
    el.classList.remove('dragging');
    place(el, from);
  }
});

// ---------- status ----------

function setStatus(mode, message) {
  statusEl.classList.toggle('thinking', mode === 'thinking');
  if (mode === 'thinking') { statusEl.textContent = 'Engine is thinking'; return; }
  if (mode === 'error') { statusEl.textContent = message; return; }
  if (!state) { statusEl.textContent = ''; return; }
  if (state.is_over) {
    const result = state.result === '1-0' ? 'White wins'
      : state.result === '0-1' ? 'Black wins' : 'Draw';
    statusEl.textContent = 'Game over — ' + result;
    return;
  }
  const turn = state.turn === 'white' ? 'White' : 'Black';
  let text = turn + ' to move';
  if (state.check_square) text += ' — check';
  statusEl.textContent = text;
}

// ---------- server ----------

async function post(path, body) {
  const response = await fetch('/api' + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}

async function newGame() {
  if (busy) return;
  unlockAudio();
  selected = null;
  busy = true;
  try {
    const next = await post('/new', { human_color: colorEl.value });
    const wasFlipped = flipped;
    flipped = next.human_color === 'black';
    if (flipped !== wasFlipped) layoutSquares();
    if (next.engine_move) {
      // Snap to the start position, then let the engine's first move glide in.
      state = { ...next, last_move: null, check_square: null };
      reconcile(parseFen(START_FEN), flipped !== wasFlipped);
      updateHighlights();
      setStatus();
      setTimeout(() => {
        state = next;
        reconcile(parseFen(next.fen), false);
        updateHighlights();
        setStatus();
        play('move');
      }, 350);
    } else {
      state = next;
      reconcile(parseFen(next.fen), flipped !== wasFlipped);
      updateHighlights();
      setStatus();
    }
  } catch (error) {
    setStatus('error', error.message);
  } finally {
    busy = false;
  }
}

async function loadState() {
  const response = await fetch('/api/state');
  state = await response.json();
  const wasFlipped = flipped;
  flipped = state.human_color === 'black';
  if (flipped !== wasFlipped) layoutSquares();
  reconcile(parseFen(state.fen), true);
  updateHighlights();
  setStatus();
}

document.getElementById('new').addEventListener('click', newGame);
buildSquares();
loadState();
