
import sys

def fix_test_join():
    path = r'C:\Proyectos\Llamadas GPH\WindowsApp\test_join_fix.py'
    content = """import sqlite3
import database_core

def test_join():
    print("Iniciando prueba de JOIN y Índices...")
    database_core.init_db()
    
    conn = sqlite3.connect(database_core.DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        
        # Verificar índices
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = [r[0] for r in cursor.fetchall()]
        print(f"Índices encontrados: {indexes}")
        
        # Verificar JOIN
        print("Probando get_contactos...")
        res = database_core.get_contactos(query="") 
        if res:
            found_data = False
            for r in res[:20]: # Revisar los primeros 20
                if r.get('totalAdeudo') and r.get('totalAdeudo') > 0:
                    print(f"✅ Éxito: Encontrado contacto con adeudo: {r['ncliente']} - ${r['totalAdeudo']}")
                    found_data = True
                    break
            if not found_data:
                print("⚠️ Advertencia: No se encontró ningún contacto con adeudo en los primeros 20 resultados. Esto podría ser normal si no hay datos en 'cartera' para esos contactos.")
        else:
            print("❌ Error: no se retornaron contactos.")
            
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_join_fix = test_join  # Alias for backward compatibility if needed
    test_join()
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed test_join_fix.py")

if __name__ == "__main__":
    fix_test_join()
