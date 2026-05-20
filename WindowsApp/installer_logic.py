import os
import sys
import shutil
import zipfile
import time
from datetime import datetime
import ctypes
import winshell
from win32com.client import Dispatch

def create_shortcut(target_exe, shortcut_name):
    try:
        desktop = winshell.desktop()
        path = os.path.join(desktop, f"{shortcut_name}.lnk")
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target_exe
        shortcut.WorkingDirectory = os.path.dirname(target_exe)
        shortcut.IconLocation = target_exe
        shortcut.save()
        return True
    except Exception as e:
        print(f"Error creando acceso directo: {e}")
        return False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_installer():
    print("--- Instalador de Central GPH ---")
    
    target_dir = r"C:\Central_GPH"
    zip_name = "app_bundle.zip"
    
    # 1. Buscar el ZIP dentro del ejecutable (PyInstaller sys._MEIPASS)
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    zip_path = os.path.join(base_path, zip_name)
    
    if not os.path.exists(zip_path):
        print(f"Error: No se encontró el archivo de datos {zip_name}")
        input("Presiona Enter para salir...")
        return

    # 2. Gestionar instalación previa
    if os.path.exists(target_dir):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{target_dir}_OLD_{timestamp}"
        print(f"Detectada instalación previa. Renombrando a: {backup_name}")
        try:
            os.rename(target_dir, backup_name)
        except Exception as e:
            print(f"Error al renombrar: {e}")
            print("Asegúrate de que la app no esté abierta.")
            input("Presiona Enter para salir...")
            return

    # 3. Crear carpeta y extraer
    print(f"Instalando en {target_dir}...")
    os.makedirs(target_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_dir)
    
    # 4. Crear acceso directo
    exe_path = os.path.join(target_dir, "Central_GPH.exe")
    if os.path.exists(exe_path):
        print("Creando acceso directo en el escritorio...")
        if create_shortcut(exe_path, "Central GPH"):
            print("OK: Acceso directo creado.")
    
    print("\n--- ¡INSTALACIÓN COMPLETADA CON ÉXITO! ---")
    print(f"La aplicación se ha instalado en: {target_dir}")
    print("Puedes encontrar el icono en tu Escritorio.")
    time.sleep(3)
    # input("\nPresiona Enter para finalizar...")

if __name__ == "__main__":
    run_installer()
