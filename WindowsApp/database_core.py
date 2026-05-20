import sqlite3
import os
import threading
import json
import shutil
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
DB_PATH = "gph_data.db"
DEBUG_MODE = True  # Flag global de hardening

def normalize_numeric(val):
    """Normalización financiera centralizada (Enterprise vFinal)"""
    if val is None: return 0.0
    try:
        if isinstance(val, (int, float)): return float(val)
        return float(str(val).replace("$", "").replace(",", "").replace("-", "0") or 0)
    except: return 0.0

class AppState:
    """Objeto central para control de estado global (Hardening v2)"""
    phone_connected = False
    audio_active = False
    syncing = False  # Nuevo (Hardening v2.1)
    current_client = None # Detallado: {id, lote, nombre, ts, valid}
    last_error = None
    last_sync = None
    session_valid = False
    uptime_start = datetime.now()

def safe_execute(fn, context="Generic"):
    """Wrapper para ejecución segura con telemetría automática (Hardening v2)"""
    try:
        return fn()
    except Exception as e:
        log_telemetry("SYSTEM", f"Fallo en {context}: {e}", "ERROR")
        print(f"[SAFE EXEC] Error en {context}: {e}")
        return None

def init_db():
    print("[DB] Iniciando SQLite...")
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_sec INTEGER,
                file_path TEXT
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cartera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vivienda TEXT UNIQUE,
                id_cobranza TEXT,
                mesesadeudo TEXT,
                clienteNombre TEXT DEFAULT '',
                nestatus TEXT DEFAULT '',
                anualidad REAL DEFAULT 0,
                adeudo_otros REAL DEFAULT 0,
                totalAdeudo REAL DEFAULT 0,
                totalAdeudoLL REAL DEFAULT 0,
                ugestion TEXT DEFAULT '',
                fultpago TEXT DEFAULT '',
                fechaFondoReserva TEXT DEFAULT '',
                fecha1erMensMtto TEXT DEFAULT '',
                statusTerreno TEXT DEFAULT '',
                adeudo REAL DEFAULT 0,
                adeudoM REAL DEFAULT 0,
                asesorNombre TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS gestiones_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lote TEXT,
                id_cobranza TEXT,
                comentario TEXT,
                status TEXT,
                error_msg TEXT,
                created_at TEXT
            )
            ''')
            # Índices de performance para filtros avanzados
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_vivienda ON cartera(vivienda)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_nestatus ON cartera(nestatus)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_statusTerreno ON cartera(statusTerreno)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_asesor ON cartera(asesorNombre)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_meses ON cartera(mesesadeudo)")
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                description TEXT,
                status TEXT,
                context TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_event_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                payload TEXT,
                file_path TEXT,
                attempts INTEGER DEFAULT 0,
                status  TEXT DEFAULT 'PENDING',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS contactos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nproyecto TEXT,
                siglas TEXT,
                condominio TEXT,
                lote TEXT,
                ncliente TEXT,
                isEmpresa TEXT,
                cemail TEXT,
                ccelular TEXT,
                cfijo TEXT,
                estatus TEXT,
                adeudo REAL,
                calle TEXT,
                numExt TEXT,
                colonia TEXT,
                municipio TEXT,
                estado TEXT,
                cod_post TEXT,
                Reflote TEXT,
                ClaveCat TEXT,
                id_proy TEXT,
                id_proy_cond TEXT,
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(nproyecto, condominio, lote)
            )
            ''')
            PROYECTOS_PERMITIDOS = [
                "CIUDAD MADERAS BOSQUES", "CIUDAD MADERAS CELAYA", "CIUDAD MADERAS CORREGIDORA QUERÉTARO", "CIUDAD MADERAS LEON",
                "CIUDAD MADERAS MONTAÑA LEÓN", "CIUDAD MADERAS MONTAÑA QUERÉTARO", "CIUDAD MADERAS MONTAÑA SAN LUIS", "CIUDAD MADERAS NORTE QUERETARO",
                "CIUDAD MADERAS PENÍNSULA", "CIUDAD MADERAS PRIVADA BOSQUES", "CIUDAD MADERAS PRIVADA CORREGIDORA", "CIUDAD MADERAS PRIVADA PENÍNSULA",
                "CIUDAD MADERAS QUERÉTARO", "CIUDAD MADERAS SAN LUIS POTOSI", "CIUDAD MADERAS SAN MIGUEL", "CIUDAD MADERAS SUR I", "CIUDAD MADERAS SUR II"
            ]
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                           ("proyectos_permitidos", ", ".join(PROYECTOS_PERMITIDOS)))
            
            # Migraciones silenciosas
            for col_name, col_type in [
                ("totalAdeudo", "REAL DEFAULT 0"), ("fechaFondoReserva", "TEXT DEFAULT ''"),
                ("fecha1erMensMtto", "TEXT DEFAULT ''"), ("statusTerreno", "TEXT DEFAULT ''"),
                ("adeudo", "REAL DEFAULT 0"), ("adeudoM", "REAL DEFAULT 0"),
                ("asesorNombre", "TEXT DEFAULT ''")
            ]:
                try: cursor.execute(f"ALTER TABLE cartera ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError: pass # Ignorar si ya existe

            for table, col in [("contactos", "updated_at"), ("cartera", "updated_at")]:
                try: cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError: pass

            indices = [
                "CREATE INDEX IF NOT EXISTS idx_contactos_lote ON contactos(lote)",
                "CREATE INDEX IF NOT EXISTS idx_cartera_vivienda ON cartera(vivienda)",
                "CREATE INDEX IF NOT EXISTS idx_cartera_nestatus ON cartera(nestatus)",
                "CREATE INDEX IF NOT EXISTS idx_cartera_totalAdeudo ON cartera(totalAdeudo)"
            ]
            for idx_sql in indices:
                try: cursor.execute(idx_sql)
                except sqlite3.OperationalError: pass

            try: cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'Usuario'")
            except sqlite3.OperationalError: pass

            cursor.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin', 'Administrador')")
            else:
                cursor.execute("UPDATE users SET role='Administrador' WHERE username='admin'")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contactos_lote ON contactos(lote)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_vivienda ON cartera(vivienda)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contactos_ncliente ON contactos(ncliente)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contactos_proy ON contactos(nproyecto)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contactos_cond ON contactos(condominio)")
        
        # --- MIGRACIÓN FORZOSA DE COLUMNAS (Añadir si faltan) ---
        print("[DB] Verificando integridad de columnas...")
        with conn:
            cursor = conn.cursor()
            # Asegurar columnas en tabla 'calls'
            try: cursor.execute("ALTER TABLE calls ADD COLUMN lote TEXT DEFAULT ''")
            except sqlite3.OperationalError: pass # Ya existe
            
            try: cursor.execute("ALTER TABLE calls ADD COLUMN cliente TEXT DEFAULT ''")
            except sqlite3.OperationalError: pass # Ya existe

            # Asegurar columnas en 'gestiones_log'
            try: cursor.execute("ALTER TABLE gestiones_log ADD COLUMN payload_resumen TEXT DEFAULT ''")
            except sqlite3.OperationalError: pass # Ya existe
        # ----------------------------------------------------------------

        print("[DB] Configurando migración industrial de cartera...")
        migrate_cartera_vivienda_unique()
        run_v3_migration()
    except Exception as e:
        print(f"[DB Error] Error init_db: {e}")
    finally:
        conn.close()
    print("[DB] Base de datos lista.")

def create_db_backup():
    """Crea una copia física de la base de datos para seguridad antes de migraciones."""
    try:
        backup_name = "gph_data_backup_v3.db"
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_name)
            print(f"[Backup] Copia de seguridad v3 creada exitosamente.")
            return True
    except Exception as e:
        print(f"[Backup] Error creando copia: {e}")
    return False

