import os
import re

def patch_api_gph():
    path = r"C:\Proyectos\Llamadas GPH\WindowsApp\api_gph.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Patrón para descargar_cartera_backend
    new_descargar = '''def descargar_cartera_backend(on_success=None, on_error=None, on_auth_required=None):
    """
    Refactorizado v5.1: Patrón de worker determinista con finalmente notificador.
    """
    def worker():
        import database_core
        import requests
        import json
        
        success = False
        error_msg = None

        try:
            token = _get_valid_token()
            if not token:
                if on_auth_required: on_auth_required()
                return

            headers = {"Content-Type": "application/json", "Accept": "application/json", "authorization": token}
            session = requests.Session()
            
            url_cart = "https://api-cobranza.gphsis.com/index.php/Clientes/initCarteraClientes"
            cart_payload = {"lotes": False, "get_ctes": True}
            
            res_cart = session.post(url_cart, json=cart_payload, headers=headers, timeout=30)
            if res_cart.status_code == 200:
                respuesta = res_cart.json()
                database_core.set_config("catalogos_json", json.dumps(respuesta))
                
                llave_correcta = "cart_clientes"
                if llave_correcta in respuesta:
                    clientes = respuesta[llave_correcta]
                else:
                    clientes = []
                    for k in respuesta:
                        if isinstance(respuesta[k], list) and len(respuesta[k]) > len(clientes):
                            clientes = respuesta[k]
                            
                if not clientes and isinstance(respuesta, list):
                    clientes = respuesta
                    
                if clientes:
                    database_core.save_cartera(clientes)
                
                success = True
            else:
                error_msg = f"Falla Cartera Backend, HTTP: {res_cart.status_code}"
                
        except Exception as e:
            error_msg = str(e)
            print(f"[SYNC][ERROR] Cartera: {error_msg}")
        finally:
            print("[SYNC] Intentando notificar UI (Cartera)...")
            if success and on_success:
                on_success()
            elif not success and on_error:
                on_error(error_msg or "Error desconocido en Cartera")

    import threading
    threading.Thread(target=worker, daemon=True).start()'''

    # Patrón para sincronizar_contactos_posventa
    new_sincronizar = '''def sincronizar_contactos_posventa(on_progress=None, on_success=None, on_error=None):
    """
    Refactorizado v5.1: Patrón de worker determinista con finalmente notificador.
    """
    def worker():
        import database_core
        import requests
        import json
        import sync_logger
        
        success = False
        error_msg = None

        try:
            profile = database_core.get_sisco_profile()
            if not profile:
                error_msg = "No se detectó perfil SISCO vinculado."
                return
            
            token = database_core.get_config("sisco_token")
            headers = {"authorization": token, "Content-Type": "application/json"}
            session = requests.Session()

            if on_progress: on_progress(0.05, "Obteniendo lista de proyectos...")
            
            url_proy = "https://api-cobranza.gphsis.com/index.php/Catalogo/PryoetosLotesGPH"
            res_proy = session.get(url_proy, headers=headers, timeout=20)
            if res_proy.status_code != 200:
                error_msg = f"Error Proyectos: {res_proy.status_code}"
                return
            
            all_proyectos = res_proy.json().get("proyectos", [])
            permitidos_raw = database_core.get_config("proyectos_permitidos")
            permitidos = [p.strip().upper() for p in permitidos_raw.split(",")] if permitidos_raw else []
            
            filtro = [p for p in all_proyectos if p.get("nproyecto", "").strip().upper() in permitidos]
            if not filtro: filtro = all_proyectos
            
            todos_contactos = []
            url_postventa = "https://api-cobranza.gphsis.com/index.php/PosVenta/Contactos/"
            
            total_proy = len(filtro)
            for i, p in enumerate(filtro):
                id_p = p.get("id_proy")
                siglas = p.get("siglas") or p.get("nproyecto", "Desconocido")
                prog = 0.1 + (i / total_proy) * 0.8
                if on_progress: on_progress(prog, f"Descargando {siglas} ({i+1}/{total_proy})...")
                
                payload = {"id_proy": str(id_p), "idCondominio": 0, "empresa": None, "origen": "GPH"}
                try:
                    res_v = session.post(url_postventa, json=payload, headers=headers, timeout=40)
                    if res_v.status_code == 200:
                        data = res_v.json()
                        raw_data = data if isinstance(data, list) else data.get("data", []) or data.get("contactos", [])
                        for c in raw_data:
                            c["id_proy"] = id_p
                            todos_contactos.append(c)
                except Exception as ex:
                    print(f"Error descargando proyecto {siglas}: {ex}")

            import sync_logger
            sync_logger.log_sync(f"[SYNC] Descarga completada: {len(todos_contactos)} registros obtenidos.")
            if on_progress: on_progress(0.95, f"Guardando {len(todos_contactos)} registros...")
            
            if todos_contactos:
                database_core.save_contactos(todos_contactos, on_progress=on_progress)
                sync_logger.log_sync("[SYNC] Guardado completado.")
                success = True
            else:
                error_msg = "No se obtuvieron contactos."
                
        except Exception as e:
            error_msg = str(e)
            print(f"[SYNC][ERROR] Contactos: {error_msg}")
        finally:
            print("[SYNC] Intentando notificar UI (Contactos)...")
            if success and on_success:
                on_success()
            elif not success and on_error:
                on_error(error_msg or "Error desconocido en Contactos")

    import threading
    threading.Thread(target=worker, daemon=True).start()'''

    # Reemplazo agresivo de las funciones
    content = re.sub(r"def descargar_cartera_backend\(.*?\):.*?threading\.Thread\(target=.*?, daemon=True\)\.start\(\)", new_descargar, content, flags=re.DOTALL)
    content = re.sub(r"def sincronizar_contactos_posventa\(.*?\):.*?threading\.Thread\(target=.*?, daemon=True\)\.start\(\)", new_sincronizar, content, flags=re.DOTALL)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("api_gph.py patched.")

