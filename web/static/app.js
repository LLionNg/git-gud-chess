const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const GLYPH = { p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚' };

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const colorEl = document.getElementById('color');
const promotionEl = document.getElementById('promotion');

let state = null;
let selected = null;
let pending = null;
let busy = false;
let audio = null;

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

function orderedSquares(flip) {
  const ranks = flip ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
  const files = flip ? [...FILES].reverse() : FILES;
  const squares = [];
  for (const rank of ranks) for (const file of files) squares.push(file + rank);
  return squares;
}

function isHumanPiece(piece) {
  if (!piece) return false;
  return (piece === piece.toUpperCase()) === (state.human_color === 'white');
}

function targetsFrom(square) {
  if (!square) return [];
  return state.legal.filter(uci => uci.slice(0, 2) === square).map(uci => uci.slice(2, 4));
}

function cellEl(square) {
  return boardEl.querySelector('[data-square="' + square + '"]');
}

function squareAt(x, y) {
  const element = document.elementFromPoint(x, y);
  const cell = element && element.closest('.cell');
  return cell ? cell.dataset.square : null;
}

function coord(text, kind) {
  const span = document.createElement('span');
  span.className = 'coord ' + kind;
  span.textContent = text;
  return span;
}

function render() {
  const flip = state.human_color === 'black';
  const pieces = parseFen(state.fen);
  const last = state.last_move;
  const targets = targetsFrom(selected);
  boardEl.innerHTML = '';
  orderedSquares(flip).forEach((square, index) => {
    const file = FILES.indexOf(square[0]);
    const rank = Number(square[1]);
    const cell = document.createElement('div');
    cell.className = 'cell ' + ((file + rank) % 2 === 0 ? 'light' : 'dark');
    cell.dataset.square = square;
    if (square === selected) cell.classList.add('selected');
    if (last && (square === last.slice(0, 2) || square === last.slice(2, 4))) cell.classList.add('last');
    if (square === state.check_square) cell.classList.add('check');
    if (targets.includes(square)) cell.classList.add('target');
    const piece = pieces[square];
    if (piece) {
      const span = document.createElement('span');
      span.className = 'piece ' + (piece === piece.toUpperCase() ? 'white' : 'black');
      span.textContent = GLYPH[piece.toLowerCase()];
      cell.appendChild(span);
    }
    if (index % 8 === 0) cell.appendChild(coord(String(rank), 'rank'));
    if (index >= 56) cell.appendChild(coord(square[0], 'file'));
    cell.addEventListener('pointerdown', event => onPointerDown(event, square));
    boardEl.appendChild(cell);
  });
  statusEl.textContent = statusText();
}

function statusText() {
  if (state.is_over) {
    const result = state.result === '1-0' ? 'White wins'
      : state.result === '0-1' ? 'Black wins' : 'Draw';
    return 'Game over - ' + result;
  }
  const turn = state.turn === 'white' ? 'White' : 'Black';
  let text = turn + ' to move';
  if (state.check_square) text += ' - check';
  if (state.engine_move) text += ' - engine played ' + state.engine_move;
  return text;
}

function onPointerDown(event, square) {
  if (busy || !state || state.is_over || state.turn !== state.human_color) return;
  if (selected && targetsFrom(selected).includes(square)) {
    event.preventDefault();
    commitMove(selected, square);
    return;
  }
  const piece = parseFen(state.fen)[square];
  if (!isHumanPiece(piece)) {
    if (selected) { selected = null; render(); }
    return;
  }
  event.preventDefault();
  selected = square;
  render();
  pending = { from: square, piece, startX: event.clientX, startY: event.clientY, el: null, size: 0 };
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
}

function onPointerMove(event) {
  if (!pending) return;
  if (!pending.el) {
    if (Math.abs(event.clientX - pending.startX) < 5 && Math.abs(event.clientY - pending.startY) < 5) return;
    startFloat();
  }
  pending.el.style.left = (event.clientX - pending.size / 2) + 'px';
  pending.el.style.top = (event.clientY - pending.size / 2) + 'px';
  const square = squareAt(event.clientX, event.clientY);
  boardEl.querySelectorAll('.cell.hover').forEach(cell => cell.classList.remove('hover'));
  if (square && targetsFrom(pending.from).includes(square)) {
    const cell = cellEl(square);
    if (cell) cell.classList.add('hover');
  }
}

function startFloat() {
  const cell = cellEl(pending.from);
  const size = cell.getBoundingClientRect().width;
  const float = document.createElement('div');
  float.className = 'floating piece ' + (pending.piece === pending.piece.toUpperCase() ? 'white' : 'black');
  float.textContent = GLYPH[pending.piece.toLowerCase()];
  float.style.width = size + 'px';
  float.style.height = size + 'px';
  float.style.fontSize = Math.round(size * 0.72) + 'px';
  document.body.appendChild(float);
  const piece = cell.querySelector('.piece');
  if (piece) piece.style.visibility = 'hidden';
  pending.el = float;
  pending.size = size;
}

function onPointerUp(event) {
  if (!pending) return;
  const from = pending.from;
  const dragging = Boolean(pending.el);
  const target = squareAt(event.clientX, event.clientY);
  cleanupPending();
  if (!dragging) return;
  if (target && targetsFrom(from).includes(target)) commitMove(from, target);
  else { selected = null; render(); }
}

function cleanupPending() {
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
  if (pending && pending.el) pending.el.remove();
  boardEl.querySelectorAll('.cell.hover').forEach(cell => cell.classList.remove('hover'));
  pending = null;
}

function commitMove(from, to) {
  const promotions = state.legal
    .filter(uci => uci.slice(0, 4) === from + to && uci.length === 5)
    .map(uci => uci[4]);
  if (promotions.length) askPromotion(from, to, promotions);
  else sendMove(from + to);
}

function askPromotion(from, to, promotions) {
  const color = state.human_color;
  promotionEl.innerHTML = '';
  for (const piece of promotions) {
    const button = document.createElement('button');
    button.className = color;
    button.textContent = GLYPH[piece];
    button.addEventListener('click', () => {
      promotionEl.classList.add('hidden');
      sendMove(from + to + piece);
    });
    promotionEl.appendChild(button);
  }
  promotionEl.classList.remove('hidden');
}

function optimisticMove(from, to) {
  const fromCell = cellEl(from);
  const toCell = cellEl(to);
  if (!fromCell || !toCell) return;
  const piece = fromCell.querySelector('.piece');
  if (!piece) return;
  boardEl.querySelectorAll('.selected, .target, .last').forEach(cell =>
    cell.classList.remove('selected', 'target', 'last'));
  const captured = toCell.querySelector('.piece');
  if (captured) captured.remove();
  piece.style.visibility = 'visible';
  toCell.appendChild(piece);
  fromCell.classList.add('last');
  toCell.classList.add('last');
}

async function sendMove(uci) {
  selected = null;
  busy = true;
  optimisticMove(uci.slice(0, 2), uci.slice(2, 4));
  playMoveSound();
  try {
    const next = await post('/move', { uci });
    setState(next);
    if (next.engine_move) playMoveSound();
  } catch (error) {
    statusEl.textContent = error.message;
    await loadState();
  } finally {
    busy = false;
  }
}

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
  selected = null;
  const next = await post('/new', { human_color: colorEl.value });
  setState(next);
  if (next.engine_move) playMoveSound();
}

