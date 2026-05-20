import customtkinter as ctk
import database_core
import json
import threading
from datetime import datetime, timezone
import tkinter.messagebox as msgbox

GPH_BLUE = "#011536"
GPH_ACCENT = "#2b64d3"

class StatsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.pack(expand=True, fill="both")
        
        ctk.CTkLabel(self, text="📊 Registro de Actividad", font=ctk.CTkFont(size=24, weight="bold"), text_color=GPH_BLUE).pack(pady=(20, 10))

        self.tabview = ctk.CTkTabview(self, fg_color="white", segmented_button_fg_color="#f0f2f5",
                                      segmented_button_selected_color=GPH_ACCENT,
                                      segmented_button_selected_hover_color="#1d4a99")
        self.tabview.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        
        self.tab_calls = self.tabview.add("📞 Llamadas (Hoy)")
        self.tab_gestiones = self.tabview.add("🚀 Gestiones (Hoy)")
        self.tab_hist = self.tabview.add("📅 Histórico")
        
        # PESTAÑA SECRETA: Solo para administradores
        self.is_admin = getattr(database_core, 'CURRENT_USER_ROLE', 'Usuario') == 'Administrador'
        if self.is_admin:
            self.tab_admin = self.tabview.add("👑 Monitor (Admin)")

        self.btn_refresh = ctk.CTkButton(self, text="🔄 Refrescar", width=100, height=32, 
                                        fg_color=GPH_ACCENT, hover_color="#1d4a99", command=self._load_data)
        self.btn_refresh.place(relx=0.95, rely=0.05, anchor="ne")

        self._setup_calls_tab()
        self._setup_gestiones_tab()
        self._setup_hist_tab()
        if self.is_admin:
            self._setup_admin_tab()

        self._load_data()

    def _setup_calls_tab(self):
        cards = ctk.CTkFrame(self.tab_calls, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=10)
        self.c_today = self._stat_card(cards, "📞", "Hoy", "0", "#2E8B57")
        self.c_today.pack(side="left", expand=True, fill="x", padx=5)
        self.c_total = self._stat_card(cards, "📱", "Total Histórico", "0", GPH_ACCENT)
        self.c_total.pack(side="left", expand=True, fill="x", padx=5)
        self.c_avg = self._stat_card(cards, "⏱", "Promedio Hoy", "0s", "#E67E22")
        self.c_avg.pack(side="left", expand=True, fill="x", padx=5)
        
        self.table_calls = ctk.CTkScrollableFrame(self.tab_calls, fg_color="#f8f9fa", height=300)
        self.table_calls.pack(fill="both", expand=True, padx=10, pady=5)

    def _setup_gestiones_tab(self):
        cards = ctk.CTkFrame(self.tab_gestiones, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=10)
        self.g_ok = self._stat_card(cards, "✅", "Exitosas (Hoy)", "0", "#2E8B57")
        self.g_ok.pack(side="left", expand=True, fill="x", padx=5)
        self.g_err = self._stat_card(cards, "⚠️", "Pendientes/Errores", "0", "#F59E0B")
        self.g_err.pack(side="left", expand=True, fill="x", padx=5)
        self.g_total = self._stat_card(cards, "🚀", "Total (Hoy)", "0", GPH_ACCENT)
        self.g_total.pack(side="left", expand=True, fill="x", padx=5)

        self.table_gest = ctk.CTkScrollableFrame(self.tab_gestiones, fg_color="#f8f9fa", height=300)
        self.table_gest.pack(fill="both", expand=True, padx=10, pady=5)

    def _setup_hist_tab(self):
        f_frame = ctk.CTkFrame(self.tab_hist, fg_color="transparent")
        f_frame.pack(fill="x", padx=10, pady=10)
        
        # --- LÓGICA DE CALENDARIO ---
        def _open_cal(target_entry):
            cal_win = ctk.CTkToplevel(self)
            cal_win.title("Seleccionar Fecha")
            cal_win.geometry("280x300")
            cal_win.configure(fg_color="#0B1120")
            cal_win.transient(self.winfo_toplevel())
            cal_win.grab_set()
            
            # Centrar mini-ventana
            cal_win.update_idletasks()
            x = cal_win.winfo_screenwidth() // 2 - 140
            y = cal_win.winfo_screenheight() // 2 - 150
            cal_win.geometry(f"+{x}+{y}")
            
            now = datetime.now()
            state = {"y": now.year, "m": now.month}
            cal_frame = ctk.CTkFrame(cal_win, fg_color="#0B1120")
            cal_frame.pack(fill="both", expand=True, padx=8, pady=8)

            def _draw():
                for w in cal_frame.winfo_children(): w.destroy()
                import calendar
                nav = ctk.CTkFrame(cal_frame, fg_color="transparent")
                nav.pack(fill="x", pady=4)
                
                ctk.CTkButton(nav, text="◀", width=30, fg_color="#1E293B", text_color="white", 
                              command=lambda: _nav(-1)).pack(side="left", padx=4)
                
                meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                ctk.CTkLabel(nav, text=f"{meses[state['m']-1]} {state['y']}", text_color="white", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", expand=True)
                
                ctk.CTkButton(nav, text="▶", width=30, fg_color="#1E293B", text_color="white", 
                              command=lambda: _nav(1)).pack(side="right", padx=4)
                
                days_hdr = ctk.CTkFrame(cal_frame, fg_color="transparent")
                days_hdr.pack(fill="x")
                for d in ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]:
                    ctk.CTkLabel(days_hdr, text=d, width=34, text_color="#94A3B8", font=ctk.CTkFont(size=10)).pack(side="left")
                
                cal = calendar.monthcalendar(state['y'], state['m'])
                for week in cal:
                    row = ctk.CTkFrame(cal_frame, fg_color="transparent")
                    row.pack(fill="x")
                    for day in week:
                        if day == 0: 
                            ctk.CTkLabel(row, text="", width=34).pack(side="left")
                        else: 
                            ctk.CTkButton(row, text=str(day), width=34, height=28, fg_color="#1E293B", text_color="white", 
                                          command=lambda d=day: _pick(d)).pack(side="left", padx=1, pady=1)

            def _nav(delta):
                state['m'] += delta
                if state['m'] > 12: 
                    state['m'] = 1
                    state['y'] += 1
                elif state['m'] < 1: 
                    state['m'] = 12
                    state['y'] -= 1
                _draw()

            def _pick(day):
                val = f"{state['y']}-{state['m']:02d}-{day:02d}"
                target_entry.delete(0, 'end')
                target_entry.insert(0, val)
                cal_win.destroy()

            _draw()
        # -----------------------------------

        ctk.CTkLabel(f_frame, text="Desde:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#333").pack(side="left", padx=(5, 2))
        
        row_start = ctk.CTkFrame(f_frame, fg_color="transparent")
        row_start.pack(side="left")
        self.hist_date_start = ctk.CTkEntry(row_start, width=100)
        self.hist_date_start.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.hist_date_start.pack(side="left")
        ctk.CTkButton(row_start, text="📅", width=28, fg_color="#011536", text_color="white", command=lambda: _open_cal(self.hist_date_start)).pack(side="left", padx=(2,0))
        
        ctk.CTkLabel(f_frame, text="Hasta:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#333").pack(side="left", padx=(15, 2))
        
        row_end = ctk.CTkFrame(f_frame, fg_color="transparent")
        row_end.pack(side="left")
        self.hist_date_end = ctk.CTkEntry(row_end, width=100)
        self.hist_date_end.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.hist_date_end.pack(side="left")
        ctk.CTkButton(row_end, text="📅", width=28, fg_color="#011536", text_color="white", command=lambda: _open_cal(self.hist_date_end)).pack(side="left", padx=(2,0))
        
        ctk.CTkLabel(f_frame, text="Módulo:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#333").pack(side="left", padx=(20, 5))
        self.hist_type = ctk.CTkComboBox(f_frame, values=["Llamadas", "Gestiones"], width=130)
        self.hist_type.set("Llamadas")
        self.hist_type.pack(side="left", padx=5)
        
        ctk.CTkButton(f_frame, text="🔍 Buscar", fg_color=GPH_ACCENT, hover_color="#1d4a99", width=100, command=self._load_history).pack(side="left", padx=20)
        
        self.table_hist = ctk.CTkScrollableFrame(self.tab_hist, fg_color="#f8f9fa", height=300)
        self.table_hist.pack(fill="both", expand=True, padx=10, pady=5)

    def _setup_admin_tab(self):
        # Barra superior de Admin
        bar = ctk.CTkFrame(self.tab_admin, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(bar, text="Supervisión de Usuarios en Tiempo Real", font=ctk.CTkFont(size=18, weight="bold"), text_color="#011536").pack(side="left")
        
        # --- NUEVO: Contenedor para acciones masivas ---
        f_actions = ctk.CTkFrame(bar, fg_color="transparent")
        f_actions.pack(side="right")
        
        ctk.CTkButton(f_actions, text="✅ Restaurar Todos", fg_color="#3B82F6", hover_color="#2563EB", 
                      text_color="white", font=ctk.CTkFont(weight="bold"), width=120,
                      command=lambda: self._mass_action("restaurar")).pack(side="left", padx=4)
                      
        ctk.CTkButton(f_actions, text="🛑 Expulsar a Todos", fg_color="#F59E0B", hover_color="#D97706", 
                      text_color="white", font=ctk.CTkFont(weight="bold"), width=120,
                      command=lambda: self._mass_action("expulsar")).pack(side="left", padx=4)
                      
        ctk.CTkButton(f_actions, text="🔓 Desbloquear Todos", fg_color="#10B981", hover_color="#059669", 
                      text_color="white", font=ctk.CTkFont(weight="bold"), width=130,
                      command=lambda: self._mass_action("desbloquear")).pack(side="left", padx=4)
                      
        ctk.CTkButton(f_actions, text="🚫 Bloquear a Todos", fg_color="#ef4444", hover_color="#b91c1c", 
                      text_color="white", font=ctk.CTkFont(weight="bold"), width=130,
                      command=lambda: self._mass_action("bloquear")).pack(side="left", padx=4)
        # -----------------------------------------------

        # Contenedor de la tabla con borde y fondo blanco
        self.table_admin = ctk.CTkScrollableFrame(self.tab_admin, fg_color="#ffffff", border_width=1, border_color="#e2e8f0", corner_radius=10, height=350)
        self.table_admin.pack(fill="both", expand=True, padx=10, pady=5)

    def _header_tab(self, parent, cols):
        hdr = ctk.CTkFrame(parent, fg_color=GPH_BLUE, corner_radius=6, height=36)
        hdr.pack(fill="x", padx=4, pady=(4, 2))
        hdr.pack_propagate(False)
        for txt, w in cols:
            ctk.CTkLabel(hdr, text=txt, text_color="white", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", expand=True, fill="x", padx=8)

    def _stat_card(self, parent, icon, title, value, color):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=12, border_width=2, border_color=color, height=90)
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=f"{icon} {title}", font=ctk.CTkFont(size=11), text_color="#666").pack(pady=(8, 2))
        lbl = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        lbl.pack()
        card._val_label = lbl
        return card

    def _load_data(self):
        if not self.winfo_exists(): 
            return
        self._load_local_stats()
        self._load_history()
        if self.is_admin:
            self._load_admin_data()

    def _load_local_stats(self):
        try:
            import sqlite3
            conn = sqlite3.connect(database_core.DB_PATH, timeout=20, check_same_thread=False)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")

            cur.execute("SELECT COUNT(*) FROM calls")
            self.c_total._val_label.configure(text=str(cur.fetchone()[0]))
            cur.execute("SELECT COUNT(*) FROM calls WHERE start_time LIKE ?", (f"{today}%",))
            self.c_today._val_label.configure(text=str(cur.fetchone()[0]))
            cur.execute("SELECT AVG(duration_sec) FROM calls WHERE start_time LIKE ? AND duration_sec > 0", (f"{today}%",))
            avg = cur.fetchone()[0]
            self.c_avg._val_label.configure(text=f"{int(avg)}s" if avg else "0s")

            cur.execute("SELECT COUNT(*) FROM gestiones_log WHERE created_at LIKE ?", (f"{today}%",))
            self.g_total._val_label.configure(text=str(cur.fetchone()[0]))
            cur.execute("SELECT COUNT(*) FROM gestiones_log WHERE status='OK' AND created_at LIKE ?", (f"{today}%",))
            self.g_ok._val_label.configure(text=str(cur.fetchone()[0]))
            cur.execute("SELECT COUNT(*) FROM gestiones_log WHERE status!='OK' AND created_at LIKE ?", (f"{today}%",))
            self.g_err._val_label.configure(text=str(cur.fetchone()[0]))

            # --- TABLA LLAMADAS (Hoy) ---
            for w in self.table_calls.winfo_children(): w.destroy()
            # Añadimos la columna "Resumen" al final
            self._header_tab(self.table_calls, [("Teléfono", 0.20), ("Fecha", 0.25), ("Duración", 0.15), ("Archivo", 0.25), ("Resumen", 0.15)])

            # Aseguramos traer 'lote' y 'cliente' de la tabla calls (posiciones 4 y 5)
            cur.execute("SELECT phone_number, start_time, duration_sec, file_path, lote, cliente FROM calls WHERE start_time LIKE ? ORDER BY id DESC", (f"{today}%",))
            for i, r in enumerate(cur.fetchall()):
                # r[0]=phone, r[1]=time, r[2]=dur, r[3]=path, r[4]=lote, r[5]=cliente
                self._create_row(
                    self.table_calls, i, 
                    [r[0], r[1], f"{r[2]}s", r[3].split("\\")[-1] if r[3] else " "], 
                    tipo_detalle="llamada",
                    # Empaquetamos toda la info extra en un JSON fantasma para mandarlo al modal
                    payload_json=json.dumps({"Cliente": r[5] or "N/A", "Lote": r[4] or "N/A", "Teléfono": r[0], "Fecha": r[1], "Duración": f"{r[2]} segundos", "Archivo": r[3] or "Sin Audio"})
                )

            # --- TABLA GESTIONES (Hoy) ---
            for w in self.table_gest.winfo_children(): w.destroy()
            # Añadimos la columna "Ver" al final
            self._header_tab(self.table_gest, [("Lote", 0.15), ("Status", 0.15), ("Fecha", 0.20), ("Info/Error", 0.35), ("Resumen", 0.15)])

            # Aseguramos traer la columna 'payload_resumen' de la base de datos (Posición 4)
            cur.execute("SELECT lote, status, created_at, error_msg, payload_resumen FROM gestiones_log WHERE created_at LIKE ? ORDER BY id DESC", (f"{today}%",))
            
            for i, r in enumerate(cur.fetchall()):
                color = "#2E8B57" if r[1] == "OK" else ("#F59E0B" if "PENDIENTE" in str(r[1]) else "#EF4444")
                
                # Le pasamos el JSON del resumen (r[4]) a la función creadora de filas
                row = self._create_row(self.table_gest, i, [r[0], r[1], r[2], r[3] or "S/E"], status_color=color, payload_json=r[4], tipo_detalle="gestion")
            conn.close()
        except Exception as e: 
            print(f"[Stats] Error: {e}")

    def _load_history(self):
        if not self.winfo_exists(): 
            return
        date_start = self.hist_date_start.get().strip() + " 00:00:00"
        date_end = self.hist_date_end.get().strip() + " 23:59:59"
        mod_type = self.hist_type.get()
        
        for w in self.table_hist.winfo_children(): w.destroy()
            
        try:
            import sqlite3
            conn = sqlite3.connect(database_core.DB_PATH, timeout=20, check_same_thread=False)
            cur = conn.cursor()
            
            if mod_type == "Llamadas":
                self._header_tab(self.table_hist, [("Teléfono", 0.20), ("Fecha", 0.25), ("Duración", 0.15), ("Archivo", 0.25), ("Resumen", 0.15)])
                cur.execute("SELECT phone_number, start_time, duration_sec, file_path, lote, cliente FROM calls WHERE start_time >= ? AND start_time <= ? ORDER BY id DESC LIMIT 500", (date_start, date_end))
                for i, r in enumerate(cur.fetchall()):
                    self._create_row(
                        self.table_hist, i, 
                        [r[0], r[1], f"{r[2]}s", r[3].split("\\")[-1] if r[3] else " "], 
                        tipo_detalle="llamada",
                        payload_json=json.dumps({"Cliente": r[5] or "N/A", "Lote": r[4] or "N/A", "Teléfono": r[0], "Fecha": r[1], "Duración": f"{r[2]} segundos", "Archivo": r[3] or "Sin Audio"})
                    )

            else:
                # Añadimos la columna "Resumen" al encabezado
                self._header_tab(self.table_hist, [("Lote", 0.15), ("Status", 0.15), ("Fecha", 0.20), ("Info/Error", 0.35), ("Resumen", 0.15)])
                
                # Le pedimos a SQLite que también nos traiga la columna payload_resumen
                cur.execute("SELECT lote, status, created_at, error_msg, payload_resumen FROM gestiones_log WHERE created_at >= ? AND created_at <= ? ORDER BY id DESC LIMIT 500", (date_start, date_end))
                
                for i, r in enumerate(cur.fetchall()):
                    color = "#2E8B57" if r[1] == "OK" else ("#F59E0B" if "PENDIENTE" in str(r[1]) else "#EF4444")
                    
                    # Le pasamos el payload_json (r[4]) a _create_row para que dibuje el botón
                    self._create_row(
                        self.table_hist, i, 
                        [r[0], r[1], r[2], r[3] or "S/E"], 
                        status_color=color, 
                        payload_json=r[4], 
                        tipo_detalle="gestion"
                    )
            conn.close()
        except Exception as e: 
            print(f"[Stats Hist] Error: {e}")

    def _load_admin_data(self):
        """Carga los datos de usuarios desde Supabase"""
        for w in self.table_admin.winfo_children(): w.destroy()
        
        # Generar encabezado
        hdr = ctk.CTkFrame(self.table_admin, fg_color="#011536", corner_radius=8, height=45)
        hdr.pack(fill="x", padx=5, pady=(5, 10))
        hdr.pack_propagate(False)
        
        # Columnas del header con pesos proporcionales
        cols_config = [
            ("👤 EJECUTIVO", 0.25),
            ("📡 IP CELULAR", 0.15),
            ("🚥 ESTADO", 0.15),
            ("⏱ TIEMPO", 0.20),
            ("⚡ ACCIONES", 0.25)
        ]
        
        for txt, _ in cols_config:
            ctk.CTkLabel(hdr, text=txt, text_color="white", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", expand=True, fill="x", padx=8)

        def fetch():
            users = database_core.get_all_users_status()
            if not self.winfo_exists(): 
                return
            self.after(0, lambda: self._render_admin_rows(users))

        threading.Thread(target=fetch, daemon=True).start()

    def _render_admin_rows(self, users):
        for w in self.table_admin.winfo_children(): w.destroy()
        
        # --- ENCABEZADOS (Alineación estricta tipo Excel) ---
        hdr = ctk.CTkFrame(self.table_admin, fg_color="#011536", corner_radius=6, height=45)
        hdr.pack(fill="x", padx=5, pady=(5, 10))
        hdr.pack_propagate(False)
        
        # La propiedad 'uniform' obliga a que todas las columnas midan exactamente lo mismo (20% cada una)
        for col in range(5):
            hdr.grid_columnconfigure(col, weight=1, uniform="columna_excel")
            
        ctk.CTkLabel(hdr, text="👤 EJECUTIVO", text_color="white", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="nsew", pady=12)
        ctk.CTkLabel(hdr, text="📡 IP CELULAR", text_color="white", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, sticky="nsew", pady=12)
        ctk.CTkLabel(hdr, text="🚥 ESTADO", text_color="white", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="nsew", pady=12)
        ctk.CTkLabel(hdr, text="⏱ TIEMPO", text_color="white", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=3, sticky="nsew", pady=12)
        ctk.CTkLabel(hdr, text="⚡ ACCIONES", text_color="white", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=4, sticky="nsew", pady=12)

        for i, u in enumerate(users):
            uid = u.get("id")
            uname = str(u.get("username", "Desc")).upper()
            rol = u.get("role", "Usuario")
            ip = u.get("phone_ip", "NO VINCULADA")
            
            ls_raw = u.get("last_seen")
            ll_raw = u.get("last_login") 
            force_lock = u.get("force_logout", False)
            is_locked = u.get("is_locked", False) 
            
            status = "⚪ OFFLINE"
            status_text_color = "#475569" 
            status_bg_color = "#f1f5f9"   
            tiempo_activo = "--"
            
            if ls_raw:
                try:
                    dt = datetime.fromisoformat(ls_raw.replace("Z", "+00:00"))
                    now_utc = datetime.now(timezone.utc)
                    diff = (now_utc - dt).total_seconds()
                    
                    if diff < 45: 
                        status = "🟢 ACTIVO"
                        status_text_color = "#059669"
                        status_bg_color = "#d1fae5"
                        
                        if ll_raw:
                            try:
                                dt_login = datetime.fromisoformat(ll_raw.replace("Z", "+00:00"))
                                minutos_online = int((now_utc - dt_login).total_seconds() // 60)
                                if minutos_online < 60: tiempo_activo = f"{minutos_online} MIN"
                                else: tiempo_activo = f"{int(minutos_online // 60)} HRS"
                            except: tiempo_activo = "CONECTADO"
                        else: tiempo_activo = "CONECTADO"
                    else:
                        dt_local = dt.astimezone()
                        minutos_fuera = int(diff // 60)
                        if minutos_fuera < 60: tiempo_activo = f"HACE {minutos_fuera} MIN"
                        else:
                            horas = int(minutos_fuera // 60)
                            tiempo_activo = f"HACE {horas} HRS" if horas < 24 else dt_local.strftime("%d/%m/%Y")
                except: pass

            if is_locked:
                status = "🚫 BLOQUEADO"
                status_text_color = "#b91c1c"
                status_bg_color = "#fee2e2"
                tiempo_activo = "--"
            elif force_lock:
                status = "🔒 EXPULSADO"
                status_text_color = "#92400e"
                status_bg_color = "#fef3c7"
                
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            row = ctk.CTkFrame(self.table_admin, fg_color=bg, corner_radius=8, border_width=1, border_color="#e2e8f0", height=60)
            row.pack(fill="x", padx=5, pady=4)
            row.pack_propagate(False)
            
            # --- FILAS (Misma alineación estricta que el encabezado) ---
            for col in range(5):
                row.grid_columnconfigure(col, weight=1, uniform="columna_excel")
            
            # 1. EJECUTIVO (Centrado)
            f_usr = ctk.CTkFrame(row, fg_color="transparent")
            f_usr.grid(row=0, column=0, sticky="nsew")
            f_usr_center = ctk.CTkFrame(f_usr, fg_color="transparent")
            f_usr_center.pack(expand=True) # Centrar dentro de la celda
            ctk.CTkLabel(f_usr_center, text=uname, font=ctk.CTkFont(size=13, weight="bold"), text_color="#0f172a").pack()
            ctk.CTkLabel(f_usr_center, text=rol, font=ctk.CTkFont(size=10), text_color="#64748b").pack()
            
            # 2. IP CELULAR (Centrado)
            ctk.CTkLabel(row, text=ip, font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").grid(row=0, column=1, sticky="nsew")
            
            # 3. ESTADO (Centrado con Badge)
            f_badge = ctk.CTkFrame(row, fg_color="transparent")
            f_badge.grid(row=0, column=2, sticky="nsew")
            badge_bg = ctk.CTkFrame(f_badge, fg_color=status_bg_color, corner_radius=6)
            badge_bg.pack(expand=True)
            ctk.CTkLabel(badge_bg, text=status, font=ctk.CTkFont(size=11, weight="bold"), text_color=status_text_color).pack(padx=12, pady=4)
            
            # 4. TIEMPO (Centrado)
            ctk.CTkLabel(row, text=tiempo_activo, font=ctk.CTkFont(size=12, weight="bold"), text_color="#475569").grid(row=0, column=3, sticky="nsew")
            
            # 5. ACCIONES (Centrado)
            f_btn = ctk.CTkFrame(row, fg_color="transparent")
            f_btn.grid(row=0, column=4, sticky="nsew")
            btn_wrapper = ctk.CTkFrame(f_btn, fg_color="transparent")
            btn_wrapper.pack(expand=True)
            
            if uid != database_core.CURRENT_USER_ID:
                if not is_locked:
                    if force_lock: # Si ya está expulsado, mostramos botón azul de Restaurar
                        ctk.CTkButton(btn_wrapper, text="✅ Restaurar", fg_color="#3B82F6", hover_color="#2563EB", text_color="white", width=85, height=28, font=ctk.CTkFont(size=11, weight="bold"), command=lambda id_u=uid: self._kick_action(id_u, restore=True)).pack(side="left", padx=4)
                    else: # Si está normal, mostramos botón naranja de Expulsar
                        ctk.CTkButton(btn_wrapper, text="🛑 Expulsar", fg_color="#F59E0B", hover_color="#D97706", text_color="white", width=80, height=28, font=ctk.CTkFont(size=11, weight="bold"), command=lambda id_u=uid: self._kick_action(id_u, restore=False)).pack(side="left", padx=4)

                if is_locked:
                    ctk.CTkButton(btn_wrapper, text="🔓 Desbloquear", fg_color="#10B981", hover_color="#059669", text_color="white", width=95, height=28, font=ctk.CTkFont(size=11, weight="bold"), command=lambda id_u=uid: self._lock_action(id_u, False)).pack(side="left", padx=4)
                else:
                    ctk.CTkButton(btn_wrapper, text="🚫 Bloquear", fg_color="#ef4444", hover_color="#dc2626", text_color="white", width=80, height=28, font=ctk.CTkFont(size=11, weight="bold"), command=lambda id_u=uid: self._lock_action(id_u, True)).pack(side="left", padx=4)
            else:
                ctk.CTkLabel(btn_wrapper, text="(ERES TÚ)", text_color="#94a3b8", font=ctk.CTkFont(size=11, weight="bold")).pack()

    def _lock_action(self, user_id, lock_state=True):
        """Acción de bloquear/desbloquear usuario"""
        if lock_state:
            msg = "¿BLOQUEAR permanentemente el acceso a este usuario?\n\nNo podrá ingresar hasta que lo desbloquees."
        else:
            msg = "¿Desbloquear a este usuario para que pueda volver a entrar?"
            
        if msgbox.askyesno("Confirmar Acción", msg):
            def exe():
                success = database_core.set_user_lock(user_id, lock_state, kick_only=False)
                if success and self.winfo_exists():
                    self.after(1000, self._load_admin_data)  # Recargar
                elif not success:
                    self.after(0, lambda: msgbox.showerror("Error", "No se pudo ejecutar la acción. Verifica tu conexión."))
                    
            threading.Thread(target=exe, daemon=True).start()

    def _kick_action(self, user_id, restore=False):
        if restore:
            msg = "¿Quitar el estado de EXPULSADO a este usuario?\n\n(Nota: Si el usuario vuelve a iniciar sesión, esto se quita automáticamente)."
        else:
            msg = ("¿Expulsar a este usuario de su sesión actual?\n\n"
                   "El usuario verá un mensaje de mantenimiento y será desconectado inmediatamente.\n"
                   "Podrá volver a entrar si no está bloqueado.")
               
        if msgbox.askyesno("Confirmar Acción", msg):
            def exe():
                if restore:
                    success = database_core.clear_kick_status(user_id)
                else:
                    success = database_core.set_user_lock(user_id, lock_state=False, kick_only=True)
                    
                if success and self.winfo_exists():
                    self.after(1000, self._load_admin_data)
            threading.Thread(target=exe, daemon=True).start()

    def _mass_action(self, action_type):
        """Manejador para las acciones globales (Afecta a todos menos a ti)."""
        messages = {
            "restaurar": "¿Quitar la marca de EXPULSADO a todos los usuarios?",
            "expulsar": "⚠️ ¿EXPULSAR A TODOS LOS EJECUTIVOS DE LA APP?\n\nPerderán su sesión al instante.",
            "desbloquear": "¿Desbloquear a todos los usuarios para que puedan volver a ingresar?",
            "bloquear": "🚫 ¿BLOQUEAR PERMANENTEMENTE A TODOS LOS USUARIOS?\n\nNadie podrá acceder hasta que los desbloquees."
        }
        
        if msgbox.askyesno("Confirmar Acción Global", messages[action_type]):
            def exe():
                import json
                from urllib import request as urllib_req
                
                # Preparamos el payload dependiendo del botón presionado
                payload = {}
                if action_type == "restaurar": payload = {"force_logout": False}
                elif action_type == "expulsar": payload = {"force_logout": True}
                elif action_type == "desbloquear": payload = {"is_locked": False}
                elif action_type == "bloquear": payload = {"is_locked": True, "force_logout": True}

                try:
                    # 'neq' significa "Not Equal" -> A todos los que NO sean yo
                    url = f"{database_core.SUPABASE_URL}/rest/v1/usuarios?id=neq.{database_core.CURRENT_USER_ID}"
                    data = json.dumps(payload).encode('utf-8')
                    req = urllib_req.Request(url, data=data, method='PATCH', headers={
                        "apikey": database_core.SUPABASE_KEY, 
                        "Authorization": f"Bearer {database_core.SUPABASE_KEY}", 
                        "Content-Type": "application/json"
                    })
                    urllib_req.urlopen(req, timeout=5)
                except Exception as e:
                    print(f"[Admin] Error en acción masiva: {e}")
                    
                # Recargar la tabla si la ventana sigue abierta
                if self.winfo_exists():
                    self.after(1000, self._load_admin_data)
                    
            threading.Thread(target=exe, daemon=True).start()

    def _create_row(self, parent, index, vals, status_color=None, payload_json=None, tipo_detalle="gestion"):
        bg = "#ffffff" if index % 2 == 0 else "#f0f2f5"
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=4, height=35)
        row.pack(fill="x", padx=4, pady=1)
        row.pack_propagate(False)
        
        # Dibujamos las celdas de texto normales
        for i, v in enumerate(vals):
            tc = status_color if (i == 1 and status_color) else "#333"
            ctk.CTkLabel(row, text=str(v), font=ctk.CTkFont(size=10, weight="bold" if i==1 else "normal"), text_color=tc).pack(side="left", expand=True, fill="x", padx=8, pady=4)
            
        # Botón de detalles (Si hay JSON o si es tipo Llamada)
        f_btn = ctk.CTkFrame(row, fg_color="transparent")
        f_btn.pack(side="left", expand=True, fill="x", padx=8)
        
        if tipo_detalle == "gestion":
            if payload_json and str(payload_json).strip() != "":
                ctk.CTkButton(f_btn, text="📄 Ver Gestión", width=100, height=24, fg_color="#3B82F6", hover_color="#2563EB", text_color="white", font=ctk.CTkFont(size=10, weight="bold"),
                              command=lambda js=payload_json: self._show_resumen_modal(js, "Detalle de Gestión Registrada")).pack(pady=4)
            else:
                ctk.CTkLabel(f_btn, text="Sin resumen", text_color="#94a3b8", font=ctk.CTkFont(size=10, slant="italic")).pack(pady=4)
        
        elif tipo_detalle == "llamada":
            # --- CORRECCIÓN: Armamos un diccionario real y dejamos que json lo convierta de forma segura ---
            import json
            diccionario_llamada = {
                "Teléfono": vals[0],
                "Fecha": vals[1],
                "Duración": vals[2],
                "Archivo Local": vals[3]
            }
            # Si el array `vals` viene con más datos (como el cliente y el lote que pediste antes),
            # deberías ajustar las posiciones aquí. Si tu array solo trae 4 cosas, esto está perfecto.
            
            json_llamada = json.dumps(diccionario_llamada)
            
            ctk.CTkButton(f_btn, text="📞 Ver Llamada", width=100, height=24, fg_color="#10B981", hover_color="#059669", text_color="white", font=ctk.CTkFont(size=10, weight="bold"),
                          command=lambda js=json_llamada: self._show_resumen_modal(js, "Detalle de Llamada Realizada")).pack(pady=4)
                
        return row

    def _show_resumen_modal(self, json_string, titulo):
        """Muestra una ventana flotante limpia con el desglose de detalles."""
        try:
            import json
            datos = json.loads(json_string)
        except Exception as e:
            msgbox.showerror("Error", f"No se pudo leer la información: {e}")
            return
            
        modal = ctk.CTkToplevel(self)
        modal.title("Auditoría de Actividad")
        modal.geometry("600x550")
        modal.configure(fg_color="#011536")
        modal.transient(self.winfo_toplevel())
        
        modal.update_idletasks()
        w, h = 600, 550
        x = modal.winfo_screenwidth() // 2 - w // 2
        y = modal.winfo_screenheight() // 2 - h // 2
        modal.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(modal, text=f"📋 {titulo}", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(pady=(20, 10))
        
        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=10)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Iterar sobre las llaves del JSON para dibujarlas ordenadas
        for k, v in datos.items():
            # Si el valor es el comentario gigante, lo ponemos abajo ocupando todo el ancho
            if k == "Comentario":
                ctk.CTkLabel(scroll, text="💬 Comentarios del Ejecutivo:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#011536", anchor="w").pack(fill="x", pady=(15,5))
                box = ctk.CTkTextbox(scroll, height=80, fg_color="#f1f5f9", text_color="#334155", font=ctk.CTkFont(size=12))
                box.insert("1.0", str(v))
                box.configure(state="disabled")
                box.pack(fill="x", pady=(0, 10))
                continue

            row = ctk.CTkFrame(scroll, fg_color="#f8fafc", corner_radius=6, border_width=1, border_color="#e2e8f0")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=f"{k}:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155", width=140, anchor="w").pack(side="left", padx=10, pady=8)
            
            # Color verde para los "SÍ", rojo para "NO"
            val_col = "#10B981" if str(v).upper() == "SÍ" else ("#ef4444" if str(v).upper() == "NO" else "#0f172a")
            
            # Entry copiable
            val_entry = ctk.CTkEntry(row, fg_color="transparent", border_width=0, text_color=val_col, font=ctk.CTkFont(size=13, weight="bold"))
            val_entry.insert(0, str(v))
            val_entry.configure(state="readonly")
            val_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=8)

        ctk.CTkButton(modal, text="✖ Cerrar", command=modal.destroy, width=200, height=40, fg_color="#ef4444", hover_color="#dc2626", font=ctk.CTkFont(weight="bold")).pack(pady=(0, 20))