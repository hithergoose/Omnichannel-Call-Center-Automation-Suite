
import sys

def fix_verify_robust():
    path = r'C:\Proyectos\Llamadas GPH\WindowsApp\verify_robust.py'
    content = """import sqlite3
import database_core

def verify():
    print("Iniciando Verificación Robusta...")
    database_core.init_db()
    
    conn = sqlite3.connect(database_core.DB_PATH, timeout=20, check_same_thread=False)
    try:
        c = conn.cursor()
        
        # Buscar un lote que esté en cartera
        c.execute("SELECT vivienda FROM cartera WHERE totalAdeudo > 0 LIMIT 1")
        row = c.fetchone()
        if not row:
            print("❌ No hay datos con adeudo en 'cartera'. No se puede verificar el JOIN.")
            return
        
        lote_objetivo = row[0]
        print(f"Lote objetivo de cartera: {lote_objetivo}")
        
        # Verificar si ese lote existe en contactos
        c.execute("SELECT ncliente FROM contactos WHERE lote = ?", (lote_objetivo,))
        c_contact = c.fetchone()
        if c_contact:
            print(f"✅ El lote {lote_objetivo} existe en 'contactos' para el cliente: {c_contact[0]}")
        else:
            print(f"⚠️ El lote {lote_objetivo} NO existe en 'contactos'. Probando con otro...")
            # Intentar al revés: buscar un contacto y ver si tiene cartera
            c.execute("SELECT lote FROM contactos LIMIT 10")
            lotes_c = [r[0] for r in c.fetchall()]
            found = False
            for l in lotes_c:
                c.execute("SELECT totalAdeudo FROM cartera WHERE vivienda = ?", (l,))
                res_ca = c.fetchone()
                if res_ca:
                    print(f"✅ Encontrado match manual: {l} tiene adeudo {res_ca[0]}")
                    found = True
                    break
            if not found:
                print("❌ No se encontró ningún match entre 'contactos' y 'cartera' con los datos actuales.")
                return

        # Probar la función final
        print(f"Llamando a get_contactos para el lote {lote_objetivo}...")
        res = database_core.get_contactos(query=lote_objetivo)
        if res:
            item = res[0]
            print(f"Resultado final:")
            print(f" - Cliente: {item['ncliente']}")
            print(f" - Adeudo: {item.get('totalAdeudo')}")
            if item.get('totalAdeudo', 0) > 0:
                print("✅ VERIFICACIÓN EXITOSA: El JOIN funciona y trae datos financieros.")
            else:
                print("❌ ERROR: El JOIN trajo el contacto pero el adeudo sigue siendo 0.")
        else:
            print("❌ ERROR: get_contactos no retornó el registro.")

    except Exception as e:
        print(f"❌ Error en verificación: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify()
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed verify_robust.py")

if __name__ == "__main__":
    fix_verify_robust()
