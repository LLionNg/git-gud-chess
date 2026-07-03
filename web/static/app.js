const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const GLYPH = { p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚' };

const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const colorEl = document.getElementById('color');
const promotionEl = document.getElementById('promotion');

let state = null;
let selected = null;

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
  const isWhite = piece === piece.toUpperCase();
  return isWhite === (state.human_color === 'white');
}

function targetsFrom(square) {
  if (!square) return [];
  return state.legal.filter(uci => uci.slice(0, 2) === square).map(uci => uci.slice(2, 4));
}

function render() {
  const flip = state.human_color === 'black';
  const pieces = parseFen(state.fen);
  const last = state.last_move;
  const targets = targetsFrom(selected);
  boardEl.innerHTML = '';
  for (const square of orderedSquares(flip)) {
    const file = FILES.indexOf(square[0]);
    const rank = Number(square[1]);
    const cell = document.createElement('div');
    cell.className = 'cell ' + ((file + rank) % 2 === 0 ? 'light' : 'dark');
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
    cell.addEventListener('click', () => onClick(square));
    boardEl.appendChild(cell);
  }
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

function onClick(square) {
  if (!state || state.is_over || state.turn !== state.human_color) return;
  if (selected && targetsFrom(selected).includes(square)) {
    playMove(selected, square);
    return;
  }
  selected = isHumanPiece(parseFen(state.fen)[square]) ? square : null;
  render();
}

function playMove(from, to) {
  const promotions = state.legal
    .filter(uci => uci.slice(0, 4) === from + to && uci.length === 5)
    .map(uci => uci[4]);
  if (promotions.length) askPromotion(from, to, promotions);
  else sendMove(from + to);
}

function askPromotion(from, to, promotions) {
  const color = state.human_color === 'white' ? 'white' : 'black';
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

async function sendMove(uci) {
  selected = null;
  try {
    setState(await post('/move', { uci }));
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

async function newGame() {
  selected = null;
  setState(await post('/new', { human_color: colorEl.value }));
}

async function loadState() {
  const response = await fetch('/api/state');
  setState(await response.json());
}

function setState(next) {
  state = next;
  render();
}

document.getElementById('new').addEventListener('click', newGame);
loadState();
