# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: produces dist/LanguageTranslator[/LanguageTranslator(.exe)]

Set LT_ONEFILE=1 in the environment to build a single self-extracting
executable instead of a folder build. Command-line --onefile cannot be
used here: PyInstaller rejects makespec options whenever a .spec file
is given, so the build scripts set this variable instead.
"""
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ONEFILE = os.environ.get("LT_ONEFILE") == "1"

hidden = (
    collect_submodules("epitran")
    + collect_submodules("argostranslate")
    + collect_submodules("app")
)
datas = (
    collect_data_files("epitran")          # pronunciation rule tables
    + collect_data_files("jamo")           # jamo decomposes Hangul to letters
                                           # (epitran -> simple.py reads these
                                           # at import time via __file__)
    + collect_data_files("panphon")        # phoneme feature tables (epitran
                                           # needs panphon.FeatureTable; without
                                           # these the frozen panel stays empty)
    + collect_data_files("wordfreq")       # word frequency lists (correction)
    + collect_data_files("langcodes")      # language tag data for wordfreq
    + collect_data_files("spellchecker")   # typo dictionary
)

excludes = [
    # heavy Qt add-ons we never import
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQuick",
    "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtCharts",
    "PySide6.QtWebChannel", "PySide6.QtDesigner",
]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=excludes,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

if ONEFILE:
    # single self-extracting executable: binaries and data go inline,
    # no COLLECT step (output: dist/LanguageTranslator[.exe])
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="LanguageTranslator",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="LanguageTranslator",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name="LanguageTranslator",
    )
