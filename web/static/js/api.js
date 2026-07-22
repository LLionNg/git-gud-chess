// Thin client for the stateless backend: every request carries the position,
// so the server works the same under uvicorn and on serverless hosts.
export class GameApi {
  async newGame(humanColor, fen = null) {
    return this.#post('/new', { human_color: humanColor, fen });
  }

  // The move list travels with each request so the server can rebuild the
  // game with history — a bare FEN cannot show draws by repetition.
  // engineEnabled=false (practice free board) keeps the engine silent.
  async move(state, uci, engineEnabled = true) {
    return this.#post('/move', {
      start_fen: state.start_fen,
      moves: state.moves,
      uci,
      human_color: state.human_color,
      engine_enabled: engineEnabled
    });
  }

  // Rebuild a position after the move list is edited. think=true asks the
  // engine to answer from the position if it is its turn (used when the
  // free board switches the engine back on).
  async state(state, think = false) {
    return this.#post('/state', {
      start_fen: state.start_fen,
      moves: state.moves,
      human_color: state.human_color,
      think
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