def _migrate_contactos_table(cursor):
    """
    Migración segura para añadir restricción UNIQUE si no existe.
    SQLite no permite ALTER TABLE ADD CONSTRAINT.
    """
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='contactos'")
    row = cursor.fetchone()
    if row:
        sql = row[0]
        # Limpieza de espacios para matching robusto
        clean_sql = sql.replace(" ", "").replace("\n", "").replace("\t", "")
        if "UNIQUE(nproyecto,condominio,lote)" not in clean_sql:
            print("[DB Migration] Recreando tabla contactos para añadir restricción UNIQUE...")
            try:
                # 1. Renombrar
                cursor.execute("ALTER TABLE contactos RENAME TO contactos_old")
                # 2. Crear nueva
                cursor.execute('''
                    CREATE TABLE contactos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nproyecto TEXT,
                        siglas TEXT,
                        condominio TEXT,
                        lote TEXT,
                        ncliente TEXT,
                        isEmpresa TEXT,
                        cemail TEXT,
                        ccelular TEXT,
                        cfijo TEXT,
                        estatus TEXT,
                        adeudo REAL,
                        calle TEXT,
                        numExt TEXT,
                        colonia TEXT,
                        municipio TEXT,
                        estado TEXT,
                        cod_post TEXT,
                        Reflote TEXT,
                        ClaveCat TEXT,
                        id_proy TEXT,
                        id_proy_cond TEXT,
                        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                        UNIQUE(nproyecto, condominio, lote)
                    )
                ''')
                # 3. Migrar datos existentes (INSERT OR IGNORE evita fallos por duplicados previos)
                cursor.execute('''
                    INSERT OR IGNORE INTO contactos (
                        id, nproyecto, siglas, condominio, lote, ncliente, isEmpresa,
                        cemail, ccelular, cfijo, estatus, adeudo, calle, numExt, 
                        colonia, municipio, estado, cod_post, Reflote, ClaveCat, 
                        id_proy, id_proy_cond, updated_at
                    ) SELECT 
                        id, nproyecto, siglas, condominio, lote, ncliente, isEmpresa,
                        cemail, ccelular, cfijo, estatus, adeudo, calle, numExt, 
                        colonia, municipio, estado, cod_post, Reflote, ClaveCat, 
                        id_proy, id_proy_cond, updated_at
                    FROM contactos_old
                ''')
                # 4. Borrar tabla vieja
                cursor.execute("DROP TABLE contactos_old")
                print("[DB Migration] Tabla contactos actualizada exitosamente.")
            except Exception as e:
                print(f"[DB Migration] Error crítico en migración: {e}")
                # Intentar revertir si es posible
                try: cursor.execute("ALTER TABLE contactos_old RENAME TO contactos")
                except: pass

def run_v3_migration():
    """Normalización de datos (TRIM). Ejecuta backup y omite telemetría para evitar locks."""
    if get_config("migration_v3_done") == "1":
        return
    
    print("[Migration v3] Iniciando normalización de datos...")
    create_db_backup()
    
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            
            # Detectar conflictos
            cursor.execute("""
                SELECT nproyecto, condominio, lote, COUNT(*) FROM contactos 
                GROUP BY nproyecto, condominio, TRIM(lote) HAVING COUNT(*) > 1
            """)
            contactos_conflicts = cursor.fetchall()
            
            cursor.execute("SELECT vivienda, COUNT(*) FROM cartera GROUP BY TRIM(vivienda) HAVING COUNT(*) > 1")
            cartera_conflicts = cursor.fetchall()
            
            if contactos_conflicts or cartera_conflicts:
                print(f"[Migration v3] ALERTA: {len(contactos_conflicts) + len(cartera_conflicts)} colisiones potenciales. Omitiendo sospechosos.")

            # Normalizar
            cursor.execute("""
                UPDATE contactos SET lote = TRIM(lote) 
                WHERE (nproyecto, condominio, TRIM(lote)) NOT IN (
                    SELECT nproyecto, condominio, TRIM(lote) FROM contactos 
                    GROUP BY nproyecto, condominio, TRIM(lote) HAVING COUNT(*) > 1
                )
            """)
            count_cont = cursor.rowcount
            
            cursor.execute("""
                UPDATE cartera SET vivienda = TRIM(vivienda)
                WHERE TRIM(vivienda) NOT IN (
                    SELECT TRIM(vivienda) FROM cartera GROUP BY TRIM(vivienda) HAVING COUNT(*) > 1
                )
            """)
            count_cart = cursor.rowcount
            
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("migration_v3_done", "1"))
            print(f"[Migration v3] Éxito. Normalizados: {count_cont} contactos, {count_cart} vivienda.")
        
    except Exception as e:
        print(f"[Migration v3] ERROR: {e}")
    finally:
        conn.close()

def cleanup_old_logs():
    """Elimina logs de telemetría más antiguos de 7 días (Hardening v2)"""
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM telemetry_log WHERE created_at < datetime('now', '-7 days')")
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"[DB] Limpieza de telemetría: {deleted} registros eliminados.")
    except Exception as e:
        print(f"[DB] Error en cleanup_old_logs: {e}")
    finally: conn.close()

