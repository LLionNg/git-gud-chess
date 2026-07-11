import { GameApi } from './api.js';
import { Board } from './board.js';
import { DrawingLayer } from './drawing.js';
import { Game } from './game.js';
import { PointerInput } from './input.js';
import { PlayerBars } from './players.js';
import { SoundBank } from './sound.js';

const board = new Board(document.getElementById('board'));
const drawings = new DrawingLayer(board);
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
  statusEl: document.getElementById('status')
});
new PointerInput({ board, game, drawings, sounds });

const colorEl = document.getElementById('color');

// Flip the view as soon as the side is picked; the game itself only
// changes color on New game.
colorEl.addEventListener('change', () => game.setFlipped(colorEl.value === 'black'));

document.getElementById('new').addEventListener('click', () => game.newGame(colorEl.value));

game.load().then(state => { colorEl.value = state.human_color; });
