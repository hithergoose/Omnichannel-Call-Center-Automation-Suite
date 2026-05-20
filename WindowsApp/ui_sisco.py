import customtkinter as ctk
import threading
import json
import os
from tkinter import messagebox
import database_core

class SiscoFrame(ctk.CTkFrame):
    def __init__(self, master, on_auth_success=None):
        super().__init__(master, fg_color="transparent")
        self.pack(expand=True, fill="both")
        self.on_auth_success = on_auth_success
        
        self.title_lbl = ctk.CTkLabel(self, text="Conexión SISCO", font=ctk.CTkFont(size=28, weight="bold"), text_color="#011536")
        self.title_lbl.pack(pady=40)
        
        info_text = (
            "Esto abrirá la página oficial de clientes.gphsis.com.\n"
            "Todo lo que tienes que hacer es iniciar sesión con Google con normalidad.\n\n"
            "La interfaz identificará automáticamente tus datos de perfil\n"
            "y los sincronizará de forma segura hacia la Nube (Supabase) del sistema."
        )
        self.desc_lbl = ctk.CTkLabel(self, text=info_text, font=ctk.CTkFont(size=16), text_color="#333333", justify="center")
        self.desc_lbl.pack(pady=10)
        
        self.banner_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.banner_lbl.pack(pady=15)
        
        self.btn_iniciar = ctk.CTkButton(self, text="Abrir Sistema e Interceptar Datos", 
                                        fg_color="#4285F4", hover_color="#3367d6", text_color="white", 
                                        command=self.iniciar_proceso, height=55, width=320, 
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_iniciar.pack(pady=30)
        
        self.status_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_lbl.pack(pady=10)

        # Iniciar verificación de estado en segundo plano
        self.banner_lbl.configure(text="Comprobando estado en la Nube...", text_color="gray")
        threading.Thread(target=self.check_status, daemon=True).start()

    def check_status(self):
        has_profile = database_core.has_sisco_profile()
        self.after(0, lambda: self.update_status_ui(has_profile))

    def update_status_ui(self, has_profile):
        if not self.winfo_exists(): return # BLINDAJE: Si ya cambiaron de pestaña, no hacer nada
        
        if has_profile:
            self.banner_lbl.configure(text="✅ Tus datos ya están sincronizados y asegurados.", text_color="green")
            self.btn_iniciar.configure(text="Volver a Interceptar (Actualizar Datos)")
        else:
            self.banner_lbl.configure(text="⚠️ Aún no has enlazado tu perfil. Intercepta tus datos ahora.", text_color="#E67E22")

    def iniciar_proceso(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            messagebox.showerror("Error de Dependencia", "Falta la librería playwright. Ejecuta en consola:\npip install playwright\nplaywright install chromium")
            return

        self.btn_iniciar.configure(state="disabled", text="Navegador abierto... Esperando Login")
        self.status_lbl.configure(text="Toma acción en el Navegador de Google Chrome...", text_color="#f39c12")
        
        hilo = threading.Thread(target=self.run_playwright_capture)
        hilo.daemon = True
        hilo.start()

    def run_playwright_capture(self):
        try:
            from playwright.sync_api import sync_playwright
            perfil_path = os.path.join(os.getcwd(), "sesion_guardada")
            
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=perfil_path,
                    headless=False,
                    channel="chrome"
                )
                
                page = context.pages[0] if len(context.pages) > 0 else context.new_page()
                datos_capturados = False
                
                def interceptar_red(request):
                    nonlocal datos_capturados
                    if "verificar_gmail" in request.url and request.method == "POST":
                        try:
                            # Playwright puede lanzar Exception si post_data_json falla (e.g. body not json)
                            data = request.post_data_json
                            if data and "googleId" in str(data):
                                self.save_data_to_db(data)
                                datos_capturados = True
                        except Exception:
                            pass

                page.on("request", interceptar_red)
                page.goto("https://clientes.gphsis.com/")
                
                while not datos_capturados:
                    try:
                        page.wait_for_timeout(500)
                    except Exception:
                        break
                
                if datos_capturados:
                    page.wait_for_timeout(2000)
                    context.close()
                    self.after(0, self.on_success)
                else:
                    self.after(0, self.on_failure)

        except Exception as e:
            self.after(0, lambda ex=e: self.on_error(ex))

    def save_data_to_db(self, payload):
        try:
            user_data = payload.get("data", {})
            google_id = user_data.get("googleId", "")
            image_url = user_data.get("imageUrl", "")
            email = user_data.get("email", "")
            name = user_data.get("name", "")
            given_name = user_data.get("givenName", "")
            family_name = user_data.get("familyName", "")
            token = user_data.get("token", "")
            
            if token:
                database_core.set_config("sisco_token", token)
            
            database_core.save_sisco_profile(google_id, image_url, email, name, given_name, family_name)
            
            if token:
                threading.Thread(target=self.hidratar_cartera, args=(token,), daemon=True).start()
        except Exception as e:
            print("[Sisco] Error procesando payload JSON: ", e)

    def hidratar_cartera(self, token):
        try:
            import urllib.request
            self.after(0, lambda: self.status_lbl.configure(text="Sincronizando Cartera local...", text_color="orange"))
            url = "https://api-cobranza.gphsis.com/index.php/Clientes/initCarteraClientes"
            import json as json_lib
            payload_data = json_lib.dumps({"lotes": False, "get_ctes": True}).encode('utf-8')
            req = urllib.request.Request(url, data=payload_data, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as res:
                if res.getcode() == 200:
                    respuesta = json_lib.loads(res.read().decode('utf-8'))
                    
                    database_core.set_config("catalogos_json", json_lib.dumps(respuesta))
                    
                    clientes = respuesta.get('cart_clientes', [])
                    if not clientes and isinstance(respuesta, list):
                        clientes = respuesta
                    if clientes:
                        database_core.save_cartera(clientes)
                        self.after(0, lambda: self.status_lbl.configure(text=f"✅ Cartera sincronizada ({len(clientes)} lotes).", text_color="green"))
        except Exception as e:
            print(f"Error en hilo: {e}")
            self.after(0, lambda: self.status_lbl.configure(text="⚠️ Error hidratando cartera local.", text_color="orange"))

    def on_success(self):
        self.status_lbl.configure(text="✅ Datos de perfil obtenidos y vinculados", text_color="green")
        self.btn_iniciar.configure(state="normal", text="Abrir Sistema e Interceptar Datos")
        messagebox.showinfo("Operación Exitosa", "¡Tus datos SISCO fueron obtenidos y guardados en la Nube con éxito!")
        if self.on_auth_success:
            self.on_auth_success()

    def on_failure(self):
        self.status_lbl.configure(text="⚠️ Operación cancelada", text_color="#e74c3c")
        self.btn_iniciar.configure(state="normal", text="Abrir Sistema e Interceptar Datos")
        messagebox.showwarning("Atención", "Se cerró el navegador manual sin haber completado el Login en Sistema.")

    def on_error(self, e):
        self.status_lbl.configure(text="❌ Error en la conexión Chromium", text_color="red")
        self.btn_iniciar.configure(state="normal", text="Abrir Sistema e Interceptar Datos")
        messagebox.showerror("Error en navegador", f"Ocurrió un error:\n{e}")
