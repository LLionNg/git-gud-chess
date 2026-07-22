import { START_FEN, isWhitePiece, movesFrom, parseFen, premoveTargets } from './chess.js';
import { askPromotion } from './promotion.js';

// The server is stateless, so the current game lives here and in localStorage.
const STORAGE_KEY = 'chessbot.game';

// Takebacks available at any moment. The allowance refills after every move
// the player makes, so normal mode can step back one move but never chain
// undos deeper into the past.
const UNDO_ALLOWANCE = { practice: Infinity, normal: 1, hell: 0 };

// Orchestrates the game: server state, move flow, premoves, and keeping the
// board, player bars, and status line in sync. Input gestures live in
// PointerInput; rendering lives in Board.
export class Game {
  constructor({ board, drawings, sounds, bars, api, statusEl, dialog, resignEl,
                undoEl, redoEl, modeBadge, engineToggle }) {
    this.board = board;
    this.drawings = drawings;
    this.sounds = sounds;
    this.bars = bars;
    this.api = api;
    this.statusEl = statusEl;
    this.dialog = dialog;
    this.resignEl = resignEl;
    this.undoEl = undoEl;
    this.redoEl = redoEl;
    this.modeBadge = modeBadge;
    this.engineToggle = engineToggle;
    this.state = null;
    this.selected = null;
    this.busy = false;
    this.premove = null;   // { from, to }
    this.mode = 'normal';
    this.undosLeft = UNDO_ALLOWANCE.normal;
    this.redoStack = [];   // units of plies removed by undo, oldest first
    this.engineOff = false;   // practice-only: silence the engine
  }

  // Practice with the engine switched off: the player commands both armies.
  get freeBoard() {
    return this.mode === 'practice' && this.engineOff;
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
    if (!this.ready || this.busy) return false;
    return this.freeBoard || this.state.turn === this.state.human_color;
  }

  // On the free board every side-to-move piece is the player's.
  isHumanPiece(code) {
    const owner = this.freeBoard ? this.state.turn : this.state.human_color;
    return isWhitePiece(code) === (owner === 'white');
  }

