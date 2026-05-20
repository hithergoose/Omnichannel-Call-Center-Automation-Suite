import customtkinter as ctk
import database_core
from tkinter import messagebox

class EditContactModal(ctk.CTkToplevel):
    def __init__(self, parent, contact_data, on_save_callback):
        super().__init__(parent)
        self.title(f"Editar Contacto: {contact_data.get('ncliente', 'Sin Nombre')}")
        self.geometry("500x600")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#011536")
        
        self.contact_data = contact_data
        self.on_save_callback = on_save_callback
        
        self.update_idletasks()
        w, h = 500, 600
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (w // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text="📝 Editar Información de Contacto", 
                    font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(pady=20)
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.entries = {}
        fields = [
            ("ncliente", "Nombre del Cliente"), ("ccelular", "Celular"),
            ("cfijo", "Teléfono Fijo"), ("cemail", "Email"),
            ("calle", "Calle"), ("numExt", "Num. Ext"),
            ("colonia", "Colonia"), ("municipio", "Municipio"),
            ("estado", "Estado"), ("cod_post", "Código Postal")
        ]
        
        for key, label in fields:
            ctk.CTkLabel(self.scroll, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(anchor="w", pady=(10, 0))
            entry = ctk.CTkEntry(self.scroll, width=400, placeholder_text=label)
            entry.insert(0, str(contact_data.get(key, "")))
            entry.pack(pady=(2, 5))
            self.entries[key] = entry
            
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20, padx=40)
        
        ctk.CTkButton(btn_frame, text="Cancelar", fg_color="#475569", hover_color="#334155", 
                     width=100, command=self.destroy).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="✅ Guardar Cambios", fg_color="#10B981", hover_color="#059669", 
                     width=200, command=self._save).pack(side="right", padx=10)

    def _save(self):
        new_data = {k: e.get().strip() for k, e in self.entries.items()}
        id_local = self.contact_data.get('id')
        
        if not id_local:
            messagebox.showerror("Error", "No se encontró el ID local del contacto.")
            return
            
        if database_core.update_contacto(id_local, new_data):
            messagebox.showinfo("Éxito", "Información actualizada correctamente.")
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        else:
            messagebox.showerror("Error", "No se pudo actualizar la base de datos local.")

