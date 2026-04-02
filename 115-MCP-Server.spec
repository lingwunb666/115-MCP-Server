# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


datas = []
datas += collect_data_files("fastmcp")
datas += collect_data_files("p115client")
datas += copy_metadata("fastmcp")
datas += copy_metadata("p115client")
datas += copy_metadata("pydantic-settings")

hiddenimports = []
hiddenimports += collect_submodules("fastmcp")
hiddenimports += collect_submodules("p115client")
hiddenimports += collect_submodules("pydantic_settings")


a = Analysis(
    ["packaging/entrypoint.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="115-MCP-Server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
