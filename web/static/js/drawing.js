const SVG_NS = 'http://www.w3.org/2000/svg';

export const DRAW_COLORS = {
  orange: 'rgba(255, 170, 0, .8)',
  green: 'rgba(150, 190, 70, .8)',
  red: 'rgba(235, 97, 80, .8)',
  blue: 'rgba(72, 193, 249, .8)'
};

// Right-click annotations: arrows on an SVG overlay and colored square marks,
// applied through the board's square elements.
export class DrawingLayer {
  constructor(board) {
    this.board = board;
    this.arrows = new Map();   // 'e2e4' -> color name
    this.marks = new Map();    // square -> color name
    this.gesture = null;       // { from, to } while drawing
    this.svg = document.createElementNS(SVG_NS, 'svg');
    this.svg.setAttribute('viewBox', '0 0 8 8');
    this.svg.setAttribute('class', 'arrows');
    board.el.appendChild(this.svg);
  }

  get active() {
    return Boolean(this.gesture);
  }

  get isEmpty() {
    return this.arrows.size === 0 && this.marks.size === 0;
  }

  begin(square) {
    this.gesture = { from: square, to: square };
  }

  preview(square) {
    if (!this.gesture || !square || square === this.gesture.to) return;
    this.gesture.to = square;
    this.redraw();
  }

  finish(square, color) {
    const from = this.gesture.from;
    this.gesture = null;
    if (square === from) {
      if (this.marks.get(from) === color) this.marks.delete(from);
      else this.marks.set(from, color);
      this.#applyMarks();
    } else {
      const key = from + square;
      if (this.arrows.get(key) === color) this.arrows.delete(key);
      else this.arrows.set(key, color);
    }
    this.redraw();
  }

  cancel() {
    this.gesture = null;
    this.redraw();
  }

  clear() {
    if (this.isEmpty) return;
    this.arrows.clear();
    this.marks.clear();
    this.#applyMarks();
    this.redraw();
  }

  redraw() {
    this.svg.innerHTML = '';
    for (const [key, color] of this.arrows) {
      this.svg.appendChild(this.#arrowShapes(key.slice(0, 2), key.slice(2, 4), color, false));
    }
    if (this.gesture && this.gesture.from !== this.gesture.to) {
      this.svg.appendChild(this.#arrowShapes(this.gesture.from, this.gesture.to, 'orange', true));
    }
  }

  #applyMarks() {
    for (const [square, el] of this.board.squares) {
      const mark = this.marks.get(square);
      el.classList.toggle('marked', Boolean(mark));
      if (mark) el.style.setProperty('--mark', DRAW_COLORS[mark]);
    }
  }

  #arrowShapes(from, to, color, preview) {
    const [fx, fy] = this.board.centerOf(from);
    const [tx, ty] = this.board.centerOf(to);
    const dx = tx - fx;
    const dy = ty - fy;
    const tail = 0.35;
    const headLen = 0.42;
    const headWidth = 0.6;
    const knight = (Math.abs(dx) === 1 && Math.abs(dy) === 2) || (Math.abs(dx) === 2 && Math.abs(dy) === 1);
    let points;   // line vertices ending at the arrowhead base
    let ux;       // unit vector of the final leg, for the head
    let uy;
    if (knight) {
      // Chess.com bends knight arrows: long leg first, then the turn.
      const mx = Math.abs(dx) === 2 ? tx : fx;
      const my = Math.abs(dx) === 2 ? fy : ty;
      ux = Math.sign(tx - mx);
      uy = Math.sign(ty - my);
      const u1x = Math.sign(mx - fx);
      const u1y = Math.sign(my - fy);
      points = [[fx + u1x * tail, fy + u1y * tail], [mx, my], [tx - ux * headLen, ty - uy * headLen]];
    } else {
      const len = Math.hypot(dx, dy);
      ux = dx / len;
      uy = dy / len;
      points = [[fx + ux * tail, fy + uy * tail], [tx - ux * headLen, ty - uy * headLen]];
    }
    const group = document.createElementNS(SVG_NS, 'g');
    if (preview) group.setAttribute('opacity', '0.5');
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', 'M ' + points.map(p => p[0] + ' ' + p[1]).join(' L '));
    path.setAttribute('stroke', DRAW_COLORS[color]);
    path.setAttribute('stroke-width', '0.22');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('fill', 'none');
    const head = document.createElementNS(SVG_NS, 'polygon');
    const bx = tx - ux * headLen;
    const by = ty - uy * headLen;
    const px = -uy * headWidth / 2;
    const py = ux * headWidth / 2;
    head.setAttribute('points', tx + ',' + ty + ' ' + (bx + px) + ',' + (by + py) + ' ' + (bx - px) + ',' + (by - py));
    head.setAttribute('fill', DRAW_COLORS[color]);
    group.appendChild(path);
    group.appendChild(head);
    return group;
  }
}