def log_call(phone_number, file_path, start_time, duration_sec, lote="", cliente=""):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            # Intentamos agregar las columnas si no existen (Migración silenciosa)
            try: cursor.execute("ALTER TABLE calls ADD COLUMN lote TEXT DEFAULT ''")
            except: pass
            try: cursor.execute("ALTER TABLE calls ADD COLUMN cliente TEXT DEFAULT ''")
            except: pass
            
            cursor.execute("""
                INSERT INTO calls (phone_number, start_time, duration_sec, file_path, lote, cliente) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (phone_number, start_time.strftime("%Y-%m-%d %H:%M:%S"), duration_sec, file_path, lote, cliente))
    finally:
        conn.close()

def log_gestion(lote, id_cobranza, status, error_msg="", comentario="", payload_resumen=""):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            # Migración silenciosa
            try: cursor.execute("ALTER TABLE gestiones_log ADD COLUMN payload_resumen TEXT DEFAULT ''")
            except: pass
            
            cursor.execute("""
                INSERT INTO gestiones_log (lote, id_cobranza, status, error_msg, comentario, created_at, payload_resumen) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (lote, id_cobranza, status, error_msg, comentario, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), payload_resumen))
    except Exception as e:
        print(f"[Local DB] Error log_gestion: {e}")
    finally:
        conn.close()

def migrate_cartera_vivienda_unique():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cartera'")
        row = cursor.fetchone()
        if not row: return
        sql = row[0].replace(" ", "").replace("\n", "").replace("\t", "")
        if "viviendaTEXTUNIQUE" in sql:
            return

        print("[DB Migration] Iniciando migración industrial de cartera...")
        backup_name = "gph_cartera_backup_pre_migration.db"
        if os.path.exists(DB_PATH):
            import shutil
            shutil.copy2(DB_PATH, backup_name)

        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cartera")
            total_original = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM cartera WHERE vivienda IS NULL OR TRIM(vivienda) = ''")
            total_descartados = cursor.fetchone()[0]

            cursor.execute("CREATE TABLE IF NOT EXISTS cartera_backup_v4 AS SELECT * FROM cartera")
            cursor.execute("DROP TABLE IF EXISTS cartera_new")
            cursor.execute('''
                CREATE TABLE cartera_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vivienda TEXT UNIQUE,
                    id_cobranza TEXT,
                    mesesadeudo TEXT,
                    clienteNombre TEXT DEFAULT '',
                    nestatus TEXT DEFAULT '',
                    anualidad REAL DEFAULT 0,
                    adeudo_otros REAL DEFAULT 0,
                    totalAdeudo REAL DEFAULT 0,
                    totalAdeudoLL REAL DEFAULT 0,
                    ugestion TEXT DEFAULT '',
                    fultpago TEXT DEFAULT '',
                    fechaFondoReserva TEXT DEFAULT '',
                    fecha1erMensMtto TEXT DEFAULT '',
                    statusTerreno TEXT DEFAULT '',
                    adeudo REAL DEFAULT 0,
                    adeudoM REAL DEFAULT 0,
                    asesorNombre TEXT DEFAULT '',
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            ''')

            # Manejo tolerante a fallos si las columnas no existen en la BD vieja
            cursor.execute("PRAGMA table_info(cartera)")
            columnas_existentes = [col[1] for col in cursor.fetchall()]
            
            # Construir SELECT dinámico
            cols_to_select = "TRIM(vivienda), id_cobranza, mesesadeudo, clienteNombre, nestatus, anualidad, adeudo_otros, totalAdeudo, totalAdeudoLL, ugestion, fultpago, fechaFondoReserva, fecha1erMensMtto, statusTerreno, adeudo, adeudoM"
            
            if "asesorNombre" in columnas_existentes:
                cols_to_select += ", asesorNombre, updated_at"
                cols_to_insert = "vivienda, id_cobranza, mesesadeudo, clienteNombre, nestatus, anualidad, adeudo_otros, totalAdeudo, totalAdeudoLL, ugestion, fultpago, fechaFondoReserva, fecha1erMensMtto, statusTerreno, adeudo, adeudoM, asesorNombre, updated_at"
            else:
                cols_to_select += ", '', updated_at" # Valor por defecto si no existe
                cols_to_insert = "vivienda, id_cobranza, mesesadeudo, clienteNombre, nestatus, anualidad, adeudo_otros, totalAdeudo, totalAdeudoLL, ugestion, fultpago, fechaFondoReserva, fecha1erMensMtto, statusTerreno, adeudo, adeudoM, asesorNombre, updated_at"

            cursor.execute(f'''
                INSERT OR IGNORE INTO cartera_new ({cols_to_insert})
                SELECT DISTINCT {cols_to_select}
                FROM cartera
                WHERE TRIM(vivienda) IS NOT NULL AND TRIM(vivienda) != ''
            ''')

            cursor.execute("SELECT COUNT(*) FROM cartera_new")
            total_migrados = cursor.fetchone()[0]
            duplicados_eliminados = (total_original - total_descartados) - total_migrados

            cursor.execute("DROP TABLE cartera")
            cursor.execute("ALTER TABLE cartera_new RENAME TO cartera")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cartera_vivienda ON cartera(vivienda)")

    except Exception as e:
        print(f"[DB Migration ERROR] Cartera: {e}")
    finally:
        conn.close()

def log_telemetry(category, description, status="INFO", context=""):
    """
    Registra un evento de telemetría en la base de datos local.
    NO bloquea y captura errores internos silenciosamente.
    """
    def task():
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            with conn:
                cursor = conn.cursor()
                # Si context es un dict, convertirlo a JSON, sino dejarlo como string
                ctx_str = context
                if isinstance(context, dict):
                    if 'user' not in context: context['user'] = CURRENT_USER or "NoAuth"
                    if 'phone_ip' not in context: context['phone_ip'] = get_config("phone_ip") or "None"
                    ctx_str = json.dumps(context)
                
                cursor.execute("""
                    INSERT INTO telemetry_log (category, description, status, context)
                    VALUES (?, ?, ?, ?)
                """, (category, description, status, ctx_str))
            conn.close()
        except Exception as e:
            print(f"[Telemetry Error] {e}")

    threading.Thread(target=task, daemon=True).start()

