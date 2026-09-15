# build_win.py - Windows build script
import PyInstaller.__main__
import os
import shutil
import sys
import urllib.request
import zipfile
import glob


def clean_build():
    for d in ['build', 'dist']:
        if os.path.exists(d):
            print(f"Cleaning {d}/ ...")
            shutil.rmtree(d)
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)


def download_vc_redist_dlls():
    """
    下载 VC++ 运行库的 DLL，并把它们放到 sklearn/.libs 和 PyInstaller 的收集目录
    通过 pip 安装的 sklearn 自带 .libs 目录，但里面可能缺少 msvcp140.dll
    我们从系统或网上获取
    """
    # 方式1：从系统目录找（GitHub Actions 的 Windows runner 有）
    system32 = r"C:\Windows\System32"
    dlls_needed = ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll']

    found_dlls = {}
    for dll in dlls_needed:
        src = os.path.join(system32, dll)
        if os.path.exists(src):
            found_dlls[dll] = src
            print(f"Found: {src}")
        else:
            print(f"Not found in System32: {dll}")

    return found_dlls


def build_app():
    print("=" * 70)
    print("Building Lithium Analyzer (Windows Version)")
    print("=" * 70)

    clean_build()

    # 先检查系统 DLL
    vc_dlls = download_vc_redist_dlls()

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
        '--hidden-import=sklearn._distributor_init',
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

    # ===== 打包完成后，把 DLL 复制到 sklearn/.libs/ =====
    print("\n" + "=" * 70)
    print("Copying VC++ runtime DLLs to sklearn/.libs/ ...")
    print("=" * 70)

    dist_dir = os.path.abspath('dist/LithiumAnalyzer')
    internal_dir = os.path.join(dist_dir, '_internal')

    # 找 sklearn 的 .libs 目录（可能在多个地方）
    target_dirs = []

    # 1. _internal/sklearn/.libs/
    sklearn_libs = os.path.join(internal_dir, 'sklearn', '.libs')
    if os.path.exists(sklearn_libs):
        target_dirs.append(sklearn_libs)

    # 2. _internal/.libs/
    root_libs = os.path.join(internal_dir, '.libs')
    if not os.path.exists(root_libs):
        os.makedirs(root_libs, exist_ok=True)
    target_dirs.append(root_libs)

    # 3. _internal/ 根目录（保险起见）
    target_dirs.append(internal_dir)

    # 复制 DLL
    copied_count = 0
    for dll_name, dll_src in vc_dlls.items():
        for target_dir in target_dirs:
            dst = os.path.join(target_dir, dll_name)
            try:
                shutil.copy2(dll_src, dst)
                print(f"  Copied {dll_name} -> {target_dir}")
                copied_count += 1
            except Exception as e:
                print(f"  Failed to copy {dll_name} to {target_dir}: {e}")

    print(f"\nTotal copied: {copied_count}")

    print("\n" + "=" * 70)
    print("BUILD COMPLETE!")
    print("=" * 70)
    exe_path = os.path.join(dist_dir, 'LithiumAnalyzer.exe')
    if os.path.exists(exe_path):
        print(f"Executable: {exe_path}")


if __name__ == '__main__':
    build_app()