async function loadState() {
  const response = await fetch('/api/state');
  setState(await response.json());
}

function setState(next) {
  state = next;
  render();
}

function playMoveSound() {
  if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
  if (audio.state === 'suspended') audio.resume();
  const ctx = audio;
  const now = ctx.currentTime;
  const detune = 0.9 + Math.random() * 0.2;

  const noiseDur = 0.05;
  const buffer = ctx.createBuffer(1, Math.floor(ctx.sampleRate * noiseDur), ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
  const noise = ctx.createBufferSource();
  noise.buffer = buffer;
  const filter = ctx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.value = 2200 * detune;
  filter.Q.value = 0.7;
  const noiseGain = ctx.createGain();
  noiseGain.gain.setValueAtTime(0.5, now);
  noiseGain.gain.exponentialRampToValueAtTime(0.001, now + noiseDur);
  noise.connect(filter).connect(noiseGain).connect(ctx.destination);

  const osc = ctx.createOscillator();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(210 * detune, now);
  osc.frequency.exponentialRampToValueAtTime(120 * detune, now + 0.08);
  const oscGain = ctx.createGain();
  oscGain.gain.setValueAtTime(0.35, now);
  oscGain.gain.exponentialRampToValueAtTime(0.001, now + 0.11);
  osc.connect(oscGain).connect(ctx.destination);

  noise.start(now);
  noise.stop(now + noiseDur);
  osc.start(now);
  osc.stop(now + 0.12);
}

document.getElementById('new').addEventListener('click', newGame);
loadState();
