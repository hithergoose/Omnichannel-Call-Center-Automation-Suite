import os
import sys
import subprocess
import shutil
import customtkinter

def build_portable():
    print("--- Iniciando construcción de versión Portable ---")
    
    # 1. Obtener rutas necesarias
    ctk_path = os.path.dirname(customtkinter.__file__)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    browsers_path = os.path.join(project_dir, "ms-playwright")
    
    print(f"Ruta CustomTkinter: {ctk_path}")
    print(f"Ruta Navegadores: {browsers_path}")
    
    # 2. Comando Base de PyInstaller
    # --add-data "ruta_origen;ruta_destino_en_exe"
    command = [
        "python", "-m", "PyInstaller",
        "--name=Central_GPH",
        "--noconfirm",
        "--clean",
        "--noconsole",
        "--onedir",
        "--icon=favicon (7).ico",
        f"--add-data=favicon (7).ico;.",
        f"--add-data=logo_gph.png;.",
        f"--add-data={ctk_path};customtkinter/",
        f"--add-data={browsers_path};ms-playwright/",
        "--hidden-import=customtkinter",
        "--hidden-import=playwright",
        "--hidden-import=pyaudiowpatch",
        "--hidden-import=soundfile",
        "--hidden-import=numpy",
        "--hidden-import=pandas",
        "--hidden-import=openpyxl",
        "--hidden-import=sqlite3",
        "--hidden-import=requests",
        "--hidden-import=PIL",
        "main.py"
    ]
    
    print("Ejecutando PyInstaller...")
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("OK: Construccion Portable completada con exito en la carpeta 'dist/Central_GPH'")
    else:
        print("ERROR: Error en la construccion:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

if __name__ == "__main__":
    build_portable()
