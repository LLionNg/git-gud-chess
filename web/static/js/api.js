// Thin client for the stateless backend: every request carries the position,
// so the server works the same under uvicorn and on serverless hosts.
export class GameApi {
  async newGame(humanColor, fen = null) {
    return this.#post('/new', { human_color: humanColor, fen });
  }

  // The move list travels with each request so the server can rebuild the
  // game with history — a bare FEN cannot show draws by repetition.
  async move(state, uci) {
    return this.#post('/move', {
      start_fen: state.start_fen,
      moves: state.moves,
      uci,
      human_color: state.human_color
    });
  }

  // Rebuild a position after undo/redo edits the move list; the engine
  // is never asked to reply, so the client lands on the player's turn.
  async state(state) {
    return this.#post('/state', {
      start_fen: state.start_fen,
      moves: state.moves,
      human_color: state.human_color
    });
  }

  async resign(state) {
    return this.#post('/resign', {
      start_fen: state.start_fen,
      moves: state.moves,
      human_color: state.human_color
    });
  }

  async #post(path, body) {
    const response = await fetch('/api' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || response.statusText);
    return data;
  }
}
