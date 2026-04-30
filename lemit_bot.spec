# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Lemit Bot
# Build with: pyinstaller lemit_bot.spec --clean --noconfirm

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "playwright",
        "playwright.sync_api",
        "playwright._impl._api_structures",
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.styles.fills",
        "openpyxl.styles.fonts",
        "openpyxl.utils",
        "openpyxl.utils.cell",
        "rich",
        "rich.console",
        "rich.progress",
        "rich.table",
        "rich.text",
        "rich.markup",
        "rich.panel",
        "excel_io",
        "excel_io.input_reader",
        "excel_io.output_writer",
        "excel_io.checkpoint",
        "queries",
        "queries.cpf_query",
        "queries.name_query",
        "queries.extractor",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pandas", "numpy", "matplotlib", "scipy", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lemit_bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX disabled: can trigger antivirus false positives
    console=True,       # Must be True for CAPTCHA prompts and file selection
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="lemit_bot",
)
