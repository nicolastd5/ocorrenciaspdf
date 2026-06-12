# -*- mode: python ; coding: utf-8 -*-

import os

# O app usa apenas QtCore/QtGui/QtWidgets/QtSvg (ícones); o PyInstaller
# detecta esses pelos imports. Nunca usar collect_submodules('PySide6'):
# arrasta QtWebEngine (~195 MB), QtQuick, multimídia etc. e infla o exe.
hiddenimports = ['ui', 'ui.widgets', 'ui.tabs', 'ui.update_worker', 'ui.splash',
                 'ui.icons', 'PySide6.QtSvg']

datas = [
    ('assets/fonts', 'assets/fonts'),
]
if os.path.isfile('assets/logo.png'):
    datas.append(('assets/logo.png', 'assets'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
        # Módulos Qt pesados que o app não usa (defesa extra)
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtDesigner', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
    ],
    noarchive=False,
    optimize=0,
)
# opengl32sw.dll (~20 MB) é fallback de OpenGL por software — app QtWidgets não usa.
a.binaries = [b for b in a.binaries if not b[0].lower().endswith('opengl32sw.dll')]
# Traduções do Qt: mantém só português (botões padrão "Cancelar" etc.).
a.datas = [
    d for d in a.datas
    if not (d[0].replace('\\', '/').startswith('PySide6/translations/') and '_pt' not in d[0])
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProcessadorOcorrencias-v1.67',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
