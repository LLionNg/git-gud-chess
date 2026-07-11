import { START_FEN, isWhitePiece, movesFrom, parseFen, premoveTargets } from './chess.js';
import { askPromotion } from './promotion.js';

// The server is stateless, so the current game lives here and in localStorage.
const STORAGE_KEY = 'chessbot.game';

// Orchestrates the game: server state, move flow, premoves, and keeping the
// board, player bars, and status line in sync. Input gestures live in
// PointerInput; rendering lives in Board.
export class Game {
  constructor({ board, drawings, sounds, bars, api, statusEl, dialog, resignEl }) {
    this.board = board;
    this.drawings = drawings;
    this.sounds = sounds;
    this.bars = bars;
    this.api = api;
    this.statusEl = statusEl;
    this.dialog = dialog;
    this.resignEl = resignEl;
    this.state = null;
    this.selected = null;
    this.busy = false;
    this.premove = null;   // { from, to }
  }

  // ----- queries -----

  get ready() {
    return Boolean(this.state);
  }

  get over() {
    return Boolean(this.state) && this.state.is_over;
  }

  get humanColor() {
    return this.state.human_color;
  }

  myTurn() {
    return this.ready && !this.busy && this.state.turn === this.state.human_color;
  }

  isHumanPiece(code) {
    return isWhitePiece(code) === (this.state.human_color === 'white');
  }

  // Legal targets on the player's turn; movement-pattern targets otherwise,
  // so a premove can be picked while the engine thinks.
  destsFor(square) {
    if (!square || !this.ready) return [];
    if (this.myTurn()) return movesFrom(this.state.legal, square);
    const code = this.board.pieceAt(square);
    return code && this.isHumanPiece(code) ? premoveTargets(code, square) : [];
  }

  // ----- selection -----

  select(square) {
    this.selected = square;
    this.refresh();
  }

  deselect() {
    this.selected = null;
    this.refresh();
  }

  // ----- view -----

  setFlipped(flipped) {
    if (!this.board.setOrientation(flipped)) return;
    this.drawings.redraw();
    this.refresh();
  }

  refresh(lastOverride) {
    this.board.setHighlights({
      selected: this.selected,
      last: lastOverride || (this.state && this.state.last_move),
      check: this.state && this.state.check_square,
      premove: this.premove,
      dests: this.destsFor(this.selected)
    });
    if (this.state) {
      this.bars.update(this.board.pieceCodes(),
        this.board.flipped ? 'black' : 'white', this.state.human_color);
    }
  }

  setStatus(mode, message) {
    if (this.resignEl) this.resignEl.disabled = !this.state || this.state.is_over || this.busy;
    this.statusEl.classList.toggle('thinking', mode === 'thinking');
    if (mode === 'thinking') { this.statusEl.textContent = 'Engine is thinking'; return; }
    if (mode === 'error') { this.statusEl.textContent = message; return; }
    if (!this.state) { this.statusEl.textContent = ''; return; }
    if (this.state.is_over) {
      const result = this.state.result === '1-0' ? 'White wins'
        : this.state.result === '0-1' ? 'Black wins' : 'Draw';
      this.statusEl.textContent = 'Game over — ' + result;
      return;
    }
    const turn = this.state.turn === 'white' ? 'White' : 'Black';
    let text = turn + ' to move';
    if (this.state.check_square) text += ' — check';
    this.statusEl.textContent = text;
  }

  // ----- game lifecycle -----