class ContactDetailsModal(ctk.CTkToplevel):
    def __init__(self, parent, contact_data):
        super().__init__(parent)
        self.title("Ficha Técnica del Cliente")
        # Ajustar altura al 90% de la pantalla para evitar que se corte
        h = int(self.winfo_screenheight() * 0.9)
        self.geometry(f"850x{h}")
        self.configure(fg_color="#011536") 
        #self.transient(parent) # Asociar con ventana principal pero no bloquear

        self.update_idletasks()
        w = 850
        x = 15 # Pegado a la izquierda
        y = 15 # Pegado arriba
        self.geometry(f"+{x}+{y}")

        def fmt_money(val):
            if val is None or str(val).strip() == "" or str(val) == "None":
                return "$0.00"
            try:
                num = float(str(val).replace('$', '').replace(',', '').strip())
                return f"${num:,.2f}"
            except:
                return str(val)

        card = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=15)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header, text="👤", font=ctk.CTkFont(size=50)).pack(side="left", padx=(0, 15))
        
        info_frame = ctk.CTkFrame(header, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)
        
        ncliente = str(contact_data.get('ncliente', 'Cliente Desconocido')).upper()
        lote = str(contact_data.get('lote', 'Sin Lote')).upper()
        asesor = str(contact_data.get('asesorNombre', 'SIN ASESOR ASIGNADO')).upper()
        nestatus = str(contact_data.get('nestatus', 'SIN ESTATUS')).upper()
        
        nom_entry = ctk.CTkEntry(info_frame, fg_color="transparent", border_width=0, text_color="#0f172a", font=ctk.CTkFont(size=24, weight="bold"))
        nom_entry.insert(0, ncliente)
        nom_entry.configure(state="readonly")
        nom_entry.pack(fill="x", pady=(5,0))
        
        lote_entry = ctk.CTkEntry(info_frame, fg_color="transparent", border_width=0, text_color="#2b64d3", font=ctk.CTkFont(size=14, weight="bold"))
        lote_entry.insert(0, f"LOTE: {lote}   |   ASESOR: {asesor}")
        lote_entry.configure(state="readonly")
        lote_entry.pack(fill="x")
        
        ST_MOROSO = ["MOROSO", "VENCIDO", "COBRANZA"]
        ST_RIESGO = ["ATRASO", "PENDIENTE"]
        ST_OK     = ["AL CORRIENTE", "LIQUIDADO"]
        
        bg_col = "#e2e8f0"; txt_col = "#334155" 
        if nestatus in ST_MOROSO: bg_col = "#fee2e2"; txt_col = "#991b1b" 
        elif nestatus in ST_RIESGO: bg_col = "#fef3c7"; txt_col = "#92400e" 
        elif nestatus in ST_OK: bg_col = "#d1fae5"; txt_col = "#166534" 

        badge = ctk.CTkLabel(header, text=nestatus, font=ctk.CTkFont(size=13, weight="bold"), text_color=txt_col, fg_color=bg_col, corner_radius=8, padx=15, pady=8)
        badge.pack(side="right", anchor="n", pady=5)

        ctk.CTkFrame(card, fg_color="#e2e8f0", height=2).pack(fill="x", padx=20, pady=5)

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        def build_section(title, data_dict, icon_color="#2b64d3"):
            sec = ctk.CTkFrame(scroll, fg_color="transparent")
            sec.pack(fill="x", pady=(10, 15), padx=10)
            
            ctk.CTkLabel(sec, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color="#011536", anchor="w").pack(fill="x", pady=(0, 10))
            
            grid = ctk.CTkFrame(sec, fg_color="transparent")
            grid.pack(fill="x")
            
            row_frame = None
            valid_items = [(k, v) for k, v in data_dict.items() if v is not None and str(v).strip() != "" and str(v) != "None"]
            
            for i, (k, v) in enumerate(valid_items):
                if i % 2 == 0:
                    row_frame = ctk.CTkFrame(grid, fg_color="transparent")
                    row_frame.pack(fill="x", pady=5)
                    
                cell = ctk.CTkFrame(row_frame, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#cbd5e1")
                cell.pack(side="left", expand=True, fill="both", padx=6)
                
                ctk.CTkLabel(cell, text=k, font=ctk.CTkFont(size=12, weight="bold"), text_color=icon_color, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
                
                val_entry = ctk.CTkEntry(cell, fg_color="transparent", border_width=0, text_color="#0f172a", font=ctk.CTkFont(size=15, weight="bold"))
                val_entry.insert(0, str(v))
                val_entry.configure(state="readonly")
                val_entry.pack(fill="x", padx=6, pady=(0, 10))

        dict_contacto = {
            "📱 Teléfono Celular": contact_data.get("ccelular"),
            "📞 Teléfono Fijo": contact_data.get("cfijo")
        }
        
        dict_finanzas = {
            "🛠️ Adeudo Mantenimiento": fmt_money(contact_data.get("adeudo")),
            "⏳ Moratorios": fmt_money(contact_data.get("adeudoM")),
            "💸 Otros Adeudos": fmt_money(contact_data.get("adeudo_otros")),
            "💰 Adeudo Total": fmt_money(contact_data.get("totalAdeudo")),
            "📊 Adeudo Total + Otros Adeudos": fmt_money(contact_data.get("totalAdeudoLL")),
            "📅 Meses de Adeudo": contact_data.get("mesesadeudo"),
            "💳 Costo Anualidad": fmt_money(contact_data.get("anualidad"))
        }
        
        dict_historial = {
            "📝 Última Gestión": contact_data.get("ugestion"),
            "💵 Último Pago": contact_data.get("fultpago"),
            "🏗️ Estatus Terreno": contact_data.get("statusterreno"),
            "🏦 Fecha Fondo Reserva": contact_data.get("fechaFondoReserva"),
            "🗓️ Fecha 1er Mensualidad": contact_data.get("fecha1erMensMtto")
        }

        build_section("Información de Contacto", dict_contacto, icon_color="#2b64d3")
        build_section("Estado Financiero", dict_finanzas, icon_color="#059669")
        build_section("Historial y Estatus", dict_historial, icon_color="#ea580c")

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        # Botón de calculadora FLOTA ahora sobre el botón de cerrar
        def open_calc():
            CalculadoraModal(self, contact_data)
            
        calc_btn = ctk.CTkButton(card, text="🧮", width=50, height=50, corner_radius=25,
                                 fg_color="#F59E0B", hover_color="#D97706", command=open_calc)
        calc_btn.place(relx=0.98, rely=0.98, anchor="se")
        
        ctk.CTkButton(btn_frame, text="✖ CERRAR FICHA", command=self.destroy, width=220, height=45, corner_radius=8,
                      fg_color="#ef4444", hover_color="#dc2626", text_color="white", font=ctk.CTkFont(size=14, weight="bold")).pack()

class CalculadoraModal(ctk.CTkToplevel):
    def __init__(self, parent, contact_data):
        super().__init__(parent)
        self.title("Simulador de Pagos GPH")
        h = int(self.winfo_screenheight() * 0.9)
        self.geometry(f"600x{h}")
        self.configure(fg_color="#011536")
        #self.transient(parent)
        #self.grab_set()

        self.contact_data = contact_data
        
        # --- CORRECCIÓN DE POSICIÓN ---
        self.update_idletasks()
        w = 600
        # Pegarlo justo a la derecha de la ventana "Ficha Técnica del Cliente"
        x = parent.winfo_x() + parent.winfo_width() + 550 
        # Si se sale de la pantalla por la derecha, lo ajustamos al borde de la pantalla
        if (x + w) > self.winfo_screenwidth():
            x = self.winfo_screenwidth() - w + 200
        y = parent.winfo_y() # Misma altura que la ficha técnica
        self.geometry(f"+{x}+{y}")
        
        # --- VARIABLES BASE DE CÁLCULO ---
        self.anualidad = database_core.normalize_numeric(contact_data.get("anualidad", 0))
        self.mensualidad_base = round(self.anualidad / 10.8, 2) if self.anualidad > 0 else 770.0
        self.adeudo_mtto = database_core.normalize_numeric(contact_data.get("adeudo", 0))
        self.moratorios_base = database_core.normalize_numeric(contact_data.get("adeudoM", 0))
        self.otros_adeudos = database_core.normalize_numeric(contact_data.get("adeudo_otros", 0))
        
        # --- VARIABLES DE INTERFAZ REACTIVA (CORRECCIÓN) ---
        self.var_sumar_mes_actual = ctk.BooleanVar(value=False)
        self.var_sumar_anualidad = ctk.BooleanVar(value=False)
        self.var_num_mensualidades = ctk.StringVar(value="1")
        self.var_descuento_mes = ctk.StringVar(value="0")
        self.var_descuento_moratorios = ctk.StringVar(value="0")

        # Variables para los resultados que cambian dinámicamente
        self.var_res_mensualidad = ctk.StringVar(value="$0.00")
        self.var_res_moratorios = ctk.StringVar(value="$0.00")
        self.var_res_saldo_vencido = ctk.StringVar(value="$0.00")
        self.var_res_total = ctk.StringVar(value="$0.00")

        # --- ESTRUCTURA VISUAL ---
        ctk.CTkLabel(self, text="🧮 Simulador de Pagos", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=20)
        
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20)

        # --- SECCIÓN: PAGO DEL MES ACTUAL ---
        card_mes = self._card(scroll, "Pago de Mensualidades Corrientes")
        
        self._row_static(card_mes, "Mensualidad Base:", f"${self.mensualidad_base:,.2f}")
        self._row_input(card_mes, "Número de Mensualidades:", self.var_num_mensualidades)
        self._row_input(card_mes, "Descuento Pronto Pago (%):", self.var_descuento_mes)
        self._row_result(card_mes, "Total Mensualidades (con desc.):", self.var_res_mensualidad, color="#3B82F6")
        
        # --- SECCIÓN: SALDO VENCIDO ---
        card_vencido = self._card(scroll, "Liquidación de Saldo Vencido")
        
        self._row_static(card_vencido, "Adeudo Mantenimiento:", f"${self.adeudo_mtto:,.2f}")
        self._row_static(card_vencido, "Moratorios (Original):", f"${self.moratorios_base:,.2f}")
        self._row_static(card_vencido, "Otros Adeudos:", f"${self.otros_adeudos:,.2f}")
        
        ctk.CTkFrame(card_vencido, fg_color="#334155", height=1).pack(fill="x", padx=10, pady=10)

        self._row_input(card_vencido, "Descuento en Moratorios (%):", self.var_descuento_moratorios)
        self._row_result(card_vencido, "Moratorios con Descuento:", self.var_res_moratorios, color="white")
        self._row_result(card_vencido, "Total Saldo Vencido:", self.var_res_saldo_vencido, color="#F59E0B")

        # --- SECCIÓN: ADEUDO FINAL (SUMA CONDICIONAL) ---
        card_total = self._card(scroll, "Cálculo de Adeudo Final")
        
        # Agregamos comandos a los checkboxes para que recalculen al darles clic
        ctk.CTkCheckBox(card_total, text="Sumar Mensualidades (Pronto-pago)", variable=self.var_sumar_mes_actual, 
                        command=self.update_calculations, font=ctk.CTkFont(size=13), text_color="white").pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkCheckBox(card_total, text=f"Sumar Anualidad (${self.anualidad:,.2f})", variable=self.var_sumar_anualidad, 
                        command=self.update_calculations, font=ctk.CTkFont(size=13), text_color="white").pack(anchor="w", padx=10, pady=5)
                        
        ctk.CTkFrame(card_total, fg_color="#334155", height=2).pack(fill="x", padx=10, pady=15)
        
        # Total Final Gigante
        row_tot = ctk.CTkFrame(card_total, fg_color="transparent")
        row_tot.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(row_tot, text="TOTAL A PAGAR:", font=ctk.CTkFont(size=18, weight="bold"), text_color="#10B981").pack(side="left")
        
        entry_total = ctk.CTkEntry(row_tot, textvariable=self.var_res_total, font=ctk.CTkFont(size=36, weight="bold"), 
                                   fg_color="transparent", text_color="#10B981", border_width=0, justify="right")
        entry_total.configure(state="readonly")
        entry_total.pack(side="right", fill="x", expand=True)

        # Botón de cierre
        ctk.CTkButton(self, text="Cerrar Simulador", command=self.destroy, height=45, fg_color="#ef4444", hover_color="#dc2626").pack(pady=20)
        
        # Ejecutar el cálculo inicial
        self.update_calculations()

    # --- FUNCIONES DE DIBUJO ---
    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=10, border_width=1, border_color="#334155")
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkFrame(card, fg_color="#334155", height=1).pack(fill="x", padx=10, pady=(0, 10))
        return card

    def _row_static(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13), text_color="white", anchor="w").pack(side="left", expand=True, fill="x")
        
        entry = ctk.CTkEntry(row, width=150, justify="right", font=ctk.CTkFont(size=13, weight="bold"), fg_color="transparent", text_color="white", border_width=0)
        entry.insert(0, str(value))
        entry.configure(state="readonly")
        entry.pack(side="right")

    def _row_input(self, parent, label, var):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)
        
        # Etiqueta (Lado izquierdo)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13), text_color="white", anchor="w").pack(side="left", expand=True, fill="x")
        
        # Contenedor derecho para la papelera y el input
        right_container = ctk.CTkFrame(row, fg_color="transparent")
        right_container.pack(side="right")

        # Función para limpiar el campo y recalcular
        def clear_field():
            var.set("") # Borrar contenido
            self.update_calculations() # Disparar recálculo

        # Botón de papelera
        btn_trash = ctk.CTkButton(right_container, text="🗑️", width=30, height=28, fg_color="#ef4444", hover_color="#dc2626", command=clear_field)
        btn_trash.pack(side="left", padx=(0, 5))
        
        # Campo de entrada
        entry = ctk.CTkEntry(right_container, textvariable=var, width=65, justify="right", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#0b1120", text_color="white")
        entry.pack(side="left")
        
        # Enlazar cualquier tecla presionada para que recalcule
        entry.bind("<KeyRelease>", self.update_calculations)

    def _row_result(self, parent, label, var, color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=color, anchor="w").pack(side="left", expand=True, fill="x")
        
        entry = ctk.CTkEntry(row, textvariable=var, width=150, justify="right", font=ctk.CTkFont(size=14, weight="bold"), fg_color="transparent", text_color=color, border_width=0)
        entry.configure(state="readonly")
        entry.pack(side="right")

    # --- LÓGICA MATEMÁTICA ---
    def update_calculations(self, event=None):
        # 1. Cálculo Mensualidad
        try:
            num_mens = int(self.var_num_mensualidades.get() or "0")
            if num_mens < 0: num_mens = 0
        except: num_mens = 0
        
        total_mens_base = self.mensualidad_base * num_mens
        
        try:
            desc_mes_pct = float(self.var_descuento_mes.get() or "0") / 100
        except: desc_mes_pct = 0
            
        desc_mes_val = total_mens_base * desc_mes_pct
        mens_final = total_mens_base - desc_mes_val
        self.var_res_mensualidad.set(f"${mens_final:,.2f}")
        
        # 2. Cálculo Moratorios
        try:
            desc_mora_pct = float(self.var_descuento_moratorios.get() or "0") / 100
        except: desc_mora_pct = 0
            
        desc_mora_val = self.moratorios_base * desc_mora_pct
        mora_final = self.moratorios_base - desc_mora_val
        self.var_res_moratorios.set(f"${mora_final:,.2f}")
        
        # 3. Saldo Vencido Total
        saldo_vencido = self.adeudo_mtto + mora_final + self.otros_adeudos
        self.var_res_saldo_vencido.set(f"${saldo_vencido:,.2f}")
        
        # 4. Total a Pagar
        total = saldo_vencido
        if self.var_sumar_mes_actual.get():
            total += mens_final
        if self.var_sumar_anualidad.get():
            total += self.anualidad
            
        self.var_res_total.set(f"${total:,.2f}")