def save_contactos(contactos_list, on_progress=None):
    import sync_logger
    total = len(contactos_list)
    if total == 0: return

    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        # Optimización de rendimiento
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        sync_logger.log_start("Contactos (PosVenta)")
        
        # 1. Preparar datos (procesamiento rápido en memoria)
        data = []
        for c in contactos_list:
            lote_norm = str(c.get('lote', '')).strip()
            data.append((
                str(c.get('nproyecto', '')), str(c.get('siglas', '')), str(c.get('condominio', '')),
                lote_norm, str(c.get('ncliente', '')), str(c.get('isEmpresa', '')),
                str(c.get('cemail', '')), str(c.get('ccelular', '')), str(c.get('cfijo', '')),
                str(c.get('estatus', '')), float(c.get('adeudo', 0) if c.get('adeudo') else 0),
                str(c.get('calle', '')), str(c.get('numExt', '')), str(c.get('colonia', '')),
                str(c.get('municipio', '')), str(c.get('estado', '')), str(c.get('cod_post', '')),
                str(c.get('Reflote', '')), str(c.get('ClaveCat', '')),
                str(c.get('id_proy', '')), str(c.get('id_proy_cond', ''))
            ))

        upsert_sql = """
            INSERT INTO contactos (
                nproyecto, siglas, condominio, lote, ncliente, isEmpresa, 
                cemail, ccelular, cfijo, estatus, adeudo, calle, numExt, 
                colonia, municipio, estado, cod_post, Reflote, ClaveCat, 
                id_proy, id_proy_cond, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(nproyecto, condominio, lote) DO UPDATE SET
                siglas=excluded.siglas, ncliente=excluded.ncliente, isEmpresa=excluded.isEmpresa,
                cemail=excluded.cemail, ccelular=excluded.ccelular, cfijo=excluded.cfijo,
                estatus=excluded.estatus, adeudo=excluded.adeudo, calle=excluded.calle,
                numExt=excluded.numExt, colonia=excluded.colonia, municipio=excluded.municipio,
                estado=excluded.estado, cod_post=excluded.cod_post, Reflote=excluded.Reflote,
                ClaveCat=excluded.ClaveCat, id_proy=excluded.id_proy, id_proy_cond=excluded.id_proy_cond,
                updated_at=datetime('now', 'localtime')
        """

        # 2. Inserción por lotes con commits periódicos
        batch_size = 1000
        commit_threshold = 5000
        processed = 0
        
        # Usamos una transacción explícita
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        for i in range(0, total, batch_size):
            chunk = data[i : i + batch_size]
            cursor.executemany(upsert_sql, chunk)
            processed += len(chunk)
            
            # Commit parcial cada 5,000 registros
            if processed % commit_threshold == 0 or processed >= total:
                conn.commit()
                if processed < total:
                    cursor.execute("BEGIN TRANSACTION")
            
            # Notificar progreso a la UI (0.95 + 0.05 de la fase de guardado)
            if on_progress:
                percent = 0.95 + ((processed / total) * 0.05)
                # Aseguramos que el hilo de la UI reciba la actualización
                on_progress(min(percent, 0.99), f"Guardando: {processed:,} / {total:,}")
            
            # Log de consola para monitoreo
            if i % 5000 == 0:
                print(f"[SYNC] Procesados {processed:,} / {total:,} registros...")

        # Finalizar metadatos
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                      ("contactos_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        sync_logger.log_end("Contactos (PosVenta)", total)
        if on_progress:
            on_progress(1.0, "✅ Actualización completada")
            
    except Exception as e:
        print(f"[Local DB] Error save_contactos: {e}")
        conn.rollback()
        raise e
    finally: conn.close()

def get_unique_values(column_name, table="cartera"):
    """Retorna una lista de valores únicos para una columna específica."""
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        source_table = "contactos" if column_name in ["nproyecto", "condominio"] else "cartera"
        if table != "cartera": source_table = table
        
        sql = f"SELECT DISTINCT {column_name} FROM {source_table} WHERE {column_name} IS NOT NULL AND {column_name} != '' ORDER BY {column_name} ASC"
        cursor.execute(sql)
        return [str(r[0]) for r in cursor.fetchall()]
    except Exception as e:
        print(f"[DB] Error get_unique_values ({column_name}): {e}")
        return []
    finally: conn.close()

def get_proyectos_list():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT nproyecto FROM contactos WHERE nproyecto IS NOT NULL AND nproyecto != '' ORDER BY nproyecto ASC")
        return [r[0] for r in cursor.fetchall()]
    except: return []
    finally: conn.close()

def get_condominios_list(proyecto=None):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        if proyecto and proyecto != "Todos":
            cursor.execute("SELECT DISTINCT condominio FROM contactos WHERE nproyecto = ? AND condominio IS NOT NULL ORDER BY condominio ASC", (proyecto,))
        else:
            cursor.execute("SELECT DISTINCT condominio FROM contactos WHERE condominio IS NOT NULL ORDER BY condominio ASC")
        return [r[0] for r in cursor.fetchall()]
    except: return []
    finally: conn.close()

def get_contactos(query=None, proyecto=None, condominio=None, col_filters=None, sin_telefono=False, limit=100, offset=0):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        sql = """SELECT c.ncliente, c.lote, c.ccelular, c.cfijo, ca.statusTerreno, ca.nestatus, 
                 ca.mesesadeudo, ca.anualidad, ca.adeudo, ca.adeudoM, ca.adeudo_otros, 
                 ca.totalAdeudo, ca.totalAdeudoLL, ca.asesorNombre, ca.ugestion, ca.fultpago, 
                 ca.fechaFondoReserva, ca.fecha1erMensMtto
                 FROM contactos c LEFT JOIN cartera ca ON c.lote = ca.vivienda WHERE 1=1"""
        params = []
        if proyecto and proyecto != "Todos": sql += " AND c.nproyecto = ?"; params.append(proyecto)
        if condominio and condominio != "Todos": sql += " AND c.condominio = ?"; params.append(condominio)
        if query:
            sql += " AND (c.ncliente LIKE ? OR c.lote LIKE ? OR c.Reflote LIKE ?)"
            p = f"%{query}%"; params.extend([p, p, p])
        
        if sin_telefono:
            sql += " AND (c.ccelular IS NULL OR c.ccelular = '' OR c.ccelular = '0' OR c.ccelular = 'None') AND (c.cfijo IS NULL OR c.cfijo = '' OR c.cfijo = '0' OR c.cfijo = 'None')"
        
        # Filtros de columna específicos (mapeo avanzado)
        if col_filters:
            mapping = {
                "ncliente": "c.ncliente", "lote": "c.lote",
                "statusTerreno": "ca.statusTerreno", "nestatus": "ca.nestatus",
                "mesesadeudo": "ca.mesesadeudo", "anualidad": "ca.anualidad",
                "adeudo": "ca.adeudo", "adeudoM": "ca.adeudoM",
                "adeudo_otros": "ca.adeudo_otros", "totalAdeudo": "ca.totalAdeudo",
                "asesorNombre": "ca.asesorNombre", "ugestion": "ca.ugestion",
                "fultpago": "ca.fultpago", "nproyecto": "c.nproyecto", "condominio": "c.condominio"
            }
            # Columnas que deben usar LIKE en lugar de =
            text_cols = ["ncliente", "lote", "statusTerreno", "nestatus", "asesorNombre", "ugestion", "fultpago"]
            
            for col, val in col_filters.items():
                if not val: continue
                if col in mapping:
                    # Manejo de multi-select o coincidencia exacta
                    if isinstance(val, (list, tuple)) or (isinstance(val, str) and "," in val):
                        items = [v.strip() for v in val.split(",")] if isinstance(val, str) else val
                        if items:
                            placeholders = ",".join(["?"] * len(items))
                            sql += f" AND {mapping[col]} IN ({placeholders})"
                            params.extend(items)
                    else:
                        # Para texto usar LIKE, para números =
                        if col in text_cols:
                            sql += f" AND {mapping[col]} LIKE ?"
                            params.append(f"%{val}%")
                        else:
                            sql += f" AND {mapping[col]} = ?"
                            params.append(val)
        
        sql += f" ORDER BY c.lote ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(sql, params)
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally: conn.close()

def get_total_contactos(query=None, proyecto=None, condominio=None, col_filters=None, sin_telefono=False):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        sql = "SELECT COUNT(*) FROM contactos c LEFT JOIN cartera ca ON c.lote = ca.vivienda WHERE 1=1"
        params = []
        if proyecto and proyecto != "Todos": sql += " AND c.nproyecto = ?"; params.append(proyecto)
        if condominio and condominio != "Todos": sql += " AND c.condominio = ?"; params.append(condominio)
        if query:
            sql += " AND (c.ncliente LIKE ? OR c.lote LIKE ? OR c.Reflote LIKE ?)"
            p = f"%{query}%"; params.extend([p, p, p])
        
        if sin_telefono:
            sql += " AND (c.ccelular IS NULL OR c.ccelular = '' OR c.ccelular = '0' OR c.ccelular = 'None') AND (c.cfijo IS NULL OR c.cfijo = '' OR c.cfijo = '0' OR c.cfijo = 'None')"

        if col_filters:
            mapping = {
                "ncliente": "c.ncliente", "lote": "c.lote",
                "statusTerreno": "ca.statusTerreno", "nestatus": "ca.nestatus",
                "mesesadeudo": "ca.mesesadeudo", "anualidad": "ca.anualidad",
                "adeudo": "ca.adeudo", "adeudoM": "ca.adeudoM",
                "adeudo_otros": "ca.adeudo_otros", "totalAdeudo": "ca.totalAdeudo",
                "asesorNombre": "ca.asesorNombre", "ugestion": "ca.ugestion",
                "fultpago": "ca.fultpago", "nproyecto": "c.nproyecto", "condominio": "c.condominio"
            }
            text_cols = ["ncliente", "lote", "statusTerreno", "nestatus", "asesorNombre", "ugestion", "fultpago"]
            
            for col, val in col_filters.items():
                if not val: continue
                if col in mapping:
                    if isinstance(val, (list, tuple)) or (isinstance(val, str) and "," in val):
                        items = [v.strip() for v in val.split(",")] if isinstance(val, str) else val
                        if items:
                            placeholders = ",".join(["?"] * len(items))
                            sql += f" AND {mapping[col]} IN ({placeholders})"
                            params.extend(items)
                    else:
                        if col in text_cols:
                            sql += f" AND {mapping[col]} LIKE ?"
                            params.append(f"%{val}%")
                        else:
                            sql += f" AND {mapping[col]} = ?"
                            params.append(val)
        cursor.execute(sql, params)
        return cursor.fetchone()[0]
    finally: conn.close()

def update_contacto(id_local, fields):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            sets = ", ".join([f"{k} = ?" for k in fields.keys()])
            params = list(fields.values())
            params.append(id_local)
            cursor.execute(f"UPDATE contactos SET {sets} WHERE id = ?", params)
        return True
    except Exception as e:
        print(f"[DB] Error update_contacto: {e}")
        return False
    finally: conn.close()

def delete_contacto(id_local):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contactos WHERE id = ?", (id_local,))
        return True
    except Exception as e:
        print(f"[DB] Error delete_contacto: {e}")
        return False
    finally: conn.close()

def save_cartera(clientes_list):
    import sync_logger
    conn = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        cursor = conn.cursor()
        
        sync_logger.log_start("Cartera (Financiero)")
        
        # Iniciar transacción
        cursor.execute("BEGIN TRANSACTION")
        
        upsert_sql = """
            INSERT INTO cartera (
                vivienda, id_cobranza, mesesadeudo, clienteNombre, nestatus, anualidad, 
                adeudo_otros, totalAdeudo, totalAdeudoLL, ugestion, fultpago, 
                fechaFondoReserva, fecha1erMensMtto, statusTerreno, adeudo, adeudoM, 
                asesorNombre, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now", "localtime"))
            ON CONFLICT(vivienda) DO UPDATE SET
                id_cobranza=excluded.id_cobranza, mesesadeudo=excluded.mesesadeudo,
                clienteNombre=excluded.clienteNombre, nestatus=excluded.nestatus,
                anualidad=excluded.anualidad, adeudo_otros=excluded.adeudo_otros,
                totalAdeudo=excluded.totalAdeudo, totalAdeudoLL=excluded.totalAdeudoLL,
                ugestion=excluded.ugestion, fultpago=excluded.fultpago,
                fechaFondoReserva=excluded.fechaFondoReserva, fecha1erMensMtto=excluded.fecha1erMensMtto,
                statusTerreno=excluded.statusTerreno, adeudo=excluded.adeudo,
                adeudoM=excluded.adeudoM, asesorNombre=excluded.asesorNombre, 
                updated_at=datetime("now", "localtime")
        """
        
        # Procesar en lotes de 1000
        batch_size = 1000
        for i in range(0, len(clientes_list), batch_size):
            chunk = clientes_list[i : i + batch_size]
            data =[]
            for c in chunk:
                vivienda_norm = str(c.get("vivienda", "")).strip()
                data.append((
                    vivienda_norm, str(c.get("id_cobranza", "")), str(c.get("mesesadeudo", "")), 
                    str(c.get("clienteNombre", "")), str(c.get("nestatus", "")),
                    normalize_numeric(c.get("anualidad")), normalize_numeric(c.get("adeudo_otros")),
                    normalize_numeric(c.get("totalAdeudo")), normalize_numeric(c.get("totalAdeudoLL")),
                    str(c.get("ugestion", "")), str(c.get("fultpago", "")),
                    str(c.get("fechaFondoReserva", "")), str(c.get("fecha1erMensMtto", "")),
                    str(c.get("statusTerreno", "")), normalize_numeric(c.get("adeudo")),
                    normalize_numeric(c.get("adeudoM")), str(c.get("asesorNombre", ""))
                ))
            cursor.executemany(upsert_sql, data)
            # Commit intermedio para liberar memoria y locks
            conn.commit()
            cursor.execute("BEGIN TRANSACTION")
        
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                       ("cartera_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        sync_logger.log_end("Cartera (Financiero)", len(clientes_list))
        
    except Exception as e:
        conn.rollback()
        print(f"[Local DB] Error save_cartera: {e}")
        raise e
    finally:
        conn.close()

def cartera_needs_refresh():
    """Retorna True si la cartera nunca se ha descargado o si la última sync fue de un día anterior."""
    try:
        from datetime import datetime
        last_sync = get_config("cartera_last_sync")
        
        # Si no hay registro previo de sincronización
        if not last_sync:
            return True
            
        # Comparamos la fecha guardada (A-M-D) contra la fecha de hoy
        last_date = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S").date()
        today_date = datetime.now().date()
        
        # Si la última descarga fue antes de hoy (ayer, antier, etc.)
        if last_date < today_date:
            return True
            
        return False # Si es el mismo día, no necesita refresco forzoso
        
    except Exception as e:
        print(f"[DB] Error verificando refresh de cartera: {e}")
        return True # Por seguridad, si falla el cálculo, obligamos a actualizar

def get_cartera():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT vivienda, id_cobranza, mesesadeudo, clienteNombre FROM cartera ORDER BY vivienda ASC")
        return [{"vivienda": r[0], "id_cobranza": r[1], "mesesadeudo": r[2], "clienteNombre": r[3]} for r in cursor.fetchall()]
    except Exception as e:
        print(f"[Local DB] Error get_cartera: {e}")
        return []
    finally: conn.close()

def get_catalogos():
    import json
    val = get_config("catalogos_json")
    if val:
        try:
            return json.loads(val)
        except Exception as e:
            print(f"[Local DB] Error parseando catálogos: {e}")
    return {}

import json
from urllib import request as urllib_req, parse as urllib_parse

SUPABASE_URL = "https://tpwbwnonpfipfmoattgh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwd2J3bm9ucGZpcGZtb2F0dGdoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzA4NDcsImV4cCI6MjA5MDA0Njg0N30.NeyAJOq6vpxKbx-U9BJvGilF8uDt-wkwNX0ciySa8QA"

CURRENT_USER = None
CURRENT_USER_ID = None
CURRENT_USER_ROLE = "Usuario"

def verify_login(username, password):
    """
    Validación EXCLUSIVA contra Supabase.
    NUEVA VERSIÓN: Cierra la ventana de doble sesión a 45s y actualiza la BD de forma síncrona.
    """
    global CURRENT_USER, CURRENT_USER_ID, CURRENT_USER_ROLE
    print(f"[Supabase Auth] Intentando validar usuario: {username}...")
    
    try:
        query = urllib_parse.urlencode({
            'username': f'eq.{username}',
            'password': f'eq.{password}',
            'select': 'id,phone_ip,role,is_locked,last_seen'
        })
        
        url = f"{SUPABASE_URL}/rest/v1/usuarios?{query}"
        req = urllib_req.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        
        with urllib_req.urlopen(req, timeout=5) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                if len(data) > 0:
                    user = data[0]
                    
                    # 1. Validación de Bloqueo Administrativo
                    if user.get('is_locked') == True:
                        print(f"[Auth] ACCESO DENEGADO: El usuario {username} está bloqueado por un Administrador.")
                        return "BLOCKED"
                        
                    # 2. Validación de Sesión Única (Ventana reducida a 45 Segundos)
                    ls_raw = user.get("last_seen")
                    if ls_raw:
                        try:
                            from datetime import timezone, datetime
                            dt_last_seen = datetime.fromisoformat(ls_raw.replace("Z", "+00:00"))
                            now_utc = datetime.now(timezone.utc)
                            diff_seconds = (now_utc - dt_last_seen).total_seconds()
                            
                            # Si su último latido fue hace menos de 45 segundos, alguien más lo está usando.
                            if diff_seconds < 45:
                                print(f"[Auth] ACCESO DENEGADO: El usuario {username} ya tiene una sesión activa.")
                                return "ALREADY_LOGGED_IN"
                        except: pass

                    user_id = user['id']
                    db_phone_ip = user.get('phone_ip')
                    role = user.get('role', 'Usuario')
                    
                    if role not in ['Administrador', 'Usuario']:
                        role = 'Usuario'
                    
                    CURRENT_USER = username
                    CURRENT_USER_ID = user_id
                    CURRENT_USER_ROLE = role
                    
                    if db_phone_ip:
                        set_config("phone_ip", db_phone_ip)
                    
                    clear_session()
                    persist_session(username, password, CURRENT_USER_ROLE)
                    
                    # 3. ACTUALIZACIÓN SÍNCRONA (Para que aparezca online de inmediato y limpie el contador)
                    try:
                        update_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{user_id}"
                        now_str = datetime.now(timezone.utc).isoformat()
                        update_data = json.dumps({
                            "last_login": now_str,
                            "last_seen": now_str,
                            "force_logout": False # Quita el estado de expulsado
                        }).encode('utf-8')
                        
                        update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', headers={
                            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"
                        })
                        urllib_req.urlopen(update_req, timeout=3)
                    except Exception as e:
                        print(f"[Auth Warning] Error actualizando BD de login: {e}")
                    
                    return True
        
        print("[Auth] Usuario o contraseña incorrectos")
        return False

    except Exception as e:
        print(f"[Supabase Auth] Error en verify_login: {e}")
        return False

