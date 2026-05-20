import os
import subprocess
import zipfile
import shutil

def zip_directory(path, zip_handler):
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            # El arco dentro del zip debe ser relativo a la carpeta dist/Central_GPH
            arcname = os.path.relpath(file_path, path)
            zip_handler.write(file_path, arcname)

def build_installer():
    print("--- Generando Instalador Final ---")
    
    # 1. Asegurar que la versión portable esté actualizada
    print("Actualizando versión portable...")
    result_portable = subprocess.run(["python", "build_portable.py"])
    
    if result_portable.returncode != 0:
        print("Error: Falló la compilación de la versión portable.")
        import sys
        sys.exit(1)
        
    if not os.path.exists("dist/Central_GPH"):
        print("Error: No se pudo generar la versión portable.")
        return

    # 2. Comprimir la versión portable en app_bundle.zip
    print("Comprimiendo aplicación...")
    with zipfile.ZipFile("app_bundle.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        zip_directory("dist/Central_GPH", zipf)
    
    # 3. Compilar el instalador con PyInstaller
    print("Compilando ejecutable del instalador...")
    command = [
        "python", "-m", "PyInstaller",
        "--name=Instalador_Central_GPH",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--icon=favicon (7).ico",
        "--add-data=app_bundle.zip;.",
        "--hidden-import=winshell",
        "--hidden-import=win32com",
        "installer_logic.py"
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("\nOK: El instalador se encuentra en 'dist/Instalador_Central_GPH.exe'")
        # Limpieza opcional
        if os.path.exists("app_bundle.zip"):
            os.remove("app_bundle.zip")
    else:
        print("ERROR: Error compilando el instalador:")
        print(result.stderr)

if __name__ == "__main__":
    build_installer()
