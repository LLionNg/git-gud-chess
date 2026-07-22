import { GameApi } from './api.js';
import { Board } from './board.js';
import { DrawingLayer } from './drawing.js';
import { Game } from './game.js';
import { GameOverDialog } from './gameover.js';
import { PointerInput } from './input.js';
import { PlayerBars } from './players.js';
import { SoundBank } from './sound.js';

const board = new Board(document.getElementById('board'));
const drawings = new DrawingLayer(board);
const dialog = new GameOverDialog(board);
const sounds = new SoundBank({
  move: '/sounds/Move.mp3',
  capture: '/sounds/Capture.mp3',
  end: '/sounds/GenericNotify.mp3'
});
const bars = new PlayerBars(
  document.getElementById('player-top'),
  document.getElementById('player-bottom')
);
const game = new Game({
  board,
  drawings,
  sounds,
  bars,
  api: new GameApi(),
  statusEl: document.getElementById('status'),
  dialog,
  resignEl: document.getElementById('resign'),
  undoEl: document.getElementById('undo'),
  redoEl: document.getElementById('redo'),
  modeBadge: document.getElementById('mode-badge'),
  engineToggle: document.getElementById('engine-toggle')
});
new PointerInput({ board, game, drawings, sounds });

const colorEl = document.getElementById('color');

dialog.onRematch = color => {
  colorEl.value = color;
  game.newGame(color);
};

// Flip the view as soon as the side is picked; the game itself only
// changes color on New game.
colorEl.addEventListener('change', () => game.setFlipped(colorEl.value === 'black'));

// ----- mode picker -----

const modeModal = document.getElementById('mode-modal');

document.getElementById('new').addEventListener('click', () => modeModal.classList.add('open'));
modeModal.addEventListener('click', event => {
  if (event.target === modeModal) modeModal.classList.remove('open');
});
addEventListener('keydown', event => {
  if (event.key === 'Escape') modeModal.classList.remove('open');
});
for (const card of modeModal.querySelectorAll('.mode-card')) {
  card.addEventListener('click', () => {
    modeModal.classList.remove('open');
    game.newGame(colorEl.value, card.dataset.mode);
  });
}

// ----- undo / redo -----

// In hell mode the buttons stay clickable but locked; clicking them only
// rattles the chains.
function shake(el) {
  el.classList.remove('shake');
  el.offsetWidth;  // restart the animation
  el.classList.add('shake');
}

for (const [el, action] of [
  [document.getElementById('undo'), () => game.undo()],
  [document.getElementById('redo'), () => game.redo()]
]) {
  el.addEventListener('click', () => {
    if (el.classList.contains('locked')) { shake(el); return; }
    action();
  });
}

// ----- engine toggle (practice free board) -----

document.getElementById('engine-toggle').addEventListener('click', () => {
  game.setEngineOff(!game.engineOff);
});

// ----- board colors -----

// Blue-white is the house default; green-white is one click away.
const THEME_KEY = 'chessbot.boardTheme';
if (localStorage.getItem(THEME_KEY) === 'green') document.body.classList.add('theme-green');
document.getElementById('swap-colors').addEventListener('click', () => {
  const green = document.body.classList.toggle('theme-green');
  try { localStorage.setItem(THEME_KEY, green ? 'green' : 'blue'); } catch (error) { /* storage full */ }
});

// Resign asks for confirmation chess.com-style: first click arms the button,
// a second click within a few seconds resigns.
const resignEl = document.getElementById('resign');
const resignLabel = resignEl.querySelector('span');
let resignTimer = null;

function disarmResign() {
  clearTimeout(resignTimer);
  resignTimer = null;
  resignEl.classList.remove('confirm');
  resignLabel.textContent = 'Resign';
}

resignEl.addEventListener('click', () => {
  if (!resignEl.classList.contains('confirm')) {
    resignEl.classList.add('confirm');
    resignLabel.textContent = 'Confirm?';
    resignTimer = setTimeout(disarmResign, 4000);
    return;
  }
  disarmResign();
  game.resign();
});

game.load().then(state => {
  colorEl.value = state.human_color;
  // Arriving from the landing page's mode picker starts a fresh game in
  // that mode; the query is stripped so a refresh does not restart it.
  const mode = new URLSearchParams(location.search).get('mode');
  if (['practice', 'normal', 'hell'].includes(mode)) {
    history.replaceState(null, '', location.pathname);
    game.newGame(colorEl.value, mode);
  }
});
