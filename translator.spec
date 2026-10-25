# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: produces dist/LimitedTranslator/LimitedTranslator.exe"""
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (
    collect_submodules("epitran")
    + collect_submodules("argostranslate")
    + collect_submodules("app")
)
datas = (
    collect_data_files("epitran")          # pronunciation rule tables
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
    ["app/main.py"],
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LimitedTranslator",
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
    name="LimitedTranslator",
)
