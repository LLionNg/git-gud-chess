import { FILES, isWhitePiece, pieceUrl } from './chess.js';

// Renders the board: highlight squares, coordinate labels, and a piece layer
// animated with CSS transforms. Owns orientation; knows nothing about rules
// beyond applying a move's side effects to the rendered pieces.
export class Board {
  constructor(el) {
    this.el = el;
    this.flipped = false;
    this.squares = new Map();   // square name -> highlight layer div
    this.pieces = new Map();    // square name -> piece div
    this.hovered = null;
    this.dragged = null;
    this.#build();
  }

  // ----- geometry -----

  coordsOf(square) {
    const f = FILES.indexOf(square[0]);
    const r = Number(square[1]) - 1;
    return [this.flipped ? 7 - f : f, this.flipped ? r : 7 - r];
  }

  centerOf(square) {
    const [x, y] = this.coordsOf(square);
    return [x + 0.5, y + 0.5];
  }

  squareAt(clientX, clientY) {
    const rect = this.el.getBoundingClientRect();
    const cx = Math.floor(((clientX - rect.left) / rect.width) * 8);
    const cy = Math.floor(((clientY - rect.top) / rect.height) * 8);
    if (cx < 0 || cx > 7 || cy < 0 || cy > 7) return null;
    const f = this.flipped ? 7 - cx : cx;
    const r = this.flipped ? cy : 7 - cy;
    return FILES[f] + (r + 1);
  }

  // ----- orientation -----

  setOrientation(flipped) {
    if (flipped === this.flipped) return false;
    this.flipped = flipped;
    this.#layout();
    return true;
  }

