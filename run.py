"""PyInstaller entry point.

The bundle starts here (as a top-level script, where relative imports do
not work), then hands over to `app.main` imported as a package - which is
also exactly what `python -m app.main` does when running from source.
"""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
