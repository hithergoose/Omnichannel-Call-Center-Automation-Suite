import customtkinter as ctk
import database_core
import threading
import os
import sys
from PIL import Image, ImageDraw

def obtener_ruta_recurso(rel_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, rel_path)

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, fg_color="#011536")
        self.on_login_success = on_login_success
        self.pack(expand=True, fill="both")
        
        self.card = ctk.CTkFrame(self, fg_color="white", corner_radius=20)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        
        self.inner_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.inner_frame.pack(padx=50, pady=50)

        # --- LOGO REDONDEADO (Pantalla de Login) ---
        logo_path = obtener_ruta_recurso("logo_gph.png")
        try:
            if os.path.exists(logo_path):
                img = Image.open(logo_path).convert("RGBA")
                # Creamos una máscara redonda
                mask = Image.new("L", img.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=80, fill=255)
                # Aplicamos la máscara para recortar los bordes
                img.putalpha(mask)
                
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(110, 110))
                self.logo_label = ctk.CTkLabel(self.inner_frame, text="", image=self.logo_image)
                self.logo_label.pack(pady=(0, 10))
        except Exception as e:
            print(f"[Login] Error cargando logo: {e}")
        # ---------------------------------------------
        
        self.title_lbl = ctk.CTkLabel(self.inner_frame, text="Central Telefónica GPH", 
                                       font=ctk.CTkFont(size=26, weight="bold"), 
                                       text_color="#011536")
        self.title_lbl.pack(pady=(0, 30))
        
        self.user_entry = ctk.CTkEntry(self.inner_frame, placeholder_text="Usuario", 
                                        width=300, height=50, font=ctk.CTkFont(size=16), 
                                        text_color="#000000")
        self.user_entry.pack(pady=10)
        
        self.pass_entry = ctk.CTkEntry(self.inner_frame, placeholder_text="Contraseña", 
                                        show="*", width=300, height=50, 
                                        font=ctk.CTkFont(size=16), text_color="#000000")
        self.pass_entry.pack(pady=10)
        
        self.error_lbl = ctk.CTkLabel(self.inner_frame, text="", text_color="red", 
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.error_lbl.pack(pady=5)
        
        self.login_btn = ctk.CTkButton(self.inner_frame, text="Ingresar al Sistema", 
                                        command=self.login, width=300, height=55, 
                                        fg_color="#2b64d3", hover_color="#1d4a99", 
                                        text_color="white", 
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.login_btn.pack(pady=(10, 0))

        self.pass_entry.bind("<Return>", lambda e: self.login())
        self.user_entry.bind("<Return>", lambda e: self.login())

    def login(self):
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get()

        if not user or not pwd:
            self.error_lbl.configure(text="Ingresa usuario y contraseña")
            return

        self.login_btn.configure(state="disabled", text="Validando...")
        self.error_lbl.configure(text="")

        def run_login():
            print("[LOGIN] Hilo iniciado — llamando verify_login...")
            resultado = database_core.verify_login(user, pwd)
            print(f"[LOGIN] verify_login retornó: {resultado}")
            self.after(0, lambda: self._on_result(resultado, user))

        threading.Thread(target=run_login, daemon=True).start()

    def _on_result(self, resultado, username):
        if resultado == True:
            database_core.log_telemetry("AUTH", f"Sesión iniciada correctamente para: {username}", "OK")
            self.on_login_success(username, database_core.CURRENT_USER_ROLE)
        elif resultado == "BLOCKED":
            self.login_btn.configure(state="normal", text="Ingresar al Sistema")
            self.error_lbl.configure(text="ACCESO DENEGADO. Tu cuenta está bloqueada.")
        elif resultado == "ALREADY_LOGGED_IN":
            self.login_btn.configure(state="normal", text="Ingresar al Sistema")
            self.error_lbl.configure(text="SESIÓN ACTIVA. Esta cuenta ya está en uso en otro equipo.")
        else:
            self.login_btn.configure(state="normal", text="Ingresar al Sistema")
            self.error_lbl.configure(text="Error de conexión o datos inválidos")
            print(f"[Login] Intento fallido para {username}.")
            database_core.log_telemetry("AUTH", f"Fallo de autenticación para: {username}", "ERROR")