  #layout() {
    for (const [square, el] of this.squares) {
      this.#place(el, square);
      el.innerHTML = '';
      const [x, y] = this.coordsOf(square);
      const light = (FILES.indexOf(square[0]) + Number(square[1])) % 2 === 1;
      if (x === 0) el.appendChild(this.#coordLabel(square[1], 'rank', light));
      if (y === 7) el.appendChild(this.#coordLabel(square[0], 'file', light));
    }
    // Orientation changed, so every piece needs its transform recomputed.
    for (const [square, el] of this.pieces) this.#placeInstant(el, square);
  }

  // ----- squares and highlights -----

  squareElement(square) {
    return this.squares.get(square);
  }

  // Marks are managed by the drawing layer, hover by drag input; everything
  // else about square styling is set from this single view snapshot.
  setHighlights({ selected, last, check, premove, dests }) {
    for (const [square, el] of this.squares) {
      el.classList.toggle('selected', square === selected);
      el.classList.toggle('last', Boolean(last) && (square === last.slice(0, 2) || square === last.slice(2, 4)));
      el.classList.toggle('check', square === check);
      el.classList.toggle('premove', Boolean(premove) && (square === premove.from || square === premove.to));
      const isTarget = dests.includes(square);
      el.classList.toggle('dest', isTarget && !this.pieces.has(square));
      el.classList.toggle('capture', isTarget && this.pieces.has(square));
    }
  }

  setHover(square) {
    if (square === this.hovered) return;
    if (this.hovered) this.squares.get(this.hovered).classList.remove('hover');
    this.hovered = square;
    if (square) this.squares.get(square).classList.add('hover');
  }

  // ----- pieces -----

  pieceAt(square) {
    const el = this.pieces.get(square);
    return el ? el.dataset.code : null;
  }

  pieceCodes() {
    return [...this.pieces.values()].map(el => el.dataset.code);
  }

  // Diff the rendered pieces against a target position; moved pieces glide,
  // captures fade, new pieces (promotions) fade in.
  setPosition(target, instant) {
    const stays = new Map();
    const missing = [];
    for (const [square, code] of Object.entries(target)) {
      const el = this.pieces.get(square);
      if (el && el.dataset.code === code) stays.set(square, el);
      else missing.push([square, code]);
    }
    const pool = [];
    for (const [square, el] of this.pieces) {
      if (stays.get(square) !== el) pool.push({ square, el });
    }
    this.pieces.clear();
    for (const [square, el] of stays) this.pieces.set(square, el);
    for (const [square, code] of missing) {
      let best = -1;
      let bestDist = Infinity;
      pool.forEach((item, i) => {
        if (!item || item.el.dataset.code !== code) return;
        const [ax, ay] = this.coordsOf(item.square);
        const [bx, by] = this.coordsOf(square);
        const d = Math.hypot(ax - bx, ay - by);
        if (d < bestDist) { bestDist = d; best = i; }
      });
      if (best >= 0) {
        const el = pool[best].el;
        pool[best] = null;
        if (instant) this.#placeInstant(el, square);
        else { this.#raiseWhileMoving(el); this.#place(el, square); }
        this.pieces.set(square, el);
      } else {
        this.pieces.set(square, this.#createPiece(code, square, !instant));
      }
    }
    for (const item of pool) if (item) this.#fadeOut(item.el);
  }

  // Apply one move's side effects to the rendered pieces: captures,
  // en passant, the castling rook, and promotion. Returns whether it captured.
  applyMove(uci, instant) {
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    const el = this.pieces.get(from);
    if (!el) return false;
    const code = el.dataset.code;
    let capture = this.pieces.has(to);
    if (capture) this.#fadeOut(this.pieces.get(to));
    if (code.toLowerCase() === 'p' && from[0] !== to[0] && !capture) {
      const epSquare = to[0] + from[1];
      this.#fadeOut(this.pieces.get(epSquare));
      this.pieces.delete(epSquare);
      capture = true;
    }
    this.pieces.delete(from);
    this.pieces.set(to, el);
    if (code.toLowerCase() === 'k' && Math.abs(FILES.indexOf(from[0]) - FILES.indexOf(to[0])) === 2) {
      const rank = from[1];
      const [rookFrom, rookTo] = to[0] === 'g' ? ['h' + rank, 'f' + rank] : ['a' + rank, 'd' + rank];
      const rook = this.pieces.get(rookFrom);
      if (rook) {
        this.pieces.delete(rookFrom);
        this.pieces.set(rookTo, rook);
        this.#raiseWhileMoving(rook);
        this.#place(rook, rookTo);
      }
    }
    if (uci[4]) this.#setPieceCode(el, isWhitePiece(code) ? uci[4].toUpperCase() : uci[4]);
    if (instant) this.#placeInstant(el, to);
    else { this.#raiseWhileMoving(el); this.#place(el, to); }
    return capture;
  }

  // ----- drag visuals (gesture logic lives in PointerInput) -----

  startDrag(square) {
    const el = this.pieces.get(square);
    if (!el) return false;
    this.dragged = el;
    el.classList.add('dragging');
    return true;
  }

  dragTo(clientX, clientY) {
    if (!this.dragged) return;
    const rect = this.el.getBoundingClientRect();
    const size = rect.width / 8;
    this.dragged.style.transform = 'translate('
      + (clientX - rect.left - size / 2) + 'px, '
      + (clientY - rect.top - size / 2) + 'px)';
  }

  endDrag(snapSquare) {
    if (!this.dragged) return;
    this.dragged.classList.remove('dragging');
    this.#placeInstant(this.dragged, snapSquare);
    this.dragged = null;
    this.setHover(null);
  }

  // ----- internals -----

  #build() {
    for (const file of FILES) {
      for (let rank = 1; rank <= 8; rank += 1) {
        const square = file + rank;
        const el = document.createElement('div');
        el.className = 'square';
        el.dataset.square = square;
        this.el.appendChild(el);
        this.squares.set(square, el);
      }
    }
    this.#layout();
  }

  #coordLabel(text, kind, light) {
    const span = document.createElement('span');
    span.className = 'coord ' + kind + (light ? ' on-light' : ' on-dark');
    span.textContent = text;
    return span;
  }

  #place(el, square) {
    const [x, y] = this.coordsOf(square);
    el.style.transform = 'translate(' + x * 100 + '%, ' + y * 100 + '%)';
  }

  #placeInstant(el, square) {
    el.classList.add('no-anim');
    this.#place(el, square);
    el.offsetWidth;  // flush styles so the jump is not transitioned
    el.classList.remove('no-anim');
  }

  #createPiece(code, square, fadeIn) {
    const el = document.createElement('div');
    el.className = 'piece';
    el.dataset.code = code;
    el.style.backgroundImage = pieceUrl(code);
    this.#placeInstant(el, square);
    if (fadeIn) {
      el.classList.add('entering');
      requestAnimationFrame(() => el.classList.remove('entering'));
    }
    this.el.appendChild(el);
    return el;
  }

  #setPieceCode(el, code) {
    el.dataset.code = code;
    el.style.backgroundImage = pieceUrl(code);
  }

  #fadeOut(el) {
    if (!el) return;
    el.classList.add('fading');
    setTimeout(() => el.remove(), 200);
  }

  #raiseWhileMoving(el) {
    el.classList.add('moving');
    setTimeout(() => el.classList.remove('moving'), 220);
  }
}
