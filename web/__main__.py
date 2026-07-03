import argparse

import uvicorn

from web.app import create_app
from web.config import WebConfig


def main() -> None:
    defaults = WebConfig()
    parser = argparse.ArgumentParser(prog="web")
    parser.add_argument("--weights", default=defaults.weights)
    parser.add_argument("--movetime", type=int, default=defaults.movetime_ms)
    parser.add_argument("--host", default=defaults.host)
    parser.add_argument("--port", type=int, default=defaults.port)
    args = parser.parse_args()
    config = WebConfig(weights=args.weights, movetime_ms=args.movetime,
                       host=args.host, port=args.port)
    uvicorn.run(create_app(config), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
