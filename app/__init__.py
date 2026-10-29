"""Language Translator application package.

Importing this package installs the UTF-8 default-encoding fix (see
``compat.py``) before any app or third-party module reads data files.
``app/__init__.py`` is the one choke point that runs first in source
runs (``python -m app.main``), frozen builds (``run.py`` imports
``app.main`` as a package), and the test suite alike.
"""
from .compat import install_utf8_defaults

install_utf8_defaults()