  async load() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch (error) { /* corrupt save */ }
    if (!saved || !saved.fen) return this.newGame('white');
    this.state = saved;
    this.board.setOrientation(this.state.human_color === 'black');
    this.board.setPosition(parseFen(this.state.fen), true);
    this.drawings.redraw();
    this.refresh();
    this.setStatus();
    return this.state;
  }

  #store() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state)); } catch (error) { /* storage full */ }
  }

  async newGame(humanColor) {
    if (this.busy) return;
    this.sounds.unlock();
    this.selected = null;
    this.premove = null;
    this.drawings.clear();
    this.busy = true;
    try {
      const next = await this.api.newGame(humanColor);
      this.busy = false;
      const reoriented = this.board.setOrientation(next.human_color === 'black');
      if (reoriented) this.drawings.redraw();
      if (next.engine_move) {
        // Snap to the start position, then let the engine's first move glide in.
        this.state = { ...next, last_move: null, check_square: null };
        this.board.setPosition(parseFen(START_FEN), reoriented);
        this.refresh();
        this.setStatus();
        setTimeout(() => {
          this.state = next;
          this.#store();
          this.board.setPosition(parseFen(next.fen), false);
          this.refresh();
          this.setStatus();
          this.sounds.play('move');
        }, 350);
      } else {
        this.state = next;
        this.#store();
        this.board.setPosition(parseFen(next.fen), reoriented);
        this.refresh();
        this.setStatus();
      }
      return next;
    } catch (error) {
      this.busy = false;
      this.setStatus('error', error.message);
      return this.state;
    }
  }

  // ----- move flow -----

  // Entry point for input: commits on the player's turn, queues otherwise.
  tryMove(from, to, instant) {
    if (this.myTurn()) this.#commitMove(from, to, instant);
    else this.#setPremove(from, to);
  }

  cancelPremove() {
    if (!this.premove) return;
    this.premove = null;
    this.refresh();
  }

  async resign() {
    if (!this.ready || this.over || this.busy) return;
    try {
      const next = await this.api.resign(this.state);
      this.state = next;
      this.selected = null;
      this.premove = null;
      this.#store();
      this.refresh();
      this.setStatus();
      this.sounds.play('end');
      this.dialog.show({
        result: next.result,
        termination: next.termination,
        humanColor: next.human_color
      });
    } catch (error) {
      this.setStatus('error', error.message);
    }
  }

  async #commitMove(from, to, instant) {
    const promotions = this.state.legal
      .filter(uci => uci.slice(0, 4) === from + to && uci.length === 5)
      .map(uci => uci[4]);
    let uci = from + to;
    if (promotions.length) {
      const choice = await askPromotion(this.board, to, promotions, this.state.human_color === 'white');
      if (!choice) {
        this.selected = null;
        this.board.setPosition(parseFen(this.state.fen), false);
        this.refresh();
        return;
      }
      uci += choice;
    }
    await this.#playMove(uci, instant);
  }

  async #playMove(uci, instant) {
    this.selected = null;
    const capture = this.board.applyMove(uci, instant);
    this.refresh(uci);
    await this.#send(uci, capture);
  }

  async #send(uci, capture) {
    this.busy = true;
    this.sounds.play(capture ? 'capture' : 'move');
    this.setStatus('thinking');
    try {
      // this.state still holds the pre-move position the server expects.
      const next = await this.api.move(this.state, uci);
      let engineCapture = false;
      if (next.engine_move) {
        const target = next.engine_move.slice(2, 4);
        const mover = this.board.pieceAt(next.engine_move.slice(0, 2));
        engineCapture = Boolean(this.board.pieceAt(target))
          || Boolean(mover && mover.toLowerCase() === 'p' && next.engine_move[0] !== target[0]);
      }
      this.state = next;
      this.busy = false;
      this.#store();
      this.board.setPosition(parseFen(next.fen), false);
      this.refresh();
      this.setStatus();
      if (next.engine_move) this.sounds.play(engineCapture ? 'capture' : 'move');
      if (next.is_over) {
        // Let the final move settle before the banner and sound land.
        setTimeout(() => {
          this.sounds.play('end');
          this.dialog.show({
            result: next.result,
            termination: next.termination,
            humanColor: next.human_color
          });
        }, 350);
      }
      this.#executePremove();
    } catch (error) {
      // The server never applied the move; roll the board back to our state.
      this.busy = false;
      this.premove = null;
      this.selected = null;
      this.board.setPosition(parseFen(this.state.fen), true);
      this.refresh();
      this.setStatus('error', error.message);
    }
  }

  #setPremove(from, to) {
    this.premove = { from, to };
    this.selected = null;
    this.refresh();
  }

  #executePremove() {
    if (!this.premove) return;
    if (!this.state || this.state.is_over || this.state.turn !== this.state.human_color) {
      if (this.over) { this.premove = null; this.refresh(); }
      return;
    }
    const { from, to } = this.premove;
    this.premove = null;
    let uci = from + to;
    // Premoves promote to a queen automatically, like chess.com's default.
    if (!this.state.legal.includes(uci)) {
      if (this.state.legal.includes(uci + 'q')) uci += 'q';
      else { this.refresh(); return; }
    }
    setTimeout(() => {
      if (!this.myTurn() || !this.state.legal.includes(uci)) return;
      this.#playMove(uci, true);
    }, 80);
  }
}
