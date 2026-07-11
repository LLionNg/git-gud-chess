// Thin client for the stateless backend: every request carries the position,
// so the server works the same under uvicorn and on serverless hosts.
export class GameApi {
  async newGame(humanColor, fen = null) {
    return this.#post('/new', { human_color: humanColor, fen });
  }

  async move(state, uci) {
    return this.#post('/move', { fen: state.fen, uci, human_color: state.human_color });
  }

  async resign(state) {
    return this.#post('/resign', { fen: state.fen, human_color: state.human_color });
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
