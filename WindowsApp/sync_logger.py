import os
from datetime import datetime

LOG_FILE = "sync_activity.log"

def log_event(event_type, message, record_count=None):
    """
    Registra un evento de sincronización en el archivo local y en consola.
    event_type: 'START', 'END', 'ERROR', 'PROGRESS', 'SYNC'
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count_str = f" | Registros: {record_count}" if record_count is not None else ""
    log_line = f"[{timestamp}] [{event_type}] {message}{count_str}"
    
    # 1. Mostrar en consola (REQUISITO v3)
    print(log_line)
    
    # 2. Guardar en archivo (append)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        # Silencioso en archivo para no romper el flujo principal
        print(f"[SyncLogger] Error escribiendo log a archivo: {e}")

def log_sync(message):
    """Log de estado genérico para trazabilidad de flujo."""
    log_event("SYNC", message)

def log_start(module_name):
    log_event("START", f"Iniciando sincronización de {module_name}")

def log_end(module_name, record_count):
    log_event("END", f"Sincronización de {module_name} completada con éxito", record_count)

def log_error(module_name, error_msg):
    log_event("ERROR", f"Error en sincronización de {module_name}: {error_msg}")