def patch_ui_dialer():
    path = r"C:\Proyectos\Llamadas GPH\WindowsApp\ui_dialer.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. SyncProgressDialog.on_sync_complete
    new_on_complete = '''    def on_sync_complete(self, success=True, error_msg=None):
        """Finaliza el diálogo con el estado correspondiente (éxito/error)."""
        print("[UI] on_sync_complete ejecutado")
        if success:
            self.progress.set(1.0)
            self.lbl_status.configure(text="✅ Datos actualizados", text_color="#10B981")
            self.done_btn.configure(state="normal")
            # Auto-cierre de 3 segundos (PUNTO FINAL REAL)
            self.after(3000, self.destroy)
        else:
            self.lbl_status.configure(text=f"❌ Error: {error_msg or 'Sincronización'}", text_color="#ef4444")
            self.done_btn.configure(state="normal")'''

    content = re.sub(r"    def on_sync_complete\(self, success=True, error_msg=None\):.*?self\.lbl_status\.configure\(text=f\"❌ Error: \{error_msg or 'Sincronización'\}\", text_color=\"#ef4444\"\)", new_on_complete, content, flags=re.DOTALL)

    # 2. _sync_cartera_ui
    new_sync_ui = '''    def _sync_cartera_ui(self):
        print("[UI] Registrando callbacks de sincronización")
        dialog = SyncProgressDialog(self.winfo_toplevel())
        dialog.grab_set()
        
        def on_progress(p, msg):
            self.after(0, lambda: dialog.update_progress(p, msg))
            
        def on_error(err):
            print(f"[SYNC] Intentando notificar UI de error: {err}")
            self.after(0, lambda: dialog.on_sync_complete(False, err))
            import sync_logger
            sync_logger.log_sync(f"[SYNC ERROR] UI notificada de error: {err}")
            
        def on_success_final():
            print("[SYNC] Intentando notificar UI (Fin de cadena)...")
            self.after(0, self.refresh_data)
            self.after(0, lambda: dialog.on_sync_complete(True))
            import sync_logger
            sync_logger.log_sync("[SYNC] UI notificada")

        def sync_wallet():
            print("[UI] Step 1 completado. Iniciando Step 2 (Cartera)...")
            self.after(0, lambda: dialog.update_progress(0.9, "Descargando datos financieros (Cartera)..."))
            import api_gph
            api_gph.descargar_cartera_backend(
                on_success=on_success_final,
                on_error=on_error
            )

        def run_sync():
            try:
                # Paso 1: Sincronizar Contactos (PosVenta)
                # Al terminar Step 1, NO se cierra, se dispara Step 2 (sync_wallet)
                import api_gph
                api_gph.sincronizar_contactos_posventa(
                    on_progress=on_progress,
                    on_success=sync_wallet,
                    on_error=on_error
                )
            except Exception as e:
                err_msg = str(e)
                import sync_logger
                sync_logger.log_sync(f"[SYNC CRITICAL] Fallo en run_sync: {err_msg}")
                on_error(err_msg)

        import threading
        threading.Thread(target=run_sync, daemon=True).start()'''

    content = re.sub(r"    def _sync_cartera_ui\(self\):.*?threading\.Thread\(target=run_sync, daemon=True\)\.start\(\)", new_sync_ui, content, flags=re.DOTALL)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("ui_dialer.py patched.")

if __name__ == "__main__":
    patch_api_gph()
    patch_ui_dialer()
