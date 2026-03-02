# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

binaries = []
datas = []
hiddenimports_extra = [
    # Licenciamento
    'license',
    'wmi', 'win32api', 'win32con', 'win32security', 'pywintypes',
    'cryptography', 'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.hkdf',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
    'httpx', 'httpcore', 'anyio', 'anyio.streams.memory',
    'anyio.streams.tls', 'anyio._backends._asyncio',
    'certifi', 'idna', 'h11',
]
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports_extra += tmp_ret[2]
tmp_ret = collect_all('httpx')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports_extra += tmp_ret[2]

a = Analysis(
    ['C:\\Users\\palme\\ccd\\ccd_telegrammilhas\\monitor.py'],
    pathex=['C:\\Users\\palme\\ccd\\ccd_telegrammilhas'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports_extra,
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
    [],
    exclude_binaries=True,
    name='monitor_bg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\palme\\ccd\\ccd_telegrammilhas\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='monitor_bg',
)