def change_password(old_pwd, new_pwd):
    """
    Cambia la contraseña del usuario actualmente logueado.
    Valida la contraseña actual primero contra Supabase.
    """
    if not CURRENT_USER_ID:
        return False, "No hay usuario activo."
        
    try:
        # Verificar contraseña actual
        query = urllib_parse.urlencode({
            'id': f'eq.{CURRENT_USER_ID}',
            'password': f'eq.{old_pwd}',
            'select': 'id'
        })
        url = f"{SUPABASE_URL}/rest/v1/usuarios?{query}"
        req = urllib_req.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        with urllib_req.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            if len(data) == 0:
                return False, "La contraseña actual es incorrecta."
                
        # Actualizar contraseña
        update_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}"
        update_data = json.dumps({"password": new_pwd}).encode('utf-8')
        update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        urllib_req.urlopen(update_req, timeout=5)
        
        # Actualizar sesión persistida local si existe
        if CURRENT_USER:
            persist_session(CURRENT_USER, new_pwd, CURRENT_USER_ROLE)
            
        return True, "Contraseña actualizada exitosamente."
    except Exception as e:
        print(f"[Supabase Auth] Error cambiando contraseña: {e}")
        return False, f"Error de conexión: {e}"

def admin_reset_password(target_username, new_pwd):
    """
    Restablece la contraseña de cualquier usuario (solo Admin).
    También activa force_logout para expulsar al usuario activo.
    """
    if CURRENT_USER_ROLE != 'Administrador':
        return False, "Permiso denegado."
        
    try:
        update_url = f"{SUPABASE_URL}/rest/v1/usuarios?username=eq.{target_username}"
        update_data = json.dumps({
            "password": new_pwd,
            "force_logout": True
        }).encode('utf-8')
        
        update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        urllib_req.urlopen(update_req, timeout=5)
        return True, f"Contraseña de {target_username} actualizada. El usuario será expulsado."
    except Exception as e:
        print(f"[Supabase Auth] Error reseteando contraseña de admin: {e}")
        return False, f"Error de conexión: {e}"

