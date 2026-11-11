"""``python -m zest_data_api`` — run the API with uvicorn."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "zest_data_api.main:app",
        host="0.0.0.0",
        port=8091,
        reload=False,
    )


if __name__ == "__main__":
    main()
