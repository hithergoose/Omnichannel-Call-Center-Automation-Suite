import requests
import database_core
import threading
import os
import mimetypes

def _get_valid_token():
    """
    Obtiene un token fresco mediante el handshake /User/verificar_gmail
    usando el perfil de Google almacenado localmente con lógica de reintento.
    """
    import json
    import time
    profile = database_core.get_sisco_profile()
    if not profile: return None
    
    login_payload = {
        "data": {
            "googleId": profile.get("google_id"),
            "imageUrl": profile.get("image_url", ""),
            "email": profile.get("email"),
            "name": profile.get("name"),
            "givenName": profile.get("given_name", ""),
            "familyName": profile.get("family_name", "")
        }
    }
    url_login = "https://api-cobranza.gphsis.com/index.php/User/verificar_gmail"
    
    # Intentos de conexión robustos
    for attempt in range(3):
        try:
            res = requests.post(url_login, json=login_payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict) and data.get("status") == 1:
                    token = data.get("data", {}).get("token")
                    if token:
                        database_core.set_config("sisco_token", token)
                        return token
            elif res.status_code == 403:
                print(f"[API] ❌ 403 Forbidden en refresco de token. Payload: {login_payload['data']['email']}")
            
            time.sleep(2 * (attempt + 1)) # Backoff
        except Exception as e:
            print(f"[API] Intento {attempt+1} falló: {e}")
            if attempt == 2: break
            time.sleep(2)
            
    # Fallback al token local si falla el refresco
    return database_core.get_config("sisco_token")

def enviar_gestion(payload, file_paths, on_success=None, on_error=None):
    """
    Envía la gestión post-llamada al servidor GPH. (Versión Estable Original)
    """
    def task():
        try:
            print("[API GPH] Iniciando hilo para enviar gestión...")
            token = _get_valid_token()
            if not token:
                if on_error: on_error("No se encontró el Token SISCO.")
                return

            url = "https://api-cobranza.gphsis.com/index.php/Clientes/new_followUp"
            headers = {"authorization": token}

            archivos_abiertos = []
            files_to_send = []

            # Normalizar a lista simple
            if isinstance(file_paths, str):
                rutas = [file_paths] if file_paths else []
            else:
                rutas = file_paths or []

            try:
                for path in rutas:
                    if os.path.exists(path):
                        f = open(path, 'rb')
                        archivos_abiertos.append(f)
                        files_to_send.append(('evidencia[]', (os.path.basename(path), f, 'application/octet-stream')))

                if files_to_send:
                    response = requests.post(url, headers=headers, data=payload, files=files_to_send, timeout=60)
                else:
                    response = requests.post(url, headers=headers, data=payload, timeout=60)
                    
                res_obj = response.json()
                if isinstance(res_obj, dict) and str(res_obj.get("status")) in ["1", "-1"]:
                    if on_success: on_success(res_obj.get("mensaje", "Gestión guardada exitosamente."))
                else:
                    msg = res_obj.get("mensaje", f"Error de lógica de API (status {res_obj.get('status')})")
                    if on_error: on_error(msg)

            except ValueError:
                text_content = response.text.strip()
                if text_content == "200" or text_content == "1":
                    if on_success: on_success("Gestión registrada")
                else:
                    if on_error: on_error(f"Error {response.status_code} del servidor")
            finally:
                for f in archivos_abiertos:
                    f.close()
                    
        except Exception as e:
            err_msg = str(e)
            print(f"Error en hilo (api_gph): {err_msg}")
            import database_core
            database_core.log_telemetry("API", f"Error enviando gestión (Encolando): {err_msg}", "WARNING")
            
            import json
            enqueue_event("GESTION", payload, json.dumps(file_paths) if isinstance(file_paths, list) else file_paths)
            if on_error: on_error(f"Encolado para reintento: {err_msg}")

    threading.Thread(target=task, daemon=True).start()