import base64
def persist_session(username, password, role):
    try:
        raw_str = f"{username}|{password}|{role}"
        encoded = base64.b64encode(raw_str.encode('utf-8')).decode('utf-8')
        set_config("session_token", encoded)
    except: pass

def get_persisted_session():
    """Retorna (username, password, role) si existe sesión guardada."""
    try:
        token = get_config("session_token")
        if not token: return None
        decoded = base64.b64decode(token.encode('utf-8')).decode('utf-8')
        parts = decoded.split('|')
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
    except: pass
    return None

def clear_session():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config WHERE key='session_token'")
    finally: conn.close()

def get_all_calls():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone_number, start_time, duration_sec, file_path FROM calls ORDER BY id DESC")
        return cursor.fetchall()
    finally: conn.close()

def get_config(key):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally: conn.close()

def get_system_metrics():
    """Calcula métricas de rendimiento y salud del sistema (Hardening v2)"""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    metrics = {
        "calls_ok": 0, "calls_err": 0, "api_err": 0, "audio_err": 0, "uptime": "0h 0m"
    }
    try:
        cursor = conn.cursor()
        # Llamadas
        cursor.execute("SELECT COUNT(*) FROM telemetry_log WHERE category='CALL' AND status='OK'")
        metrics["calls_ok"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM telemetry_log WHERE category='CALL' AND status='ERROR'")
        metrics["calls_err"] = cursor.fetchone()[0]
        # Errores API y Audio
        cursor.execute("SELECT COUNT(*) FROM telemetry_log WHERE category='API' AND status='ERROR'")
        metrics["api_err"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM telemetry_log WHERE category='AUDIO' AND status='ERROR'")
        metrics["audio_err"] = cursor.fetchone()[0]
        
        # Uptime
        diff = datetime.now() - AppState.uptime_start
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        metrics["uptime"] = f"{hours}h {minutes}m"
        
    except: pass
    finally: conn.close()
    return metrics

def set_config(key, value):
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    finally: conn.close()
    
    # Sincronizar hacia Supabase si es la configuración del teléfono
    if key == "phone_ip" and CURRENT_USER_ID:
        try:
            update_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}"
            update_data = json.dumps({"phone_ip": value}).encode('utf-8')
            update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            })
            # Ejecutar de fondo sin bloquear (con un timeout muy corto para no colgar la UI)
            import threading
            def bg_push():
                try: urllib_req.urlopen(update_req, timeout=3)
                except: pass
            threading.Thread(target=bg_push, daemon=True).start()
        except Exception:
            pass

