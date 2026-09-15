# build_win.py - Windows 打包脚本
import PyInstaller.__main__
import os
import shutil


def clean_build():
    for d in ['build', 'dist']:
        if os.path.exists(d):
            print(f"Cleaning {d}/ ...")
            shutil.rmtree(d)
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)


def build_app():
    print("=" * 70)
    print("Building Lithium Analyzer (Windows Version)")
    print("=" * 70)

    clean_build()

    PyInstaller.__main__.run([
        'main.py',
        '--onedir',
        '--windowed',
        '--name=LithiumAnalyzer',
        '--add-data=data_processor.py;.',
        '--add-data=conduction_quant_v2.py;.',
        '--add-data=fundamental_quant.py;.',
        '--add-data=futures_api.py;.',
        '--hidden-import=PyQt5.sip',
        '--hidden-import=pandas',
        '--hidden-import=numpy',
        '--hidden-import=matplotlib',
        '--hidden-import=openpyxl',
        '--hidden-import=sklearn',
        '--hidden-import=sklearn.neighbors',
        '--hidden-import=sklearn.preprocessing',
        '--hidden-import=scipy',
        '--hidden-import=scipy.sparse',
        '--hidden-import=matplotlib.backends.backend_qt5agg',
        '--collect-all=PyQt5',
        '--collect-all=matplotlib',
        '--collect-all=sklearn',
        '--collect-all=scipy',
        '--exclude-module=torch',
        '--exclude-module=tensorflow',
        '--exclude-module=akshare',
        '--clean',
        '--noconfirm',
    ])

    print("\n" + "=" * 70)
    print("BUILD COMPLETE!")
    print("=" * 70)
    exe_path = os.path.abspath('dist/LithiumAnalyzer/LithiumAnalyzer.exe')
    if os.path.exists(exe_path):
        print(f"Executable: {exe_path}")


if __name__ == '__main__':
    build_app()