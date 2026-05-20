# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/fonts/Inter-Regular.ttf',           'assets/fonts'),
        ('assets/fonts/Inter-Medium.ttf',            'assets/fonts'),
        ('assets/fonts/Inter-SemiBold.ttf',          'assets/fonts'),
        ('assets/fonts/Inter-Bold.ttf',              'assets/fonts'),
        ('assets/fonts/JetBrainsMono-Regular.ttf',   'assets/fonts'),
        ('assets/fonts/JetBrainsMono-Medium.ttf',    'assets/fonts'),
    ],
    hiddenimports=[
        'google.generativeai',
        'google.genai',
        'google.ai.generativelanguage',
        'google.api_core',
        'google.auth',
    ],
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
    name='ProcessadorOcorrencias-v1.50',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