def save_sisco_profile(google_id, image_url, email, name, given_name, family_name):
    if not CURRENT_USER_ID:
        return
    try:
        # Check if record already exists for this user
        get_url = f"{SUPABASE_URL}/rest/v1/sisco_data?user_id=eq.{CURRENT_USER_ID}&select=id"
        get_req = urllib_req.Request(get_url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        
        with urllib_req.urlopen(get_req, timeout=5) as get_res:
            data = json.loads(get_res.read().decode('utf-8'))
            
        payload = {
            "user_id": str(CURRENT_USER_ID),
            "google_id": google_id,
            "image_url": image_url,
            "email": email,
            "name": name,
            "given_name": given_name,
            "family_name": family_name,
            "updated_at": datetime.now().isoformat()
        }
        
        if len(data) > 0:
            # Update (PATCH)
            update_url = f"{SUPABASE_URL}/rest/v1/sisco_data?user_id=eq.{CURRENT_USER_ID}"
            req = urllib_req.Request(update_url, data=json.dumps(payload).encode('utf-8'), method='PATCH', headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            })
        else:
            # Insert (POST)
            insert_url = f"{SUPABASE_URL}/rest/v1/sisco_data"
            req = urllib_req.Request(insert_url, data=json.dumps(payload).encode('utf-8'), method='POST', headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            })
            
        with urllib_req.urlopen(req, timeout=5) as res:
            pass
            
    except Exception as e:
        print("[Supabase] Error subiendo Sisco Profile:", e)

def has_sisco_profile():
    """
    Check if the current user already has Sisco data in the database.
    """
    if not CURRENT_USER_ID:
        return False
        
    try:
        url = f"{SUPABASE_URL}/rest/v1/sisco_data?user_id=eq.{CURRENT_USER_ID}&select=id"
        req = urllib_req.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        
        with urllib_req.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode('utf-8'))
            return len(data) > 0
    except Exception as e:
        print("[Supabase] Error consultando estado de Sisco Profile:", e)
        return False

# ----- VARIABLES GLOBALES PARA CACHÉ LOGICO LIGERO -----
_global_settings_cache = {}
_global_settings_last_fetch = 0

def get_global_setting(key, fallback):
    """
    Lee parametros globales compartidos de forma general en la base de datos supabase (global_settings).
    Usa un cache de 5 minutos (300s) para no ahogar a Supabase con peticiones.
    """
    global _global_settings_cache, _global_settings_last_fetch
    import time
    
    # Refresh cache si tiene mas de 5 min
    if time.time() - _global_settings_last_fetch > 300 or not _global_settings_cache:
        try:
            url = f"{SUPABASE_URL}/rest/v1/global_settings?select=*"
            req = urllib_req.Request(url, headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            })
            
            with urllib_req.urlopen(req, timeout=12) as res:
                data = json.loads(res.read().decode('utf-8'))
                if len(data) > 0:
                    _global_settings_cache = data[0]
                    _global_settings_last_fetch = time.time()
        except Exception as e:
            print(f"[Supabase] Error refrescando global_settings: {e}")
            
    val = _global_settings_cache.get(key)
    return val if val is not None else fallback

