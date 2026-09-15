# build_win.py - Windows 打包脚本
import PyInstaller.__main__
import os
import shutil


def clean_build():
    for d in ['build', 'dist']:
        if os.path.exists(d):
            print(f"清理 {d}/ ...")
            shutil.rmtree(d)
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)


def build_app():
    print("=" * 70)
    print("打包碳酸锂分析工具 (Windows 版)")
    print("=" * 70)

    clean_build()

    PyInstaller.__main__.run([
        'main.py',
        '--onedir',
        '--windowed',
        '--name=碳酸锂分析工具',
        # Windows 上用分号 ;
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
    print("✅ 打包完成！")
    print("=" * 70)
    exe_path = os.path.abspath('dist/碳酸锂分析工具/碳酸锂分析工具.exe')
    if os.path.exists(exe_path):
        print(f"📁 可执行文件: {exe_path}")


if __name__ == '__main__':
    build_app()