  // Plies the human has played, derived from who moved first. Undo is only
  // meaningful while at least one of the player's own moves is on the board.
  #humanPlies() {
    if (!this.state) return 0;
    const startWhite = (this.state.start_fen || START_FEN).split(' ')[1] !== 'b';
    const humanFirst = startWhite === (this.state.human_color === 'white');
    const n = this.state.moves.length;
    return humanFirst ? Math.ceil(n / 2) : Math.floor(n / 2);
  }

  // Whether the ply at `index` was played by the human.
  #humanPly(index) {
    const startWhite = (this.state.start_fen || START_FEN).split(' ')[1] !== 'b';
    const humanFirst = startWhite === (this.state.human_color === 'white');
    return (index % 2 === 0) === humanFirst;
  }

  canUndo() {
    if (!this.ready || this.busy || this.mode === 'hell' || this.undosLeft <= 0) return false;
    if (this.state.termination === 'resignation') return false;
    return this.freeBoard ? this.state.moves.length > 0 : this.#humanPlies() > 0;
  }

  canRedo() {
    return this.ready && !this.busy && this.mode !== 'hell'
      && this.state.termination !== 'resignation' && this.redoStack.length > 0;
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

  #updateActions() {
    const hell = this.mode === 'hell';
    if (this.undoEl) {
      // Hell keeps the buttons clickable so the lock can taunt the player;
      // the click handler shakes instead of undoing.
      this.undoEl.classList.toggle('locked', hell);
      this.undoEl.disabled = !hell && !this.canUndo();
    }
    if (this.redoEl) {
      this.redoEl.classList.toggle('locked', hell);
      this.redoEl.disabled = !hell && !this.canRedo();
    }
    if (this.modeBadge) {
      this.modeBadge.hidden = !this.ready;
      this.modeBadge.textContent = this.mode;
      this.modeBadge.dataset.mode = this.mode;
    }
    if (this.engineToggle) {
      this.engineToggle.hidden = this.mode !== 'practice';
      this.engineToggle.disabled = !this.ready || this.busy;
      this.engineToggle.classList.toggle('off', this.engineOff);
      this.engineToggle.querySelector('.label').textContent =
        this.engineOff ? 'Engine: Off' : 'Engine: On';
    }
  }

  setStatus(mode, message) {
    if (this.resignEl) this.resignEl.disabled = !this.state || this.state.is_over || this.busy;
    this.#updateActions();
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
    if (this.freeBoard) text += ' (free board)';
    this.statusEl.textContent = text;
  }

  // ----- game lifecycle -----

  async load() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch (error) { /* corrupt save */ }
    if (!saved || !saved.fen) return this.newGame('white');
    // Saves from before histories were kept restart counting from here.
    if (!Array.isArray(saved.moves)) saved = { ...saved, start_fen: saved.fen, moves: [] };
    this.mode = UNDO_ALLOWANCE[saved.mode] !== undefined ? saved.mode : 'normal';
    // null marks the unlimited allowance; JSON cannot hold Infinity.
    this.undosLeft = saved.undos_left ?? UNDO_ALLOWANCE[this.mode];
    this.redoStack = Array.isArray(saved.redo) ? saved.redo : [];
    this.engineOff = this.mode === 'practice' && Boolean(saved.engine_off);
    this.state = saved;
    this.board.setOrientation(this.state.human_color === 'black');
    this.board.setPosition(parseFen(this.state.fen), true);
    this.drawings.redraw();
    this.refresh();
    this.setStatus();
    return this.state;
  }

  #store() {
    const save = {
      ...this.state,
      mode: this.mode,
      undos_left: Number.isFinite(this.undosLeft) ? this.undosLeft : null,
      redo: this.redoStack,
      engine_off: this.engineOff
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(save)); } catch (error) { /* storage full */ }
  }

  async newGame(humanColor, mode) {
    if (this.busy) return;
    if (UNDO_ALLOWANCE[mode] !== undefined) this.mode = mode;
    this.undosLeft = UNDO_ALLOWANCE[this.mode];
    this.redoStack = [];
    this.engineOff = false;
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

  // ----- engine toggle (practice free board) -----

  // Switching the engine off frees both armies for the player to set up a
  // scenario; switching it back on lets the engine answer immediately if
  // the position is its turn.
  async setEngineOff(off) {
    if (this.mode !== 'practice' || this.busy || off === this.engineOff) return;
    this.engineOff = off;
    this.selected = null;
    this.premove = null;
    this.#store();
    this.refresh();
    this.setStatus();
    if (off || !this.ready || this.over || this.state.turn === this.state.human_color) return;
    this.busy = true;
    this.setStatus('thinking');
    try {
      const next = await this.api.state(this.state, true);
      let capture = false;
      if (next.engine_move) {
        const target = next.engine_move.slice(2, 4);
        capture = Boolean(this.board.pieceAt(target));
      }
      this.busy = false;
      this.state = next;
      this.#store();
      this.board.setPosition(parseFen(next.fen), false);
      this.refresh();
      this.setStatus();
      if (next.engine_move) this.sounds.play(capture ? 'capture' : 'move');
      if (next.is_over) {
        setTimeout(() => {
          this.sounds.play('end');
          this.dialog.show({
            result: next.result,
            termination: next.termination,
            humanColor: next.human_color
          });
        }, 350);
      }
    } catch (error) {
      this.busy = false;
      this.setStatus('error', error.message);
    }
  }

  // ----- undo / redo -----

  // Takes back the player's last move together with the engine's reply, so
  // the board always lands back on the player's turn. On the free board
  // every ply is the player's, so undo steps a single ply at a time.
  async undo() {
    if (!this.canUndo()) return;
    const moves = this.state.moves.slice();
    const count = this.freeBoard || this.#humanPly(moves.length - 1) ? 1 : 2;
    const removed = moves.splice(moves.length - count, count);
    this.redoStack.push(removed);
    this.undosLeft -= 1;
    await this.#rebuild(moves, () => {
      this.redoStack.pop();
      this.undosLeft += 1;
    });
  }

  async redo() {
    if (!this.canRedo()) return;
    const unit = this.redoStack.pop();
    const moves = this.state.moves.concat(unit);
    await this.#rebuild(moves, () => this.redoStack.push(unit));
  }

  // Replaces the move list and asks the server to replay it; rollback undoes
  // the bookkeeping if the request fails.
  async #rebuild(moves, rollback) {
    this.busy = true;
    this.selected = null;
    this.premove = null;
    this.setStatus();
    try {
      const next = await this.api.state({ ...this.state, moves });
      this.busy = false;
      this.state = next;
      this.#store();
      this.board.setPosition(parseFen(next.fen), false);
      this.drawings.clear();
      this.refresh();
      this.setStatus();
      this.sounds.play('move');
    } catch (error) {
      this.busy = false;
      rollback();
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
      const next = await this.api.move(this.state, uci, !this.freeBoard);
      let engineCapture = false;
      if (next.engine_move) {
        const target = next.engine_move.slice(2, 4);
        const mover = this.board.pieceAt(next.engine_move.slice(0, 2));
        engineCapture = Boolean(this.board.pieceAt(target))
          || Boolean(mover && mover.toLowerCase() === 'p' && next.engine_move[0] !== target[0]);
      }
      this.state = next;
      this.busy = false;
      // Playing a fresh move abandons whatever the redo stack held and
      // refills the mode's takeback allowance (a redo does neither).
      this.redoStack = [];
      this.undosLeft = UNDO_ALLOWANCE[this.mode];
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
