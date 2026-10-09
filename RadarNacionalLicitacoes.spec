# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/classification/default_catalog.json','src/classification'), ('src/learning/course.json','src/learning'), ('src/learning/course.pdf','src/learning'), ('src/learning/course_pdf_manifest.json','src/learning')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt usa a ICU fornecida pelo Windows. Não incluir uma ICU homônima
# de Poppler/Conda/etc. encontrada no PATH: seus símbolos são incompatíveis.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() != 'icuuc.dll'
              and not Path(entry[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RadarNacionalLicitacoes',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RadarNacionalLicitacoes',
)
