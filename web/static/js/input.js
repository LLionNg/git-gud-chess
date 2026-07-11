// Pointer gestures on the board: click-move, drag-move, premove selection,
// and right-click drawing. Decisions about what a move means belong to Game;
// this class only turns pointer events into calls on it.
export class PointerInput {
  constructor({ board, game, drawings, sounds }) {
    this.board = board;
    this.game = game;
    this.drawings = drawings;
    this.sounds = sounds;
    this.drag = null;   // { from, started, reclick, startX, startY }
    const el = board.el;
    el.addEventListener('contextmenu', event => event.preventDefault());
    el.addEventListener('pointerdown', event => this.#onDown(event));
    el.addEventListener('pointermove', event => this.#onMove(event));
    el.addEventListener('pointerup', event => this.#onUp(event));
    el.addEventListener('pointercancel', () => this.#onCancel());
  }

  #onDown(event) {
    this.sounds.unlock();
    if (!this.game.ready) return;
    const square = this.board.squareAt(event.clientX, event.clientY);
    if (event.button === 2) {
      if (this.drag) this.#abortDrag();
      if (this.game.premove) {
        this.game.cancelPremove();
        return;
      }
      if (!square) return;
      this.drawings.begin(square);
      this.board.el.setPointerCapture(event.pointerId);
      return;
    }
    if (event.button !== 0) return;
    this.drawings.clear();
    this.game.cancelPremove();
    if (this.game.over || !square) {
      this.game.deselect();
      return;
    }
    const selected = this.game.selected;
    if (selected && selected !== square && this.game.destsFor(selected).includes(square)) {
      event.preventDefault();
      this.game.tryMove(selected, square, false);
      return;
    }
    const code = this.board.pieceAt(square);
    if (!code || !this.game.isHumanPiece(code)) {
      this.game.deselect();
      return;
    }
    event.preventDefault();
    const reclick = selected === square;
    this.game.select(square);
    this.drag = { from: square, started: false, reclick, startX: event.clientX, startY: event.clientY };
    this.board.el.setPointerCapture(event.pointerId);
  }

  #onMove(event) {
    if (this.drawings.active) {
      this.drawings.preview(this.board.squareAt(event.clientX, event.clientY));
      return;
    }
    if (this.drag && (event.buttons & 2)) {
      // Right button pressed mid-drag cancels it, like chess.com.
      this.#abortDrag();
      return;
    }
    if (this.drag && !this.drag.started) {
      if (Math.hypot(event.clientX - this.drag.startX, event.clientY - this.drag.startY) < 4) return;
      this.drag.started = this.board.startDrag(this.drag.from);
      if (!this.drag.started) { this.drag = null; return; }
    }
    if (this.drag && this.drag.started) {
      this.board.dragTo(event.clientX, event.clientY);
      const over = this.board.squareAt(event.clientX, event.clientY);
      this.board.setHover(over && this.game.destsFor(this.drag.from).includes(over) ? over : null);
      return;
    }
    this.#updateCursor(event);
  }

  #onUp(event) {
    if (event.button === 2) {
      if (!this.drawings.active) return;
      const gesture = this.drawings.gesture;
      const target = this.board.squareAt(event.clientX, event.clientY) || gesture.to;
      this.drawings.finish(target, this.#drawColor(event, target === gesture.from));
      return;
    }
    if (!this.drag) return;
    const { from, started, reclick } = this.drag;
    this.drag = null;
    if (!started) {
      if (reclick) this.game.deselect();
      return;
    }
    this.board.endDrag(from);
    const target = this.board.squareAt(event.clientX, event.clientY);
    if (target && target !== from && this.game.destsFor(from).includes(target)) {
      this.game.tryMove(from, target, true);
    } else {
      this.game.deselect();
    }
  }

  #onCancel() {
    if (this.drawings.active) this.drawings.cancel();
    if (this.drag) this.#abortDrag();
  }

  #abortDrag() {
    if (this.drag.started) this.board.endDrag(this.drag.from);
    this.drag = null;
    this.game.deselect();
  }

  #drawColor(event, isMark) {
    if (event.shiftKey) return 'green';
    if (event.ctrlKey) return 'red';
    if (event.altKey) return 'blue';
    return isMark ? 'red' : 'orange';
  }

  #updateCursor(event) {
    if (!this.game.ready || this.game.over) {
      this.board.el.style.cursor = 'default';
      return;
    }
    const square = this.board.squareAt(event.clientX, event.clientY);
    const code = square && this.board.pieceAt(square);
    const selected = this.game.selected;
    const canPick = (code && this.game.isHumanPiece(code))
      || (selected && this.game.destsFor(selected).includes(square));
    this.board.el.style.cursor = canPick ? 'grab' : 'default';
  }
}
