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
  resignEl: document.getElementById('resign')
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

document.getElementById('new').addEventListener('click', () => game.newGame(colorEl.value));

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

game.load().then(state => { colorEl.value = state.human_color; });
