
import sys

def fix_database_core():
    path = r'C:\Proyectos\Llamadas GPH\WindowsApp\database_core.py'
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    for i, line in enumerate(lines):
        if 'def save_cartera(clientes_list):' in line:
            new_lines.append('def save_cartera(clientes_list):\n')
            new_lines.append('    import sync_logger\n')
            new_lines.append('    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)\n')
            new_lines.append('    try:\n')
            new_lines.append('        with conn:\n')
            new_lines.append('            cursor = conn.cursor()\n')
            new_lines.append('            sync_logger.log_start("Cartera (Financiero)")\n')
            new_lines.append('            data = []\n')
            new_lines.append('            for c in clientes_list:\n')
            new_lines.append('                vivienda_norm = str(c.get("vivienda", "")).strip()\n')
            new_lines.append('                data.append((\n')
            new_lines.append('                    vivienda_norm, str(c.get("id_cobranza", "")), \n')
            new_lines.append('                    str(c.get("mesesadeudo", "")), str(c.get("clienteNombre", "")),\n')
            new_lines.append('                    float(c.get("totalAdeudo", 0) if c.get("totalAdeudo") else 0),\n')
            new_lines.append('                    str(c.get("fechaFondoReserva", "")), str(c.get("fecha1erMensMtto", "")),\n')
            new_lines.append('                    str(c.get("statusTerreno", "")),\n')
            new_lines.append('                    float(c.get("adeudo", 0) if c.get("adeudo") else 0),\n')
            new_lines.append('                    float(c.get("adeudoM", 0) if c.get("adeudoM") else 0)\n')
            new_lines.append('                ))\n')
            new_lines.append('            \n')
            new_lines.append('            upsert_sql = """\n')
            new_lines.append('                INSERT INTO cartera (\n')
            new_lines.append('                    vivienda, id_cobranza, mesesadeudo, clienteNombre, \n')
            new_lines.append('                    totalAdeudo, fechaFondoReserva, fecha1erMensMtto,\n')
            new_lines.append('                    statusTerreno, adeudo, adeudoM, updated_at\n')
            new_lines.append('                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now", "localtime"))\n')
            new_lines.append('                ON CONFLICT(vivienda) DO UPDATE SET\n')
            new_lines.append('                    id_cobranza=excluded.id_cobranza, mesesadeudo=excluded.mesesadeudo,\n')
            new_lines.append('                    clienteNombre=excluded.clienteNombre, totalAdeudo=excluded.totalAdeudo,\n')
            new_lines.append('                    fechaFondoReserva=excluded.fechaFondoReserva, fecha1erMensMtto=excluded.fecha1erMensMtto,\n')
            new_lines.append('                    statusTerreno=excluded.statusTerreno, adeudo=excluded.adeudo,\n')
            new_lines.append('                    adeudoM=excluded.adeudoM, updated_at=datetime("now", "localtime")\n')
            new_lines.append('            """\n')
            new_lines.append('            cursor.executemany(upsert_sql, data)\n')
            new_lines.append('            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", \n')
            new_lines.append('                           ("cartera_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))\n')
            new_lines.append('            sync_logger.log_end("Cartera (Financiero)", len(clientes_list))\n')
            new_lines.append('    except Exception as e:\n')
            new_lines.append('        print(f"[Local DB] Error save_cartera: {e}")\n')
            new_lines.append('        try:\n')
            new_lines.append('            import sync_logger\n')
            new_lines.append('            sync_logger.log_error("Cartera (Financiero)", str(e))\n')
            new_lines.append('        except: pass\n')
            new_lines.append('    finally:\n')
            new_lines.append('        conn.close()\n')
            skip = True
            continue
        
        if skip:
            if i + 1 < len(lines) and lines[i+1].startswith('def '):
                skip = False
            elif i + 1 == len(lines):
                 skip = False
            continue
            
        new_lines.append(line)

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Fixed database_core.py")

if __name__ == "__main__":
    fix_database_core()