def get_comentarios_predeterminados():
    """Obtiene la lista de comentarios predeterminados desde Supabase."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/comentarios_predeterminados?select=comentario&order=comentario.asc"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        req = urllib_req.Request(url, headers=headers, method="GET")
        with urllib_req.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode('utf-8'))
            return [item['comentario'] for item in data]
    except Exception as e:
        print(f"[Supabase Comments Error] {e}")
    return ["Buzon de voz", "Llamada finalizada", "No contesto"]

def get_sisco_profile():
    if not CURRENT_USER_ID:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/sisco_data?user_id=eq.{CURRENT_USER_ID}&select=*"
        req = urllib_req.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        })
        with urllib_req.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode('utf-8'))
            if len(data) > 0:
                return data[0]
            return None
    except Exception as e:
        print("[Supabase] Error descargando perfil SISCO:", e)
        return None

# --- AQUÍ EMPIEZA LO QUE VAS A PEGAR NUEVO ---

def ping_heartbeat():
    if not CURRENT_USER_ID: 
        return False
    
    try:
        # 1. Revisar si hay orden de expulsión/bloqueo
        url_get = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}&select=force_logout,is_locked"
        req_get = urllib_req.Request(url_get, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        
        with urllib_req.urlopen(req_get, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            
            if data and len(data) > 0:
                if data[0].get('is_locked') == True:
                    return "BLOCKED"
                
                if data[0].get('force_logout') == True:
                    # Resetear force_logout
                    reset_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}"
                    reset_data = json.dumps({"force_logout": False}).encode('utf-8')
                    reset_req = urllib_req.Request(reset_url, data=reset_data, method='PATCH', 
                                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"})
                    try: 
                        urllib_req.urlopen(reset_req, timeout=3)
                    except: pass
                    return True  # Fui expulsado
        
        # 2. Actualizar last_seen
        update_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}"
        update_data = json.dumps({"last_seen": datetime.now(timezone.utc).isoformat()}).encode('utf-8')
        update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', 
                                       headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"})
        urllib_req.urlopen(update_req, timeout=3)
        
    except Exception as e:
        print(f"[Heartbeat] Error silencioso: {e}")
    
    return False

def get_all_users_status():
    """Descarga la lista de usuarios para el Panel de Administrador."""
    try:
        # AÑADIDO: 'last_login' para calcular el tiempo conectado
        url = f"{SUPABASE_URL}/rest/v1/usuarios?select=id,username,role,last_seen,last_login,phone_ip,force_logout,is_locked&order=role.asc,username.asc"
        req = urllib_req.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        
        with urllib_req.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode('utf-8'))
    except Exception as e:
        print(f"[Supabase] Error obteniendo usuarios: {e}")
        return []

def set_user_lock(user_id=None, lock_state=True, kick_only=False):
    
    """
    Activa o desactiva el switch de expulsión y/o bloqueo.
    
    Args:
        user_id: ID del usuario a afectar (None = todos menos el actual)
        lock_state: True para bloquear, False para desbloquear
        kick_only: True solo para expulsar (sin bloquear)
    """
    try:
        if kick_only:
            # Solo expulsar (force_logout = true)
            payload = {"force_logout": True}
        else:
            # Bloquear/Desbloquear
            payload = {"is_locked": lock_state}
            # Si está bloqueando, también expulsar si está conectado
            if lock_state:
                payload["force_logout"] = True
        
        if user_id:
            url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{user_id}"
        else:  # Acción global
            url = f"{SUPABASE_URL}/rest/v1/usuarios?id=neq.{CURRENT_USER_ID}"
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib_req.Request(url, data=data, method='PATCH', 
                                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"})
        urllib_req.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print(f"[Supabase] Error en set_user_lock: {e}")
        return False

def set_offline_instant():
    """Fuerza el estado offline inmediato en Supabase al cerrar sesión"""
    if not CURRENT_USER_ID: return
    try:
        from datetime import timedelta, timezone, datetime
        import json
        from urllib import request as urllib_req
        
        past_time = datetime.now(timezone.utc) - timedelta(minutes=4)
        # Aseguramos el formato ISO compatible con Postgres
        time_str = past_time.isoformat()
        
        update_url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{CURRENT_USER_ID}"
        update_data = json.dumps({"last_seen": time_str}).encode('utf-8')
        
        update_req = urllib_req.Request(update_url, data=update_data, method='PATCH', headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"})
        urllib_req.urlopen(update_req, timeout=3)
    except Exception as e: 
        print(f"[Offline Error] {e}")

def clear_kick_status(user_id):
    """Le quita la placa de EXPULSADO a un usuario manualmente"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/usuarios?id=eq.{user_id}"
        data = json.dumps({"force_logout": False}).encode('utf-8')
        req = urllib_req.Request(url, data=data, method='PATCH', headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"})
        urllib_req.urlopen(req, timeout=5)
        return True
    except: return False

def is_enlace_movil_visible():
    """
    Verifica si la app "Enlace Móvil" está corriendo y visible.
    Versión Blindada: Revisa procesos, sub-procesos de UI (ApplicationFrameHost)
    y ventanas nativas del sistema.
    """
    import subprocess
    import ctypes
    
    try:
        # 1. Verificación rápida de proceso base
        out = subprocess.check_output('tasklist /FI "IMAGENAME eq PhoneExperienceHost.exe"', shell=True).decode('cp850', errors='ignore')
        out_old = subprocess.check_output('tasklist /FI "IMAGENAME eq YourPhone.exe"', shell=True).decode('cp850', errors='ignore')
        
        if "PhoneExperienceHost.exe" not in out and "YourPhone.exe" not in out_old:
            return False # Definitivamente está cerrado

        # 2. Verificación de UI visible mediante ctypes (user32)
        user32 = ctypes.windll.user32
        titulos_posibles =["Enlace Móvil", "Phone Link", "Tu Teléfono", "Your Phone"]
        
        ventana_encontrada = False
        
        def enum_windows_proc(hwnd, lParam):
            nonlocal ventana_encontrada
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    titulo_actual = buff.value
                    if any(t in titulo_actual for t in titulos_posibles):
                        ventana_encontrada = True
            return True

        # Convertimos la función de Python a C y escaneamos TODAS las ventanas de la pantalla
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        
        return ventana_encontrada
        
    except Exception as e:
        print(f"[Enlace Móvil Check] Error inesperado: {e}")
        return False