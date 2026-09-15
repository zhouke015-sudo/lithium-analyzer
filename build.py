# build.py
import PyInstaller.__main__
import os
import shutil


def clean_build():
    for d in ['build', 'dist']:
        if os.path.exists(d):
            print(f"🗑️  清理 {d}/ 目录...")
            try:
                shutil.rmtree(d)
            except:
                pass


def build_app():
    print("=" * 70)
    print("🔨 打包碳酸锂分析工具 (手动输入版本)")
    print("=" * 70)

    clean_build()

    PyInstaller.__main__.run([
        'main.py',
        '--onedir',
        '--windowed',
        '--name=碳酸锂分析工具',
        '--add-data=data_processor.py:.',
        '--add-data=conduction_quant_v2.py:.',
        '--add-data=fundamental_quant.py:.',
        '--add-data=futures_api.py:.',
        '--hidden-import=PyQt5.sip',
        '--hidden-import=pandas',
        '--hidden-import=numpy',
        '--hidden-import=matplotlib',
        '--hidden-import=openpyxl',
        '--hidden-import=sklearn',
        '--hidden-import=sklearn.neighbors',
        '--hidden-import=sklearn.preprocessing',
        '--hidden-import=scipy',  # 新增
        '--hidden-import=scipy.sparse',  # 新增
        '--hidden-import=matplotlib.backends.backend_qt5agg',
        '--collect-all=PyQt5',
        '--collect-all=matplotlib',
        '--collect-all=sklearn',
        '--collect-all=scipy',  # 新增
        '--exclude-module=torch',
        '--exclude-module=tensorflow',
        # '--exclude-module=scipy',                 # 删除这行！
        '--clean',
        '--noconfirm',
    ])

    print("\n" + "=" * 70)
    print("✅ 打包完成！")
    print("=" * 70)

    app_path = os.path.abspath('dist/碳酸锂分析工具.app')
    if os.path.exists(app_path):
        print(f"📁 应用程序位置: {app_path}")


if __name__ == '__main__':
    build_app()