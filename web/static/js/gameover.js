import { pieceUrl } from './chess.js';

const REASONS = {
  checkmate: 'by checkmate',
  stalemate: 'by stalemate',
  insufficient_material: 'by insufficient material',
  seventyfive_moves: 'by the 75-move rule',
  fivefold_repetition: 'by repetition',
  fifty_moves: 'by the 50-move rule',
  threefold_repetition: 'by repetition',
  resignation: 'by resignation'
};

// Chess.com-style end-of-game modal over the board: result banner, side
// selection, and a rematch button. The rematch action is injected by the
// composition root via `onRematch(color)`.
export class GameOverDialog {
  constructor(board) {
    this.board = board;
    this.el = null;
    this.onRematch = null;
  }

  show({ result, termination, humanColor }) {
    this.close();
    const draw = result === '1/2-1/2';
    const won = !draw && (result === '1-0') === (humanColor === 'white');
    let picked = humanColor;

    const backdrop = document.createElement('div');
    backdrop.className = 'gameover-backdrop';
    backdrop.addEventListener('pointerdown', event => {
      event.stopPropagation();
      if (event.target === backdrop) this.close();
    });

    const card = document.createElement('div');
    card.className = 'gameover';

    const close = document.createElement('button');
    close.className = 'gameover-close';
    close.textContent = '×';
    close.addEventListener('click', () => this.close());

    const head = document.createElement('div');
    head.className = 'gameover-head ' + (draw ? 'draw' : won ? 'win' : 'loss');
    const title = document.createElement('div');
    title.className = 'gameover-title';
    title.textContent = draw ? 'Draw' : won ? 'You won!' : 'You lost';
    const sub = document.createElement('div');
    sub.className = 'gameover-sub';
    sub.textContent = REASONS[termination] || 'game over';
    head.appendChild(title);
    head.appendChild(sub);

    const body = document.createElement('div');
    body.className = 'gameover-body';
    const label = document.createElement('div');
    label.className = 'side-label';
    label.textContent = 'Play as';
    const sides = document.createElement('div');
    sides.className = 'side-select';
    for (const color of ['white', 'black']) {
      const button = document.createElement('button');
      button.className = 'side-btn' + (color === picked ? ' picked' : '');
      button.style.backgroundImage = pieceUrl(color === 'white' ? 'K' : 'k');
      button.title = color === 'white' ? 'White' : 'Black';
      button.addEventListener('click', () => {
        picked = color;
        sides.querySelectorAll('.side-btn').forEach(b => b.classList.remove('picked'));
        button.classList.add('picked');
      });
      sides.appendChild(button);
    }
    const rematch = document.createElement('button');
    rematch.className = 'rematch';
    rematch.textContent = 'Rematch';
    rematch.addEventListener('click', () => {
      this.close();
      if (this.onRematch) this.onRematch(picked);
    });
    body.appendChild(label);
    body.appendChild(sides);
    body.appendChild(rematch);

    card.appendChild(close);
    card.appendChild(head);
    card.appendChild(body);
    backdrop.appendChild(card);
    this.board.el.appendChild(backdrop);
    this.el = backdrop;
  }

  close() {
    if (!this.el) return;
    this.el.remove();
    this.el = null;
  }
}
