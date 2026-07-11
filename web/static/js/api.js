// Thin client for the FastAPI backend.
export class GameApi {
  async newGame(humanColor, fen = null) {
    return this.#post('/new', { human_color: humanColor, fen });
  }

  async move(uci) {
    return this.#post('/move', { uci });
  }

  async state() {
    const response = await fetch('/api/state');
    return response.json();
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
