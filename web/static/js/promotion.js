import { pieceUrl } from './chess.js';

// Chess.com-style popover anchored to the promotion square. Resolves with the
// chosen piece letter, or null when dismissed by clicking the backdrop.
export function askPromotion(board, square, promotions, white) {
  return new Promise(resolve => {
    const backdrop = document.createElement('div');
    backdrop.className = 'promo-backdrop';
    const panel = document.createElement('div');
    panel.className = 'promo-panel';
    const [x, y] = board.coordsOf(square);
    panel.style.left = x * 12.5 + '%';
    if (y === 0) panel.style.top = '0';
    else panel.style.bottom = '0';
    const order = ['q', 'n', 'r', 'b'].filter(p => promotions.includes(p));
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
    board.el.appendChild(backdrop);
    board.el.appendChild(panel);
  });
}