def enqueue_event(event_type, payload, file_path=None):
    """Guarda un evento en la cola persistente para reintento (Hardening v2)"""
    import json
    conn = database_core.sqlite3.connect(database_core.DB_PATH, timeout=20)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_event_queue (event_type, payload, file_path, status)
                VALUES (?, ?, ?, 'PENDING')
            """, (event_type, json.dumps(payload), file_path))
            print(f"[API] Evento {event_type} encolado para reintento.")
    except Exception as e:
        print(f"[API] Error encolando evento: {e}")
    finally: conn.close()

def start_event_worker():
    """Inicia el hilo trabajador de la cola de eventos (Hardening v2)"""
    def worker():
        import time
        import json
        print("[API] Event Worker iniciado.")
        while True:
            try:
                # Buscar eventos pendientes
                conn = database_core.sqlite3.connect(database_core.DB_PATH, timeout=20)
                cursor = conn.cursor()
                cursor.execute("SELECT id, event_type, payload, file_path, attempts FROM api_event_queue WHERE status = 'PENDING' LIMIT 5")
                events = cursor.fetchall()
                conn.close()

                for ev_id, ev_type, ev_payload, ev_file, attempts in events:
                    if attempts >= 5:
                        # Marcar como fallido tras 5 intentos
                        conn = database_core.sqlite3.connect(database_core.DB_PATH, timeout=20)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE api_event_queue SET status = 'FAILED' WHERE id = ?", (ev_id,))
                        conn.commit()
                        conn.close()
                        database_core.log_telemetry("API", f"Evento {ev_id} falló tras 5 intentos", "ERROR")
                        continue

                    # Intentar procesar
                    success = False
                    payload = json.loads(ev_payload)
                    
                    if ev_type == "GESTION":
                        # Llamada síncrona interna para reintento
                        success = _enviar_gestion_sync(payload, ev_file)
                    
                    conn = database_core.sqlite3.connect(database_core.DB_PATH, timeout=20)
                    cursor = conn.cursor()
                    if success:
                        cursor.execute("DELETE FROM api_event_queue WHERE id = ?", (ev_id,))
                        database_core.log_telemetry("API", f"Evento {ev_id} reintentado exitosamente", "OK")
                    else:
                        cursor.execute("UPDATE api_event_queue SET attempts = attempts + 1 WHERE id = ?", (ev_id,))
                    conn.commit()
                    conn.close()

            except Exception as e:
                print(f"[API Worker] Error: {e}")
            
            time.sleep(30) # Procesar cada 30 segundos

    threading.Thread(target=worker, daemon=True).start()

def _enviar_gestion_sync(payload, file_path):
    """Versión básica síncrona para el worker."""
    try:
        token = _get_valid_token()
        if not token: return False
        url = "https://api-cobranza.gphsis.com/index.php/Clientes/new_followUp"
        headers = {"authorization": token}
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                files = {'evidencia[]': (os.path.basename(file_path), f, 'audio/mpeg')}
                res = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        else:
            res = requests.post(url, headers=headers, data=payload, timeout=30)
            
        return res.status_code in [200, 201]
    except: return False

def descargar_cartera_backend(on_success=None, on_error=None, on_auth_required=None, on_progress=None):

    def worker():
        import database_core, requests, json
        
        if on_progress: on_progress(0.1, "Iniciando descarga de Cartera...")
        
        token = _get_valid_token()
        if not token:
            if on_auth_required: on_auth_required()
            return

        # Reintentos para la cartera
        for intento in range(2): 
            try:
                if on_progress: on_progress(0.3, f"Conectando a servidor (Intento {intento+1})...")
                
                url = "https://api-cobranza.gphsis.com/index.php/Clientes/initCarteraClientes"
                res = requests.post(url, json={"lotes": False, "get_ctes": True}, 
                                    headers={"authorization": token}, timeout=60) # Timeout de 60s
                
                if res.status_code == 200:
                    data = res.json()
                    if on_progress: on_progress(0.6, "Procesando datos recibidos...")
                    
                    # Lógica de extracción
                    clientes = data.get('cart_clientes',[])
                    if not clientes and isinstance(data, list): clientes = data
                    
                    if clientes:
                        if on_progress: on_progress(0.8, f"Guardando {len(clientes)} registros...")
                        database_core.save_cartera(clientes)
                        if on_success: on_success()
                        return # Éxito total
                    else:
                        raise Exception("La API respondió pero la lista de clientes está vacía")
                else:
                    raise Exception(f"Error HTTP {res.status_code}")
                    
            except Exception as e:
                print(f"[SYNC ERROR] Cartera: {e}")
                if intento == 1: # Último intento fallido
                    if on_error: on_error(str(e))
                else:
                    if on_progress: on_progress(0.4, "Reintentando conexión...")
        
    threading.Thread(target=worker, daemon=True).start()

    
def sincronizar_contactos_posventa(on_progress=None, on_success=None, on_error=None):
    """
    Versión robusta: Descarga solo proyectos permitidos, notifica errores individuales
    en la UI y permite continuar aunque un proyecto falle.
    """
    def worker():
        import database_core
        import requests
        import sync_logger
        
        TIMEOUT_GLOBAL = 40 
        MAX_RETRIES = 2
        
        success = False
        contactos_exitosos =[]
        errores_proyectos =[]

        try:
            token = _get_valid_token()
            if not token:
                if on_error: on_error("No se detectó perfil SISCO vinculado.")
                return

            headers = {"authorization": token, "Content-Type": "application/json"}
            session = requests.Session()

            # 1. Obtener lista completa de proyectos
            if on_progress: on_progress(0.05, "Obteniendo lista de proyectos...")
            res_proy = session.get("https://api-cobranza.gphsis.com/index.php/Catalogo/PryoetosLotesGPH", headers=headers, timeout=TIMEOUT_GLOBAL)
            
            all_proyectos = res_proy.json().get("proyectos",[]) if res_proy.status_code == 200 else[]
            
            # --- FILTRADO INTELIGENTE (Solo proyectos configurados en BD) ---
            permitidos_raw = database_core.get_config("proyectos_permitidos")
            if permitidos_raw:
                lista_permitidos = [p.strip().upper() for p in permitidos_raw.split(",")]
                proyectos_a_descargar =[
                    p for p in all_proyectos 
                    if p.get("nproyecto", "").strip().upper() in lista_permitidos
                ]
            else:
                proyectos_a_descargar = all_proyectos
            
            total_proy = len(proyectos_a_descargar)
            if total_proy == 0:
                msg = "No se encontraron proyectos configurados para descargar."
                sync_logger.log_error("Contactos", msg)
                if on_progress: on_progress(1.0, msg)
                return

            # 2. Bucle robusto por proyecto filtrado
            for i, p in enumerate(proyectos_a_descargar):
                id_p = p.get("id_proy")
                siglas = p.get("siglas") or p.get("nproyecto", "Desconocido")
                
                # Actualizar progreso UI
                progreso = 0.1 + (i / total_proy) * 0.7
                if on_progress: on_progress(progreso, f"Descargando {siglas} ({i+1}/{total_proy})...")

                # Reintento por proyecto
                for intento in range(MAX_RETRIES):
                    try:
                        payload = {"id_proy": str(id_p), "idCondominio": 0, "empresa": None, "origen": "GPH"}
                        res_v = session.post("https://api-cobranza.gphsis.com/index.php/PosVenta/Contactos/", json=payload, headers=headers, timeout=TIMEOUT_GLOBAL)
                        
                        if res_v.status_code == 200:
                            data = res_v.json()
                            raw_data = data if isinstance(data, list) else (data.get("data") or data.get("contactos") or [])
                            for c in raw_data:
                                c["id_proy"] = id_p
                                contactos_exitosos.append(c)
                            break 
                        else:
                            raise Exception(f"HTTP {res_v.status_code}")
                            
                    except Exception as e:
                        if intento == MAX_RETRIES - 1:
                            msg_err = f"❌ FALLO DEFINITIVO en {siglas}: {str(e)}"
                            sync_logger.log_error("Contactos", msg_err)
                            errores_proyectos.append(msg_err)
                            if on_progress: on_progress(progreso, msg_err) # Notifica el error a la UI
                        continue 

            # 3. Guardado final en BD
            if contactos_exitosos:
                if on_progress: on_progress(0.9, f"Guardando {len(contactos_exitosos)} registros...")
                database_core.save_contactos(contactos_exitosos, on_progress=on_progress)
                sync_logger.log_sync(f"[SYNC] Finalizada. Éxitos: {len(contactos_exitosos)} | Errores: {len(errores_proyectos)}")
                success = True
            else:
                if on_error: on_error("No se pudieron obtener contactos de los proyectos.")

        except Exception as e:
            sync_logger.log_error("Contactos", f"Fallo general en sincronización: {e}")
            if on_error: on_error(str(e))
        finally:
            if success and on_success:
                on_success()

    threading.Thread(target=worker, daemon=True).start()