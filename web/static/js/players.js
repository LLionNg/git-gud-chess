import { pieceUrl } from './chess.js';

const PIECE_VALUES = { p: 1, n: 3, b: 3, r: 5, q: 9 };
const INITIAL_COUNTS = { p: 8, n: 2, b: 2, r: 2, q: 1 };
const CAPTURE_ORDER = ['p', 'n', 'b', 'r', 'q'];

// The chess.com-style bars framing the board: avatar, name, and captured
// material with a running score for whichever side is ahead.
export class PlayerBars {
  constructor(topEl, bottomEl) {
    this.topEl = topEl;
    this.bottomEl = bottomEl;
  }

  update(pieceCodes, bottomColor, humanColor) {
    const counts = { w: { p: 0, n: 0, b: 0, r: 0, q: 0 }, b: { p: 0, n: 0, b: 0, r: 0, q: 0 } };
    for (const code of pieceCodes) {
      const type = code.toLowerCase();
      if (type !== 'k') counts[code === code.toUpperCase() ? 'w' : 'b'][type] += 1;
    }
    this.#render(this.bottomEl, bottomColor, counts, humanColor);
    this.#render(this.topEl, bottomColor === 'white' ? 'black' : 'white', counts, humanColor);
  }

  #render(bar, color, counts, humanColor) {
    // Placeholder identity; an OAuth profile would set the name and avatar here.
    bar.querySelector('.player-name').textContent = color === humanColor ? 'You' : 'Magnus.exe';
    const mine = color === 'white' ? 'w' : 'b';
    const theirs = mine === 'w' ? 'b' : 'w';
    const row = bar.querySelector('.captured');
    row.innerHTML = '';
    let gained = 0;
    let lost = 0;
    for (const type of CAPTURE_ORDER) {
      const taken = Math.max(0, INITIAL_COUNTS[type] - counts[theirs][type]);
      lost += Math.max(0, INITIAL_COUNTS[type] - counts[mine][type]) * PIECE_VALUES[type];
      gained += taken * PIECE_VALUES[type];
      if (!taken) continue;
      const group = document.createElement('div');
      group.className = 'cap-group';
      for (let i = 0; i < taken; i += 1) {
        const cap = document.createElement('span');
        cap.className = 'cap';
        cap.style.backgroundImage = pieceUrl(theirs === 'w' ? type.toUpperCase() : type);
        group.appendChild(cap);
      }
      row.appendChild(group);
    }
    if (gained > lost) {
      const score = document.createElement('span');
      score.className = 'cap-score';
      score.textContent = '+' + (gained - lost);
      row.appendChild(score);
    }
  }
}
