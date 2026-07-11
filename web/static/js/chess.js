// Pure chess helpers shared across the UI; no DOM access.

export const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

export function isWhitePiece(code) {
  return code === code.toUpperCase();
}

export function pieceUrl(code) {
  const color = isWhitePiece(code) ? 'w' : 'b';
  return 'url(/pieces/' + color + code.toUpperCase() + '.svg)';
}

export function parseFen(fen) {
  const pieces = {};
  fen.split(' ')[0].split('/').forEach((row, index) => {
    const rank = 8 - index;
    let file = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) file += Number(ch);
      else { pieces[FILES[file] + rank] = ch; file += 1; }
    }
  });
  return pieces;
}

export function movesFrom(legal, square) {
  return legal.filter(uci => uci.slice(0, 2) === square).map(uci => uci.slice(2, 4));
}

// Squares a piece could ever reach, ignoring occupancy — the premove rule:
// blockers may vanish before the move executes.
export function premoveTargets(code, from) {
  const f = FILES.indexOf(from[0]);
  const r = Number(from[1]) - 1;
  const type = code.toLowerCase();
  const white = isWhitePiece(code);
  const out = [];
  const add = (df, dr) => {
    const nf = f + df;
    const nr = r + dr;
    if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) out.push(FILES[nf] + (nr + 1));
  };
  const ray = (df, dr) => { for (let i = 1; i < 8; i += 1) add(df * i, dr * i); };
  if (type === 'p') {
    const dir = white ? 1 : -1;
    add(0, dir);
    if (r === (white ? 1 : 6)) add(0, 2 * dir);
    add(1, dir);
    add(-1, dir);
  } else if (type === 'n') {
    for (const [df, dr] of [[1, 2], [2, 1], [2, -1], [1, -2], [-1, -2], [-2, -1], [-2, 1], [-1, 2]]) add(df, dr);
  } else if (type === 'k') {
    for (let df = -1; df <= 1; df += 1) for (let dr = -1; dr <= 1; dr += 1) if (df || dr) add(df, dr);
    if (f === 4 && r === (white ? 0 : 7)) { add(2, 0); add(-2, 0); }
  } else {
    if (type === 'r' || type === 'q') { ray(1, 0); ray(-1, 0); ray(0, 1); ray(0, -1); }
    if (type === 'b' || type === 'q') { ray(1, 1); ray(1, -1); ray(-1, 1); ray(-1, -1); }
  }
  return out;
}
