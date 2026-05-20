import os
import sys
# --- CONFIGURACIÓN DE PLAYWRIGHT LOCAL (Bundled) ---
def setup_playwright_env():
    try:
        import sys, os
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        browsers_path = os.path.join(base_path, "ms-playwright")
        if os.path.exists(browsers_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
    except Exception:
        pass

setup_playwright_env()

import customtkinter as ctk
import database_core
from ui_login import LoginFrame
from audio_mixer import AudioMixer
from ui_dialer import DialerFrame
from ui_recordings import RecordingsFrame
from ui_profile import ProfileFrame
from ui_sisco import SiscoFrame
from ui_stats import StatsFrame
from PIL import Image, ImageDraw, ImageTk
import api_gph
import threading
import time
import logging
import traceback

# --- NUEVO SISTEMA DE LOGS (CAJA NEGRA EN APPDATA) ---
log_dir = os.path.join(os.getenv('APPDATA'), 'CentralGPH')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'GPH_App.log'),
    level=logging.DEBUG, 
    format='%(asctime)s - [%(levelname)s] - %(module)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Esto atrapa los errores "fatales" que cierran la app y los guarda en el log
def log_excepciones_no_manejadas(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.excepthook(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Excepción no manejada (Crash):", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_excepciones_no_manejadas

logging.info("==================================================")
logging.info("INICIO DE SESIÓN DE LA APLICACIÓN GPH CALL CENTER")
logging.info("==================================================")

# ------------------------------------------

def obtener_ruta_recurso(rel_path):
    """Obtiene la ruta absoluta al recurso, funciona para dev y para PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, rel_path)

ctk.set_appearance_mode("Light")
GPH_BLUE = "#011536"
GPH_ACCENT = "#2b64d3"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.attributes("-alpha", 0.0)  # Vuelve la ventana invisible
        self.after(10, lambda: self.attributes("-alpha", 1.0))  # La vuelve visible muy rápido
        self._failure_counter = 0
        self._MAX_FAILURES = 3 
        print("[App] Iniciando componentes...")
        print("[App] Configurando base de datos...")
        try:
            database_core.init_db()
        except Exception as e:
            print(f"[App] ERROR CRÍTICO DB: {e}")
            
        print("[App] Configurando UI...")
        self.title("Central Telefónica GPH")
        
        # --- NUEVO: Icono de la ventana superior ---
        try:
            icon_path = obtener_ruta_recurso("favicon (7).ico")
            if os.path.exists(icon_path):
                img_icon = ImageTk.PhotoImage(file=icon_path)
                self.wm_iconbitmap() # Limpia el default
                self.iconphoto(False, img_icon)
        except Exception as e:
            print(f"[App] Error cargando icono superior: {e}")
        # -------------------------------------------

        # --- Lógica de Pantalla Adaptativa ---
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        if screen_width < 1400 or screen_height < 800:
            self.after(100, self.state, 'zoomed')
        else:
            self.geometry(f"{int(screen_width * 0.8)}x{int(screen_height * 0.8)}")
        # -----------------------------------------------
            
        print("[App] Iniciando AudioMixer...")
        self.mixer = AudioMixer()
        print("[App] AudioMixer listo")
        
        self.last_activity = time.time()
        self.current_frame = None
        self._heartbeat_running = False
        
        # Intentar restaurar sesión persistida (Validación estricta Punto 3)
        session = database_core.get_persisted_session()
        if session:
            user, pwd, role = session
            print(f"[App] Sesión persistida encontrada para {user}. Validando contra Supabase...")
            if database_core.verify_login(user, pwd):
                database_core.log_telemetry("AUTH", f"Sesión persistida restaurada para {user}", "OK")
                self.show_home(user, role)
            else:
                print("[App] Sesión inválida o expirada. Redirigiendo a login.")
                database_core.log_telemetry("AUTH", f"Sesión persistida fallida para {user}", "WARNING")
                database_core.clear_session()
                self.show_login()
        else:
            self.show_login()
        
        # Bind de actividad global (Punto 6)
        self.bind_all("<Any-KeyPress>", lambda e: self.update_last_activity())
        self.bind_all("<Any-Button>", lambda e: self.update_last_activity())
        
        print("[App] Sistema listo. Programando sincronización e inactividad...")
        self.after(3000, self._start_silent_sync)
        self.after(60000, self._check_inactivity)
        
        # Hardening v2: Iniciar Watchdog y Worker de Eventos
        api_gph.start_event_worker()
        threading.Thread(target=self._service_watchdog, daemon=True).start()
        self.after(300000, self._check_session_protection)  # Cada 5 minutos
        
        # Iniciar heartbeat loop continuamente
        self._heartbeat_running = True
        threading.Thread(target=self._heartbeat_loop_continuous, daemon=True).start()
        print("[App] Heartbeat loop iniciado")

    def _heartbeat_loop_continuous(self):
        """Loop continuo que ejecuta el heartbeat cada 20 segundos"""
        time.sleep(5) 
        
        while self._heartbeat_running:
            try:
                if database_core.CURRENT_USER_ID:
                    resultado = database_core.ping_heartbeat()
                    
                    if resultado == "BLOCKED":
                        self.after(0, lambda: self.logout(force_kick=True, reason="blocked"))
                        break
                    elif resultado:
                        self.after(0, lambda: self.logout(force_kick=True, reason="kicked"))
                        break
                    
                time.sleep(20)  
            except Exception as e:
                print(f"[Heartbeat Loop] Error: {e}")
                time.sleep(20)

    def show_login(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = LoginFrame(self, self.show_home)

    def show_home(self, username="Admin", role="Usuario"):
        print(f"[App] >> show_home START para: {username} ({role})")
        self.current_user_role = role
        if self.current_frame:
            self.current_frame.destroy()
        print("[App] >> frame anterior destruido")
        
        self.current_frame = ctk.CTkFrame(self)
        self.current_frame.pack(expand=True, fill="both")
        print("[App] >> frame principal creado")
        
        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self.current_frame, width=220, corner_radius=0, fg_color=GPH_BLUE)
        self.sidebar_frame.pack(side="left", fill="y")
        print("[App] >> sidebar creado")
        
        # --- LOGO REDONDEADO (Barra Lateral) ---
        logo_path = obtener_ruta_recurso("logo_gph.png")
        if os.path.exists(logo_path):
            print("[App] >> cargando logo...")
            try:
                img = Image.open(logo_path).convert("RGBA")
                # Creamos máscara redonda
                mask = Image.new("L", img.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=80, fill=255)
                img.putalpha(mask)
                
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="", image=self.logo_image)
            except Exception as e:
                print(f"[App] >> error cargando logo: {e}")
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Central GPH", font=ctk.CTkFont(size=24, weight="bold"), text_color="white")
        else:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Central GPH", font=ctk.CTkFont(size=24, weight="bold"), text_color="white")
        
        self.logo_label.pack(pady=30, padx=20)
        print("[App] >> logo empaquetado")
        
        self.btn_dialer = ctk.CTkButton(self.sidebar_frame, text="📞 Hacer Llamada", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=self.show_dialer)
        self.btn_dialer.pack(pady=10, padx=20, fill="x")
        
        self.btn_records = ctk.CTkButton(self.sidebar_frame, text="🎵 Grabaciones", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=self.show_recordings)
        self.btn_records.pack(pady=10, padx=20, fill="x")
        
        self.btn_profile = ctk.CTkButton(self.sidebar_frame, text="⚙️ Servidor Celular", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=self.show_profile)
        self.btn_profile.pack(pady=10, padx=20, fill="x")
        
        self.btn_stats = ctk.CTkButton(self.sidebar_frame, text="📊 Registro de Actividad", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=self.show_stats)
        self.btn_stats.pack(pady=10, padx=20, fill="x")

        self.btn_sisco = ctk.CTkButton(self.sidebar_frame, text="🔗 Conexión SISCO", fg_color="#4285F4", hover_color="#3367d6", text_color="white", command=self.show_sisco)
        self.btn_sisco.pack(pady=10, padx=20, fill="x")

        self.btn_change_pwd = ctk.CTkButton(self.sidebar_frame, text="🔑 Cambiar Contraseña", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=self.show_change_password)
        self.btn_change_pwd.pack(pady=10, padx=20, fill="x")

        self.sidebar_buttons = [self.btn_dialer, self.btn_records, self.btn_profile, self.btn_stats]
        print("[App] >> botones sidebar listos")
        
        # Right frame
        self.right_frame = ctk.CTkFrame(self.current_frame, fg_color="transparent")
        self.right_frame.pack(side="right", expand=True, fill="both")
        print("[App] >> right_frame creado")
        
        self.header_frame = ctk.CTkFrame(self.right_frame, fg_color=GPH_BLUE, corner_radius=10, height=50)
        self.header_frame.pack(side="top", fill="x", padx=20, pady=(15, 0))
        self.header_frame.pack_propagate(False)
        
        greeting_lbl = ctk.CTkLabel(self.header_frame, text=f"Bienvenido(a), {username.capitalize()} ({role})", font=ctk.CTkFont(size=18, weight="bold"), text_color="white")
        greeting_lbl.pack(side="left", padx=25, pady=10)
        
        self.lbl_global_cartera = ctk.CTkLabel(self.header_frame, text="Verificando cartera...", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
        self.lbl_global_cartera.pack(side="left", padx=20, pady=10)
        
        self.btn_logout = ctk.CTkButton(self.header_frame, text="🚪 Cerrar Sesión", width=120, height=32, corner_radius=8, fg_color="#ef4444", hover_color="#dc2626", text_color="white", font=ctk.CTkFont(size=12, weight="bold"), command=self.logout)
        self.btn_logout.pack(side="right", padx=15, pady=8)

        # --- NUEVO BANNER GLOBAL DE CONEXIÓN ---
        self.connection_status_ui = ctk.CTkFrame(self.header_frame, fg_color="#94A3B8", corner_radius=8, height=30)
        self.connection_status_ui.pack(side="right", padx=10)
        self.connection_status_label = ctk.CTkLabel(self.connection_status_ui, text="Buscando...", font=ctk.CTkFont(size=11, weight="bold"), text_color="white", width=250)
        self.connection_status_label.pack(padx=10, pady=5)
        
        print("[App] >> header creado")
        
        self.content_frame = ctk.CTkFrame(self.right_frame, fg_color="white", corner_radius=10)
        self.content_frame.pack(side="top", expand=True, fill="both", padx=20, pady=15)
        print("[App] >> content_frame creado")

        self.footer_frame = ctk.CTkFrame(self.right_frame, height=30, fg_color="#f1f5f9", corner_radius=0)
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)
        
        self.status_lbl = ctk.CTkLabel(self.footer_frame, text="✅ Sistema Listo", font=ctk.CTkFont(size=11), text_color="#64748b")
        self.status_lbl.pack(side="left", padx=20)
        
        self.sync_indicator = ctk.CTkLabel(self.footer_frame, text="", font=ctk.CTkFont(size=10), text_color="#94a3b8")
        self.sync_indicator.pack(side="right", padx=20)
        
        self.active_module = None
        self.is_syncing = False 
        
        if not database_core.has_sisco_profile():
            print("[App] >> Perfil SISCO no detectado. Bloqueando UI y mostrando SiscoFrame.")
            self.lock_sidebar()
            self.show_sisco()
        else:
            print("[App] >> Perfil SISCO OK. Cargando Dialer.")
            self.show_dialer()
            
        print("[App] >> show_home COMPLETO")

    def update_connection_status_ui(self, is_connected):
        """Actualiza el color y texto del banner de conexión en el header."""
        if not hasattr(self, 'connection_status_ui') or not self.connection_status_ui.winfo_exists(): return
        
        if is_connected:
            self.connection_status_ui.configure(fg_color="#10B981") # Verde
            self.connection_status_label.configure(text="✅ Celular Conectado")
        else:
            self.connection_status_ui.configure(fg_color="#EF4444") # Rojo
            self.connection_status_label.configure(text="⚠️ Celular Desconectado")

    def lock_sidebar(self):
        print("[UI] Sidebar Bloqueado")
        if hasattr(self, 'sidebar_buttons'):
            for btn in self.sidebar_buttons:
                btn.configure(state="disabled")
        if hasattr(self, 'btn_sisco'):
            self.btn_sisco.configure(state="disabled")
        if hasattr(self, 'btn_change_pwd'):
            self.btn_change_pwd.configure(state="disabled")

    def unlock_sidebar(self):
        print("[UI] Sidebar Desbloqueado")
        if hasattr(self, 'sidebar_buttons'):
            for btn in self.sidebar_buttons:
                btn.configure(state="normal")
        if hasattr(self, 'btn_sisco'):
            self.btn_sisco.configure(state="normal")
        if hasattr(self, 'btn_change_pwd'):
            self.btn_change_pwd.configure(state="normal")

    def show_dialer(self):
        print("[App] >> DialerFrame: destruyendo módulo anterior...")
        if self.active_module:
            self.active_module.destroy()
        print("[App] >> DialerFrame: creando instancia...")
        self.active_module = DialerFrame(self.content_frame, self.mixer)
        print("[App] >> DialerFrame: instancia creada OK")

    def show_recordings(self):
        if self.active_module:
            self.active_module.destroy()
        self.active_module = RecordingsFrame(self.content_frame)

    def show_profile(self):
        if self.active_module:
            self.active_module.destroy()
        self.active_module = ProfileFrame(self.content_frame, self.mixer)

    def show_sisco(self):
        if self.active_module:
            self.active_module.destroy()
        self.active_module = SiscoFrame(self.content_frame, on_auth_success=self.unlock_sidebar)

    def show_stats(self):
        if self.active_module:
            self.active_module.destroy()
        self.active_module = StatsFrame(self.content_frame)

    def show_change_password(self):
        pwd_window = ctk.CTkToplevel(self)
        pwd_window.title("Gestión de Contraseña")
        
        is_admin = (database_core.CURRENT_USER_ROLE == "Administrador")
        win_w, win_h = 550, 600
        pwd_window.geometry(f"{win_w}x{win_h}")
        pwd_window.grab_set()
        
        try:
            icon_path = obtener_ruta_recurso("favicon (7).ico")
            if os.path.exists(icon_path):
                pwd_window.after(200, lambda: pwd_window.iconbitmap(icon_path))
        except Exception as e:
            print(f"[UI] Error cargando icono en modal: {e}")
            
        pwd_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (win_w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (win_h // 2)
        pwd_window.geometry(f"+{x}+{y}")
        
        pwd_window.configure(fg_color=GPH_BLUE)
        
        # Container principal
        main_frame = ctk.CTkFrame(pwd_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        title_lbl = ctk.CTkLabel(main_frame, text="Gestión de Contraseña", font=ctk.CTkFont(size=22, weight="bold"), text_color="white")
        title_lbl.pack(pady=(5, 10))
        
        if is_admin:
            tabs = ctk.CTkTabview(main_frame, fg_color="#1e293b", segmented_button_fg_color="#0f172a", segmented_button_selected_color=GPH_ACCENT, segmented_button_selected_hover_color="#1d4a99")
            tabs.pack(fill="both", expand=True)
            tab_perfil = tabs.add("Mi Perfil")
            tab_admin = tabs.add("Administración")
            
            # Scrollable frame inside the tab so it can keep the large original design
            parent_perfil = ctk.CTkScrollableFrame(tab_perfil, fg_color="transparent")
            parent_perfil.pack(fill="both", expand=True)
        else:
            # Scrollable frame directly if no tabs
            parent_perfil = ctk.CTkScrollableFrame(main_frame, fg_color="transparent")
            parent_perfil.pack(fill="both", expand=True)

        # --- PESTAÑA / VISTA MI PERFIL ---
        def build_profile_view(parent):
            info_frame = ctk.CTkFrame(parent, fg_color="#0f172a", border_width=2, border_color="#38bdf8", corner_radius=10)
            info_frame.pack(fill="x", pady=(0, 15), ipadx=10, ipady=10)
            
            user_lbl = ctk.CTkLabel(info_frame, text=f"👤 Usuario: {database_core.CURRENT_USER}", font=ctk.CTkFont(size=15, weight="bold"), text_color="white")
            user_lbl.pack(pady=(10, 2))
            role_lbl = ctk.CTkLabel(info_frame, text=f"Rol: {database_core.CURRENT_USER_ROLE}", font=ctk.CTkFont(size=13), text_color="#cbd5e1")
            role_lbl.pack(pady=(0, 10))
            
            pwd_frame = ctk.CTkFrame(parent, fg_color="transparent")
            pwd_frame.pack(fill="x", expand=False)
            
            lbl_old = ctk.CTkLabel(pwd_frame, text="Contraseña Actual:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_old.pack(anchor="w", pady=(0, 0))
            entry_old = ctk.CTkEntry(pwd_frame, show="*", width=400, height=35, fg_color="#0f172a", border_color="#334155", text_color="white")
            entry_old.pack(pady=(2, 10))
            
            lbl_new = ctk.CTkLabel(pwd_frame, text="Nueva Contraseña:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_new.pack(anchor="w")
            entry_new = ctk.CTkEntry(pwd_frame, show="*", width=400, height=35, fg_color="#0f172a", border_color="#334155", text_color="white")
            entry_new.pack(pady=(2, 10))
            
            lbl_confirm = ctk.CTkLabel(pwd_frame, text="Confirmar Contraseña:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_confirm.pack(anchor="w")
            entry_confirm = ctk.CTkEntry(pwd_frame, show="*", width=400, height=35, fg_color="#0f172a", border_color="#334155", text_color="white")
            entry_confirm.pack(pady=(2, 10))
            
            lbl_error = ctk.CTkLabel(pwd_frame, text="", text_color="#ef4444", font=ctk.CTkFont(size=12))
            lbl_error.pack(pady=(0, 5))
            
            gen_frame = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=8)
            gen_frame.pack(fill="x", pady=(5, 15), ipadx=10, ipady=10)
            
            gen_title = ctk.CTkLabel(gen_frame, text="🛡️ Generador de Contraseña Segura", font=ctk.CTkFont(size=14, weight="bold"), text_color="white")
            gen_title.pack(pady=(5, 5))
            
            lbl_generated = ctk.CTkLabel(gen_frame, text="---", font=ctk.CTkFont(size=18, weight="bold"), text_color="#38bdf8")
            lbl_generated.pack(pady=(0, 10))
            
            def generate_secure_pwd():
                import string, random
                chars = string.ascii_letters + string.digits + "!@#$%^&*"
                secure_pwd = "".join(random.choice(chars) for _ in range(12))
                lbl_generated.configure(text=secure_pwd)
                pwd_window.clipboard_clear()
                pwd_window.clipboard_append(secure_pwd)
                pwd_window.update()
                
                entry_new.delete(0, 'end')
                entry_new.insert(0, secure_pwd)
                entry_new.configure(show="")
                entry_confirm.delete(0, 'end')
                entry_confirm.insert(0, secure_pwd)
                entry_confirm.configure(show="")
                lbl_error.configure(text="Contraseña copiada al portapapeles y aplicada.", text_color="#10B981")
                
            btn_gen = ctk.CTkButton(gen_frame, text="Generar y Usar Contraseña", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=generate_secure_pwd)
            btn_gen.pack(pady=(0, 5))
            
            def attempt_change():
                old_p = entry_old.get()
                new_p = entry_new.get()
                conf_p = entry_confirm.get()
                
                if not old_p or not new_p or not conf_p:
                    lbl_error.configure(text="Completa todos los campos.", text_color="#EF4444")
                    return
                if new_p != conf_p:
                    lbl_error.configure(text="Las nuevas contraseñas no coinciden.", text_color="#EF4444")
                    return
                if len(new_p) < 4:
                    lbl_error.configure(text="Mínimo 4 caracteres.", text_color="#EF4444")
                    return
                    
                btn_save.configure(state="disabled", text="Guardando...")
                def task():
                    success, msg = database_core.change_password(old_p, new_p)
                    self.after(0, handle_result, success, msg)
                    
                def handle_result(success, msg):
                    if not pwd_window.winfo_exists(): return
                    btn_save.configure(state="normal", text="Actualizar Contraseña")
                    if success:
                        import tkinter.messagebox as msgbox
                        msgbox.showinfo("Éxito", msg)
                        pwd_window.destroy()
                    else:
                        lbl_error.configure(text=msg, text_color="#EF4444")
                
                import threading
                threading.Thread(target=task, daemon=True).start()
                
            buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
            buttons_frame.pack(fill="x", pady=(5, 10))
            
            btn_save = ctk.CTkButton(buttons_frame, text="Actualizar Contraseña", font=ctk.CTkFont(size=14, weight="bold"), height=40, fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=attempt_change)
            btn_save.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            btn_cancel = ctk.CTkButton(buttons_frame, text="Cancelar", font=ctk.CTkFont(size=14, weight="bold"), height=40, fg_color="#ef4444", hover_color="#dc2626", text_color="white", command=pwd_window.destroy)
            btn_cancel.pack(side="right", fill="x", expand=True, padx=(5, 0))

        build_profile_view(parent_perfil)
        
        # --- PESTAÑA ADMINISTRACIÓN ---
        if is_admin:
            scroll_admin = ctk.CTkScrollableFrame(tab_admin, fg_color="transparent")
            scroll_admin.pack(fill="both", expand=True)
            
            lbl_select = ctk.CTkLabel(scroll_admin, text="Seleccionar Usuario:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_select.pack(anchor="w")
            
            cmb_users = ctk.CTkComboBox(scroll_admin, values=["Cargando..."], width=400)
            cmb_users.pack(pady=(2, 10))
            
            lbl_last_seen = ctk.CTkLabel(scroll_admin, text="Última conexión: --", font=ctk.CTkFont(size=12), text_color="#94a3b8")
            lbl_last_seen.pack(anchor="w", pady=(0, 10))
            
            # Form reset
            reset_frame = ctk.CTkFrame(scroll_admin, fg_color="transparent")
            reset_frame.pack(fill="x", expand=False)
            
            lbl_new_admin = ctk.CTkLabel(reset_frame, text="Nueva Contraseña:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_new_admin.pack(anchor="w")
            entry_new_admin = ctk.CTkEntry(reset_frame, show="*", width=400, height=35, fg_color="#0f172a", border_color="#334155", text_color="white")
            entry_new_admin.pack(pady=(2, 10))
            
            lbl_conf_admin = ctk.CTkLabel(reset_frame, text="Confirmar Contraseña:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cbd5e1")
            lbl_conf_admin.pack(anchor="w")
            entry_conf_admin = ctk.CTkEntry(reset_frame, show="*", width=400, height=35, fg_color="#0f172a", border_color="#334155", text_color="white")
            entry_conf_admin.pack(pady=(2, 10))
            
            lbl_error_admin = ctk.CTkLabel(reset_frame, text="", text_color="#ef4444", font=ctk.CTkFont(size=12))
            lbl_error_admin.pack(pady=(0, 5))
            
            gen_frame_admin = ctk.CTkFrame(scroll_admin, fg_color="#1e293b", corner_radius=8)
            gen_frame_admin.pack(fill="x", pady=(5, 15), ipadx=10, ipady=10)
            
            gen_title_admin = ctk.CTkLabel(gen_frame_admin, text="🛡️ Generador de Contraseña Segura", font=ctk.CTkFont(size=14, weight="bold"), text_color="white")
            gen_title_admin.pack(pady=(5, 5))
            
            lbl_gen_admin = ctk.CTkLabel(gen_frame_admin, text="---", font=ctk.CTkFont(size=18, weight="bold"), text_color="#38bdf8")
            lbl_gen_admin.pack(pady=(0, 10))
            
            def generate_secure_admin():
                import string, random
                chars = string.ascii_letters + string.digits + "!@#$%^&*"
                secure_pwd = "".join(random.choice(chars) for _ in range(12))
                lbl_gen_admin.configure(text=secure_pwd)
                pwd_window.clipboard_clear()
                pwd_window.clipboard_append(secure_pwd)
                pwd_window.update()
                
                entry_new_admin.delete(0, 'end')
                entry_new_admin.insert(0, secure_pwd)
                entry_new_admin.configure(show="")
                entry_conf_admin.delete(0, 'end')
                entry_conf_admin.insert(0, secure_pwd)
                entry_conf_admin.configure(show="")
                lbl_error_admin.configure(text="Contraseña copiada al portapapeles y aplicada.", text_color="#10B981")
                
            btn_gen_admin = ctk.CTkButton(gen_frame_admin, text="Generar y Usar Contraseña", fg_color=GPH_ACCENT, hover_color="#1d4a99", text_color="white", command=generate_secure_admin)
            btn_gen_admin.pack(pady=(0, 5))
            
            users_map = {}
            def load_users():
                import threading
                def fetch():
                    data = database_core.get_all_users_status()
                    if not pwd_window.winfo_exists(): return
                    self.after(0, lambda: on_users_loaded(data))
                threading.Thread(target=fetch, daemon=True).start()
                
            def on_users_loaded(data):
                names = []
                for u in data:
                    un = u.get('username')
                    if un:
                        users_map[un] = u
                        names.append(un)
                if names:
                    cmb_users.configure(values=names)
                    cmb_users.set(names[0])
                    on_user_select(names[0])
                else:
                    cmb_users.configure(values=["No hay usuarios"])
                    
            def on_user_select(choice):
                u = users_map.get(choice)
                if u:
                    ls = u.get('last_seen')
                    if ls:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(ls.replace("Z", "+00:00"))
                            lbl_last_seen.configure(text=f"Última conexión: {dt.strftime('%d/%m/%Y %H:%M:%S')}")
                        except: lbl_last_seen.configure(text=f"Última conexión: {ls}")
                    else:
                        lbl_last_seen.configure(text="Última conexión: Nunca")
                        
            cmb_users.configure(command=on_user_select)
            load_users()
            
            def attempt_admin_reset():
                target = cmb_users.get()
                new_p = entry_new_admin.get()
                conf_p = entry_conf_admin.get()
                
                if not target or target == "Cargando..." or target == "No hay usuarios":
                    return
                if not new_p or not conf_p:
                    lbl_error_admin.configure(text="Completa todos los campos.", text_color="#EF4444")
                    return
                if new_p != conf_p:
                    lbl_error_admin.configure(text="Las contraseñas no coinciden.", text_color="#EF4444")
                    return
                if len(new_p) < 4:
                    lbl_error_admin.configure(text="Mínimo 4 caracteres.", text_color="#EF4444")
                    return
                    
                btn_reset_admin.configure(state="disabled", text="Restableciendo...")
                def task():
                    success, msg = database_core.admin_reset_password(target, new_p)
                    self.after(0, handle_result, success, msg, new_p)
                    
                def handle_result(success, msg, applied_pwd):
                    if not pwd_window.winfo_exists(): return
                    btn_reset_admin.configure(state="normal", text="Restablecer y Expulsar")
                    if success:
                        pwd_window.clipboard_clear()
                        pwd_window.clipboard_append(applied_pwd)
                        pwd_window.update()
                        import tkinter.messagebox as msgbox
                        msgbox.showinfo("Éxito", f"{msg}\n\nLa nueva contraseña ha sido copiada al portapapeles.")
                        pwd_window.destroy()
                    else:
                        lbl_error_admin.configure(text=msg, text_color="#EF4444")
                
                import threading
                threading.Thread(target=task, daemon=True).start()
                
            buttons_frame_admin = ctk.CTkFrame(scroll_admin, fg_color="transparent")
            buttons_frame_admin.pack(fill="x", pady=(5, 10))
            
            btn_reset_admin = ctk.CTkButton(buttons_frame_admin, text="Restablecer y Expulsar", font=ctk.CTkFont(size=14, weight="bold"), height=40, fg_color="#ef4444", hover_color="#dc2626", text_color="white", command=attempt_admin_reset)
            btn_reset_admin.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            btn_cancel_admin = ctk.CTkButton(buttons_frame_admin, text="Cancelar", font=ctk.CTkFont(size=14, weight="bold"), height=40, fg_color="#ef4444", hover_color="#dc2626", text_color="white", command=pwd_window.destroy)
            btn_cancel_admin.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def logout(self, auto_expired=False, force_kick=False, reason=None):
        self._heartbeat_running = False
        print(f"[App] Cerrando sesión {'(AUTO)' if auto_expired else ''} {'(KICK)' if force_kick else ''}...")
        
        threading.Thread(target=database_core.set_offline_instant, daemon=True).start()

        database_core.clear_session()
        database_core.CURRENT_USER = None
        database_core.CURRENT_USER_ID = None
        database_core.CURRENT_USER_ROLE = "Usuario"
        
        if auto_expired and self.state() != "iconic":
            import tkinter.messagebox as msgbox
            msgbox.showwarning("Sesión Expirada", "Su sesión ha sido cerrada por inactividad para proteger sus datos.")
            
        if force_kick and self.state() != "iconic":
            import tkinter.messagebox as msgbox
            if reason == "blocked":
                msgbox.showwarning("Acceso Bloqueado", 
                    "Su cuenta ha sido BLOQUEADA por un administrador.\n\n"
                    "No podrá acceder al sistema hasta que el administrador habilite su cuenta nuevamente.\n\n"
                    "Contacte a soporte para más información.")
            else:
                msgbox.showwarning("Mantenimiento del Sistema", 
                    "La aplicación se encuentra en mantenimiento programado.\n\n"
                    "Has sido expulsado temporalmente por un administrador.\n\n"
                    "Por favor, contacta al administrador antes de intentar ingresar nuevamente.")
        
        self.show_login()

    def update_last_activity(self):
        self.last_activity = time.time()

    def _check_inactivity(self):
        if database_core.CURRENT_USER:
            try:
                timeout_min = int(database_core.get_global_setting("inactivity_timeout_minutes", 30))
                timeout_sec = timeout_min * 60
            except:
                timeout_sec = 1800  
            
            elapsed = time.time() - self.last_activity
            if elapsed > timeout_sec:
                self.after(0, lambda: self.logout(auto_expired=True))
                return  
            
        self.after(30000, self._check_inactivity)

    def update_sync_status(self, message, color="#64748b"):
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            try:
                self.after(0, lambda: self.status_lbl.configure(text=message, text_color=color))
            except:
                pass

    def _service_watchdog(self):
        print("[App] Watchdog de servicios iniciado con Auto-Curación.")
        while self._heartbeat_running: # Se detiene cuando la app cierra
            try:
                phone_ip = database_core.get_config("phone_ip")
                if phone_ip:
                    is_connected = self._check_phone_status_silent(phone_ip)
                    
                    if is_connected:
                        self._failure_counter = 0 
                        # Si estaba desconectado y ahora ya no, actualizamos UI
                        if not database_core.AppState.phone_connected:
                            database_core.AppState.phone_connected = True
                            self.after(0, lambda: self.update_connection_status_ui(True))
                    else:
                        self._failure_counter += 1
                        # Solo marcamos como desconectado si falla 3 veces seguidas (3 x 3s = 9s de margen)
                        if self._failure_counter >= self._MAX_FAILURES:
                            if database_core.AppState.phone_connected:
                                database_core.AppState.phone_connected = False
                                self.after(0, lambda: self.update_connection_status_ui(False))
                    
                    # Auto-recuperación silenciosa (Intenta buscar si está en rojo)
                    if not database_core.AppState.phone_connected:
                        new_ip = self._silent_udp_discovery()
                        if new_ip:
                            database_core.set_config("phone_ip", new_ip)
                            self._failure_counter = 0
                            database_core.AppState.phone_connected = True
                            self.after(0, lambda: self.update_connection_status_ui(True))
                            
            except Exception as e:
                # Logueamos errores sin detener el watchdog
                print(f"[Watchdog] Error de ciclo: {e}")
            
            time.sleep(3) # Chequeo cada 3 segundos (estándar para GPH)

    def _silent_udp_discovery(self):
        """Busca el celular en la red de forma invisible sin congelar la app"""
        import socket
        try:
            # Obtiene IP local
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                pc_ip = s.getsockname()[0]
                
            broadcast_ip = ".".join(pc_ip.split('.')[:-1]) + '.255'
            
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.settimeout(1.5) # Muy poco tiempo para no afectar el bucle
                s.sendto(b"GPH_DISCOVER_REQUEST", (broadcast_ip, 9090))
                data, addr = s.recvfrom(1024)
                if data.startswith(b"GPH_DISCOVER_RESPONSE"):
                    return data.decode().split(":")[1]
        except:
            pass
        return None

    def _check_phone_status_silent(self, ip):
        import requests
        try:
            res = requests.get(f"http://{ip}:8080/status", timeout=3)
            return res.status_code == 200
        except: 
            return False

    def _check_session_protection(self):
        def task():
            print("[App] Validando protección de sesión...")
            try:
                token = api_gph._get_valid_token()
                if token is None:
                    print("[App] Sesión inválida detectada por Watchdog. Cerrando...")
                    database_core.log_telemetry("AUTH", "Sesión invalidada por protección automática", "WARNING")
                    self.after(0, self.show_login)
                else:
                    database_core.AppState.session_valid = True
            except Exception as e:
                print(f"[App] Warning: Error validando sesión (ignorando): {e}")
            finally:
                self.after(300000, self._check_session_protection)
        
        threading.Thread(target=task, daemon=True).start()

    def _start_silent_sync(self):
        def run_full_sync(es_forzoso=False):
            if database_core.AppState.syncing: return
            
            database_core.AppState.syncing = True
            print(f"[SYNC] Iniciando flujo {'forzoso' if es_forzoso else 'silencioso'}...")
            
            # Usamos lambdas vacías para que el sync silencioso no busque ventanas de UI
            api_gph.sincronizar_contactos_posventa(
                on_progress=None, 
                on_success=lambda: api_gph.descargar_cartera_backend(
                    on_progress=None,
                    on_success=lambda: self._finalizar_sync_total(True),
                    on_error=lambda err: self._finalizar_sync_total(False)
                ),
                on_error=lambda err: self._finalizar_sync_total(False)
            )

        if database_core.cartera_needs_refresh():
            print("[SYNC] Cartera desactualizada. Ejecutando descarga forzosa...")
            threading.Thread(target=lambda: run_full_sync(True), daemon=True).start()
        
        def sync_worker():
            time.sleep(300) 
            while True:
                if not database_core.AppState.syncing:
                    run_full_sync(False)
                time.sleep(3600)

        threading.Thread(target=sync_worker, daemon=True).start()

    def _finalizar_sync_total(self, success=True):
        database_core.AppState.syncing = False
        print(f"[SYNC] Proceso finalizado. Exito: {success}")
        if hasattr(self, 'active_module') and hasattr(self.active_module, 'refresh_data'):
            self.after(0, self.active_module.refresh_data)

    def _on_bg_sync_complete(self):
        print("[Background Sync] OK - Base actualizada.")
        if hasattr(self, 'active_module') and self.active_module:
            if hasattr(self.active_module, 'refresh_data'):
                self.after(0, self.active_module.refresh_data)

    def on_closing(self):
        self._heartbeat_running = False
        self.destroy()

if __name__ == "__main__":
    import ctypes
    mutex_name = "Global\\CentralGPH_Mutex_App"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:
        import tkinter.messagebox as msgbox
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        msgbox.showwarning("Atención", "La aplicación Central GPH ya se encuentra abierta.")
        sys.exit(0)

    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()