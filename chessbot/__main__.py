"""Entry point: ``python -m chessbot`` starts the UCI loop."""

from __future__ import annotations

from chessbot.uci import UciProtocol


def main() -> None:
    UciProtocol().run()


if __name__ == "__main__":
    main()
