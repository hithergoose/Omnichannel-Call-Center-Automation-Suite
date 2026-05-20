import customtkinter as ctk
import tkinter.ttk as ttk
import tkinter as tk
import os
import json
import re
import subprocess
import database_core
import threading
import urllib.request
import time
from datetime import datetime
from tkinter import messagebox
import requests
import api_gph
from database_core import AppState, safe_execute
import sync_logger
import ui_modals
import utils_export

class SyncProgressDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sincronización GPH")
        self.geometry("500x350")
        self.configure(fg_color="#011536")
        self.attributes("-topmost", True) # Ventana al frente
        
        ctk.CTkLabel(self, text="Sincronizando...", font=ctk.CTkFont(size=16, weight="bold"), text_color="white").pack(pady=10)
        
        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.pack(pady=10)
        
        self.log_text = ctk.CTkTextbox(self, width=450, height=120, fg_color="#0b1120", text_color="#10B981")
        self.log_text.pack(pady=10)
        self.log_text.insert("0.0", "Iniciando proceso...\n")
        self.log_text.configure(state="disabled")

        # Botón desactivado inicialmente
        self.done_btn = ctk.CTkButton(self, text="Cerrar", fg_color="#64748b", command=self.destroy, state="disabled")
        self.done_btn.pack(pady=10)

    def log(self, message):
        if not self.winfo_exists(): return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def update_progress(self, percent, message):
        if not self.winfo_exists(): return
        self.progress.set(percent)
        self.log(message)

    def on_sync_complete(self, success=True, error_msg=None):
        if not self.winfo_exists(): return
        
        # Cambiamos el título de la ventana y el texto principal
        self.log("------------------------------------------")
        if success:
            self.progress.set(1.0)
            self.log("✅ PROCESO FINALIZADO CON ÉXITO.")
            self.done_btn.configure(state="normal", fg_color="#10B981")
        else:
            self.log(f"❌ PROCESO FINALIZADO CON ERRORES: {error_msg}")
            self.done_btn.configure(state="normal", fg_color="#EF4444")

class FilterCombo(ctk.CTkFrame):
    def __init__(self, master, label, key, callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.key = key
        self.callback = callback
        self.all_values = []
        self.loaded = False
        
        ctk.CTkLabel(self, text=label.upper(), font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(anchor="w")
        
        self.combo = ttk.Combobox(self, font=("Segoe UI", 10))
        self.combo.pack(fill="x", pady=2)
        
        self.combo.bind("<FocusIn>", self._load_values)
        self.combo.bind("<KeyRelease>", self._on_key)
        self.combo.bind("<Return>", lambda e: self.callback())

    def _load_values(self, event=None):
        if self.loaded: return
        def task():
            try:
                import database_core
                vals = database_core.get_unique_values(self.key)
                self.all_values = sorted([str(v) for v in vals if v])
                self.after(0, self._refresh_ui)
            except Exception as e:
                print(f"[FilterCombo] Error loading {self.key}: {e}")
            
        threading.Thread(target=task, daemon=True).start()
        self.loaded = True

    def _refresh_ui(self):
        self.combo["values"] = self.all_values[:100]

    def _on_key(self, event):
        if event.keysym in ["Return", "Escape", "Tab"]: return
        if not self.loaded: self._load_values()
        
        val = self.combo.get().lower()
        if not val:
            self.combo["values"] = self.all_values
            return
        
        # Filtrado predictivo
        if "," in val: return # Dejar multi-select manual libre
        
        filtered = [v for v in self.all_values if val in v.lower()]
        self.combo["values"] = filtered[:100]
        try:
            self.combo.event_generate('<Down>') # Abrir dropdown si hay sugerencias
        except: pass

    def get(self):
        return self.combo.get().strip()

    def clear(self):
        self.combo.set("")

class GestionForm(ctk.CTkToplevel):
    C_BG      = "#0B1120"
    C_CARD    = "#131B2E"
    C_ACCENT  = "#3B82F6"
    C_ACCENT2 = "#10B981"
    C_SURFACE = "#1E293B"
    C_BORDER  = "#334155"
    C_TEXT    = "#E2E8F0"
    C_MUTED   = "#94A3B8"
    C_CHIP    = "#1D4ED8"

    MEDIOS =["ALERTA CAJA","ENVÍO DE CORREO ELECTRÓNICO","ENVÍO DE MENSAJE DE WHATSAPP",
              "LLAMADA TELEFÓNICA","VISITA A DOMICILIO","VISITA A OFICINA"]
    FPAGO  =["CAJA/EFECTIVO","CAJA/CHEQUE","CAJA/TARJETA","TEA",
              "PAGINA CIUDAD MADERAS","DOMICILIADOS","TRANSFERENCIA"]

    def __init__(self, master, filepath, call_number="", call_start=None, call_duration=0, contact_info=None, is_short_call=False):
        super().__init__(master)
        self.filepath = filepath
        self.call_number = call_number
        self.call_start = call_start or datetime.now()
        self.call_duration = call_duration
        self.contact_info = contact_info or {}
        self.selected_names =[]
        
        self.title("Gestión Post-Llamada")
        self.geometry("800x720")
        self.configure(fg_color=self.C_BG)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.update_idletasks()
        w, h = 800, 720
        x = master.winfo_x() + (master.winfo_width() // 2) - (w // 2)
        y = master.winfo_y() + 20 
        if y < 10: y = 10
        self.geometry(f"+{x}+{y}")

        self.catalogos = database_core.get_catalogos() or {}

        hdr = ctk.CTkFrame(self, fg_color=self.C_ACCENT, corner_radius=0, height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📋 Registrar Seguimiento", font=ctk.CTkFont(size=15, weight="bold"), text_color="#fff").pack(side="left", padx=14)
        ctk.CTkLabel(hdr, text=datetime.now().strftime("%d/%m/%Y"), font=ctk.CTkFont(size=11), text_color="#dbeafe").pack(side="right", padx=14)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=self.C_BG, scrollbar_button_color=self.C_BORDER)
        self.scroll.pack(fill="both", expand=True)

        self.descuentos_list = self.catalogos.get('tipo_descuento',[])
        if not self.descuentos_list and isinstance(self.catalogos.get('data'), dict):
            self.descuentos_list = self.catalogos['data'].get('tipo_descuento',[])
        self.map_desc = {str(i.get('nombre','')): str(i.get('id_tipo','')) for i in self.descuentos_list if 'id_tipo' in i}
        n_desc = list(self.map_desc.keys()) or ["Sin descuentos"]

        raw = database_core.get_cartera()
        self.map_cartera = {}
        self.cliente_lotes = {}
        self.todos_clientes =[]
        for c in raw:
            v = c.get('vivienda',''); n = c.get('clienteNombre', c.get('clientenombre',''))
            self.map_cartera[v] = c.get('id_cobranza','')
            self.cliente_lotes.setdefault(n,[]).append(v)
        self.todos_clientes = sorted(set(self.cliente_lotes.keys()))

        c1 = self._card("Datos de la Gestión", "📞")
        
        row_basic1 = ctk.CTkFrame(c1, fg_color="transparent"); row_basic1.pack(fill="x", padx=14, pady=5)
        
        f_asunto = ctk.CTkFrame(row_basic1, fg_color="transparent"); f_asunto.pack(side="left", expand=True, fill="x")
        self._lbl(f_asunto, "Asunto")
        self.asunto_cmb = ctk.CTkComboBox(f_asunto, values=self.MEDIOS, width=280, fg_color=self.C_SURFACE, border_color=self.C_BORDER, text_color="white")
        self.asunto_cmb.set("LLAMADA TELEFÓNICA"); self.asunto_cmb.pack(padx=14, anchor="w")
        self.asunto_cmb.configure(state="disabled") 
        
        f_fecha = ctk.CTkFrame(row_basic1, fg_color="transparent"); f_fecha.pack(side="left", expand=True, fill="x")
        self._lbl(f_fecha, "Fecha de Operación")
        self.fecha_entry = ctk.CTkEntry(f_fecha, width=280, fg_color=self.C_SURFACE, border_color=self.C_BORDER, text_color="white")
        self.fecha_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.fecha_entry.configure(state="disabled") 
        self.fecha_entry.pack(padx=14, anchor="w")

        row_basic2 = ctk.CTkFrame(c1, fg_color="transparent"); row_basic2.pack(fill="x", padx=14, pady=5)
        self._lbl(row_basic2, "Nombre Cliente (puede agregar varios)")
        inp_row = ctk.CTkFrame(row_basic2, fg_color="transparent"); inp_row.pack(fill="x", padx=14, pady=(0,2))
        self.cliente_entry = ctk.CTkEntry(inp_row, placeholder_text="Escriba para buscar...", fg_color=self.C_SURFACE, border_color=self.C_BORDER, text_color="white")
        self.cliente_entry.pack(side="left", fill="x", expand=True)
        self.cliente_entry.bind("<KeyRelease>", self._on_key)

        self.sug_frame = ctk.CTkFrame(c1, fg_color=self.C_SURFACE, corner_radius=8, border_width=1, border_color=self.C_ACCENT)
        self.sug_list = tk.Listbox(self.sug_frame, height=5, font=("Segoe UI",10), bg="#1E293B", fg="#E2E8F0", selectbackground="#3B82F6", selectforeground="#fff", relief="flat", borderwidth=0, highlightthickness=0)
        self.sug_list.pack(fill="both", expand=True, padx=3, pady=3)
        self.sug_list.bind("<<ListboxSelect>>", self._on_select)

        self.chips_frame = ctk.CTkFrame(c1, fg_color="transparent")
        self.btn_buscar = ctk.CTkButton(c1, text="🔍 Buscar Propiedades", width=200, height=32, corner_radius=8, fg_color=self.C_ACCENT, hover_color="#2563EB", command=self._buscar_propiedades)
        self.btn_buscar.pack(padx=14, pady=(2,6), anchor="w")

        self.lotes_container = ctk.CTkFrame(c1, fg_color=self.C_SURFACE, corner_radius=8, border_width=1, border_color=self.C_BORDER)
        self.lote_vars =[]

        cc = database_core.AppState.current_client
        if cc and cc.get("valid"):
            if (datetime.now() - cc["ts"]).total_seconds() < 3600:
                nombre_pre = cc.get("nombre", "")
                if nombre_pre:
                    self.cliente_entry.insert(0, nombre_pre)
                    self._on_key(None)

        c2 = self._card("Resultado del Contacto", "🎯")
        row_opts = ctk.CTkFrame(c2, fg_color="transparent"); row_opts.pack(fill="x", padx=14, pady=(0,6))
        
        self.contacto_var = ctk.StringVar(value="NO")
        self.convenio_var = ctk.StringVar(value="NO")
        self.pago_var = ctk.StringVar(value="NO")

        self.c_col1 = ctk.CTkFrame(row_opts, fg_color="transparent")
        self.c_col1.pack(side="left", expand=True, fill="x")
        self._lbl(self.c_col1, "¿Se logró contactar?")
        f_cc = ctk.CTkFrame(self.c_col1, fg_color="transparent"); f_cc.pack(anchor="w", padx=14)
        ctk.CTkRadioButton(f_cc, text="SÍ", variable=self.contacto_var, value="SÍ", command=self._t_contacto, text_color="white").pack(side="left", padx=(0,10))
        ctk.CTkRadioButton(f_cc, text="NO", variable=self.contacto_var, value="NO", command=self._t_contacto, text_color="white").pack(side="left")

        self.c_col2 = ctk.CTkFrame(row_opts, fg_color="transparent")
        self._lbl(self.c_col2, "¿Se logró convenio?")
        f_cv = ctk.CTkFrame(self.c_col2, fg_color="transparent"); f_cv.pack(anchor="w", padx=14)
        ctk.CTkRadioButton(f_cv, text="SÍ", variable=self.convenio_var, value="SÍ", text_color="white").pack(side="left", padx=(0,10))
        ctk.CTkRadioButton(f_cv, text="NO", variable=self.convenio_var, value="NO", text_color="white").pack(side="left")

        self.c_col3 = ctk.CTkFrame(row_opts, fg_color="transparent")
        self._lbl(self.c_col3, "¿Realizó un pago?")
        f_cp = ctk.CTkFrame(self.c_col3, fg_color="transparent"); f_cp.pack(anchor="w", padx=14)
        ctk.CTkRadioButton(f_cp, text="SÍ", variable=self.pago_var, value="SÍ", command=self._t_pago, text_color="white").pack(side="left", padx=(0,10))
        ctk.CTkRadioButton(f_cp, text="NO", variable=self.pago_var, value="NO", command=self._t_pago, text_color="white").pack(side="left")

        self.fr_pago = ctk.CTkFrame(c2, fg_color=self.C_SURFACE, corner_radius=8, border_width=1, border_color=self.C_BORDER)
        
        r_f1 = ctk.CTkFrame(self.fr_pago, fg_color="transparent"); r_f1.pack(fill="x", pady=5)
        
        f_fpago = ctk.CTkFrame(r_f1, fg_color="transparent"); f_fpago.pack(side="left", expand=True, fill="x")
        self._lbl(f_fpago, "Forma de pago")
        self.fpago_cmb = ctk.CTkComboBox(f_fpago, values=self.FPAGO, width=250, fg_color=self.C_BG, button_color=self.C_ACCENT, text_color="white")
        self.fpago_cmb.pack(padx=14, anchor="w")
        
        f_cant = ctk.CTkFrame(r_f1, fg_color="transparent"); f_cant.pack(side="left", expand=True, fill="x")
        self._lbl(f_cant, "Cantidad ($)*")
        self.cantidad_entry = ctk.CTkEntry(f_cant, width=200, fg_color=self.C_BG, text_color="white")
        self.cantidad_entry.insert(0, "0"); self.cantidad_entry.pack(padx=14, anchor="w")
        
        r_f2 = ctk.CTkFrame(self.fr_pago, fg_color="transparent"); r_f2.pack(fill="x", pady=5)
        
        f_desc = ctk.CTkFrame(r_f2, fg_color="transparent"); f_desc.pack(side="left", expand=True, fill="x")
        self._lbl(f_desc, "Tipo Descuento")
        self.descuento_cmb = ctk.CTkComboBox(f_desc, values=n_desc, width=300, fg_color=self.C_BG, button_color=self.C_ACCENT, text_color="white")
        self.descuento_cmb.pack(padx=14, anchor="w")

        c3 = self._card("Evidencias Generales", "📎")
        
        self.rutas_evidencia = [self.filepath] if self.filepath and os.path.exists(self.filepath) else[]
        self.btn_ev = ctk.CTkButton(c3, text="➕ Agregar Evidencias Generales (Audios/Fotos)...", anchor="center", width=380, fg_color=self.C_SURFACE, border_width=1, text_color="white", command=self._cambiar_ev)
        self.btn_ev.pack(padx=14, pady=(8,8), anchor="w")
        
        self.files_frame = ctk.CTkFrame(c3, fg_color="transparent")
        self.files_frame.pack(fill="x", padx=14, pady=(0, 8))
        self._render_files()

        c4 = self._card("Comentarios del Ejecutivo", "💬")
        
        # NUEVO: Comentarios predeterminados (Supabase)
        self._lbl(c4, "Comentarios Predeterminados")
        preds = database_core.get_comentarios_predeterminados()
        self.libre_option = "(Escribir libre...)"
        self.preds_cmb = ctk.CTkComboBox(c4, values=[self.libre_option] + preds, width=300, 
                                        fg_color=self.C_SURFACE, border_color=self.C_BORDER, 
                                        text_color="white", command=self._on_pred_selected)
        self.preds_cmb.set(self.libre_option)
        self.preds_cmb.pack(padx=14, pady=(2, 8), anchor="w")

        self.text_coment = ctk.CTkTextbox(c4, width=700, height=60, fg_color=self.C_SURFACE, border_width=1, text_color="white")
        self.text_coment.pack(padx=14, pady=(5,10), anchor="w")
        if is_short_call:
            w_lbl = ctk.CTkLabel(c4, text="⚠️ LLAMADA CORTA: El audio no se guardó. Describe el motivo de forma clara.", text_color="#EF4444", font=ctk.CTkFont(weight="bold"))
            w_lbl.pack(before=self.text_coment, pady=(5, 5), padx=14, anchor="w")

        self.lbl_st = ctk.CTkLabel(self.scroll, text="", text_color=self.C_MUTED, font=ctk.CTkFont(size=11))
        self.lbl_st.pack(pady=(3,1))
        self.progress = ctk.CTkProgressBar(self.scroll, width=380, mode="indeterminate", progress_color=self.C_ACCENT, fg_color=self.C_SURFACE)
        
        btn_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_container.pack(pady=(4,14), fill="x", padx=14)
        self.btn_cancel = ctk.CTkButton(btn_container, text="❌ Cancelar", height=42, fg_color="#EF4444", hover_color="#B91C1C", text_color="white", command=self._cerrar_gestion)
        self.btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_save = ctk.CTkButton(btn_container, text="🚀 Guardar Gestión", height=42, fg_color=self.C_ACCENT2, hover_color="#059669", text_color="white", command=self._guardar)
        self.btn_save.pack(side="right", expand=True, fill="x", padx=(5, 0))

        self.original_client = None
        if cc and cc.get("valid"):
            if (datetime.now() - cc["ts"]).total_seconds() < 3600:
                self.original_client = cc.get("nombre", "").upper()
                if self.original_client:
                    self.selected_names.append(self.original_client)
                    self.cliente_entry.delete(0, tk.END)
                    self.sug_frame.pack_forget()
                    self._render_chips()

        self._t_contacto()

    def _render_files(self):
        for w in self.files_frame.winfo_children(): w.destroy()
        if not self.rutas_evidencia:
            ctk.CTkLabel(self.files_frame, text="Sin evidencias generales", text_color=self.C_MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
            return
        for f in self.rutas_evidencia:
            row = ctk.CTkFrame(self.files_frame, fg_color=self.C_SURFACE, corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📄 {os.path.basename(f)}", font=ctk.CTkFont(size=11), text_color="white").pack(side="left", padx=10, pady=4)
            ctk.CTkButton(row, text="✖", width=24, fg_color="#EF4444", text_color="white", command=lambda path=f: self._remove_file(path)).pack(side="right", padx=5)

    def _remove_file(self, path):
        if path in self.rutas_evidencia:
            self.rutas_evidencia.remove(path)
            self._render_files()

    def _cambiar_ev(self):
        import tkinter.filedialog as fd
        rutas = fd.askopenfilenames(title="Seleccionar Evidencia General", filetypes=[("Archivos","*.mp3 *.wav *.pdf *.jpg *.png"),("Todos","*.*")])
        if rutas:
            for r in rutas:
                if r not in self.rutas_evidencia: self.rutas_evidencia.append(r)
            self._render_files()

    def _on_pred_selected(self, val):
        if val == self.libre_option:
            self.text_coment.configure(state="normal")
            # Opcional: limpiar si antes habia un predeterminado
            # self.text_coment.delete("1.0", "end")
        else:
            self.text_coment.configure(state="normal")
            self.text_coment.delete("1.0", "end")
            self.text_coment.insert("1.0", val)
            self.text_coment.configure(state="disabled")

    def _card(self, title, icon=""):
        c = ctk.CTkFrame(self.scroll, fg_color=self.C_CARD, corner_radius=10, border_width=1, border_color=self.C_BORDER)
        c.pack(fill="x", padx=12, pady=(8,3))
        h = ctk.CTkFrame(c, fg_color="transparent"); h.pack(fill="x", padx=14, pady=(10,4))
        ctk.CTkLabel(h, text=f"{icon}  {title}", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.C_TEXT).pack(side="left")
        return c

    def _lbl(self, p, t):
        ctk.CTkLabel(p, text=t, font=ctk.CTkFont(size=11), text_color=self.C_MUTED).pack(padx=14, pady=(3,1), anchor="w")

    def _t_contacto(self):
        if self.contacto_var.get() == "SÍ":
            self.c_col2.pack(side="left", expand=True, fill="x", after=self.c_col1)
            self.c_col3.pack(side="left", expand=True, fill="x", after=self.c_col2)
            self._t_pago()
        else: 
            self.c_col2.pack_forget()
            self.c_col3.pack_forget()
            self.fr_pago.pack_forget()

    def _t_pago(self):
        if self.pago_var.get() == "SÍ" and self.contacto_var.get() == "SÍ":
            self.fr_pago.pack(fill="x", padx=10, pady=(5,10))
        else: 
            self.fr_pago.pack_forget()

    def _on_key(self, e=None):
        t = self.cliente_entry.get().strip().upper()
        self.sug_list.delete(0, tk.END)
        if len(t) < 2: self.sug_frame.pack_forget(); return
        hits =[n for n in self.todos_clientes if t in n.upper() and n not in self.selected_names][:10]
        if hits:
            self.sug_list.configure(height=min(len(hits), 5))
            for c in hits: self.sug_list.insert(tk.END, c)
            self.sug_frame.pack(fill="x", padx=14, pady=(0,4), after=self.cliente_entry.master)
        else: self.sug_frame.pack_forget()

    def _on_select(self, e=None):
        sel = self.sug_list.curselection()
        if not sel: return
        nm = self.sug_list.get(sel[0])
        if nm not in self.selected_names:
            self.selected_names.append(nm)
            self._render_chips()
        self.cliente_entry.delete(0, tk.END)
        self.sug_frame.pack_forget()

    def _render_chips(self):
        for w in self.chips_frame.winfo_children(): w.destroy()
        for nm in self.selected_names:
            chip = ctk.CTkFrame(self.chips_frame, fg_color=self.C_CHIP, corner_radius=16, height=30)
            chip.pack(anchor="w", padx=0, pady=3)
            ctk.CTkLabel(chip, text=f"  {nm}  ", text_color="#fff", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0), pady=4)
            
            if nm != getattr(self, 'original_client', None):
                ctk.CTkButton(chip, text="✕", width=24, fg_color="#EF4444", text_color="white", command=lambda n=nm: self._remove_chip(n)).pack(side="left", padx=(4, 8), pady=4)
            else:
                ctk.CTkLabel(chip, text="🔒 ", text_color="#94A3B8", font=ctk.CTkFont(size=12)).pack(side="left", padx=(4, 8), pady=4)
                
        if self.selected_names: self.chips_frame.pack(fill="x", padx=14, pady=(4, 6))
        else: self.chips_frame.pack_forget()
        
        self._buscar_propiedades()

    def _remove_chip(self, name):
        if name in self.selected_names:
            self.selected_names.remove(name)
            self._render_chips()
            if not self.selected_names:
                self.lotes_container.pack_forget()
                for w in self.lotes_container.winfo_children(): w.destroy()
                self.lote_vars.clear()

    def _buscar_propiedades(self):
        for w in self.lotes_container.winfo_children():
            if w.winfo_exists(): w.destroy()
        self.lote_vars.clear()
        
        all_lotes =[]
        for nm in self.selected_names:
            for v in self.cliente_lotes.get(nm,[]): 
                if (nm, v) not in all_lotes:
                    all_lotes.append((nm, v))
                    
        if not all_lotes: return
        
        self._lbl(self.lotes_container.master, "Propiedades encontradas")
        hdr = ctk.CTkFrame(self.lotes_container, fg_color="transparent"); hdr.pack(fill="x", padx=10, pady=(8, 4))
        self.sa_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(hdr, text="Seleccionar Todos", variable=self.sa_var, command=self._ta, text_color="white").pack(side="left")
        
        for nm, v in all_lotes:
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(self.lotes_container, text=f"  {nm}  —  {v}", variable=var, text_color="white").pack(anchor="w", padx=12, pady=3)
            self.lote_vars.append((v, var))
            
        self.lotes_container.pack(fill="x", padx=14, pady=(4, 10))

    def _ta(self):
        for _, var in self.lote_vars: var.set(self.sa_var.get())
    
    def _cerrar_gestion(self):
        import database_core
        database_core.AppState.current_client = None
        self.destroy()

    def _guardar(self):
        lotes =[(v, self.map_cartera.get(v,"")) for v, var in self.lote_vars if var.get()]
        if not lotes:
            self.lbl_st.configure(text="⚠️ Selecciona al menos un lote.", text_color="#F59E0B"); return

        self.btn_save.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.lbl_st.configure(text=f"Enviando {len(lotes)} gestión(es)...", text_color="#F59E0B")
        self.progress.pack(pady=3); self.progress.start()

        fh = self.fecha_entry.get().strip() or datetime.now().strftime("%Y-%m-%d")
        cf = "1" if self.contacto_var.get() == "SÍ" else "0"
        cv = "1" if self.convenio_var.get() == "SÍ" else "0"
        cp = "1" if self.pago_var.get() == "SÍ" else "0"
        
        user_text = self.text_coment.get("1.0", "end-1c").strip()
        ts = self.call_start.strftime("%Y-%m-%d %H:%M:%S")
        
        call_metadata = f"[Llamada al: {self.call_number} | Fecha: {ts} | Duración: {self.call_duration}s]"
        comentario = f"Gestión registrada por medio de app Central Telefónica GPH | Comentario: {user_text}{call_metadata}"
        
        medio = self.asunto_cmb.get()
        idx = self.MEDIOS.index(medio)+1 if medio in self.MEDIOS else 4
        mp = f"{idx}-{medio}"

        self._pend=list(lotes); self._ok=0; self._err=[]
        
        meses=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        now=datetime.now()
        ms=f"{meses[now.month-1]} {now.year}"

        def clean_num(val):
            return val.replace("$", "").replace(",", "").strip() or "0"
        
        def nxt():
            if not self.winfo_exists(): return
            if not self._pend:
                self.progress.stop(); self.progress.pack_forget()
                database_core.AppState.current_client = None
                
                if self._err: 
                    self.lbl_st.configure(text=f"✅ {self._ok} Procesadas · ❌ {len(self._err)} Errores", text_color="#F59E0B")
                else: 
                    self.lbl_st.configure(text=f"✅ {self._ok} gestión(es) registradas", text_color=self.C_ACCENT2)
                    self.after(1800, self.destroy)
                
                self.btn_save.configure(state="normal")
                self.btn_cancel.configure(state="normal")
                return
                
            v, idc = self._pend.pop(0)
            
            c_vencidas = str(self.contact_info.get('mesesadeudo', "0"))
            if not c_vencidas or c_vencidas == "None": c_vencidas = "0"

            self.lbl_st.configure(text=f"📤 → {v}...", text_color="#F59E0B")
            pl = {
                "id_cobranza": idc, "status": "1", "tipo": "0", "cuotasVencidas": c_vencidas,
                "lotes": "false", "medio": mp, "contacto": cf, "comentario": comentario,
                "fechaRecibo": fh, "fecha": fh
            }
            
            if cf == "1":
                pl.update({"convenio": cv})
                if cp == "1":
                    id_d = self.map_desc.get(self.descuento_cmb.get(),"13")
                    nd = self.descuento_cmb.get()
                    
                    pl.update({
                        "cartera": "1",
                        "fpago": self.fpago_cmb.get(),
                        "descuento": nd,
                        "id_tipoDescuento": id_d,
                        "cantidad": clean_num(self.cantidad_entry.get()),
                        "isComision": "0",
                        "pagodesde": ms,
                        "pagohasta": ms
                    })
                else:
                    pl.update({"pagodesde":"", "pagohasta":""})
            else: 
                pl.update({"pagodesde":"", "pagohasta":""})
                
            if getattr(self, 'original_client', None):
                nom_resumen = self.original_client
            else:
                nom_resumen = self.cliente_entry.get().strip().upper()
                if not nom_resumen:
                    nom_resumen = self.contact_info.get('clienteNombre', self.contact_info.get('ncliente', 'SIN NOMBRE'))

            archivos_nombres = "Sin archivos"
            if self.rutas_evidencia:
                archivos_nombres = ", ".join([os.path.basename(r) for r in self.rutas_evidencia if r])

            resumen = json.dumps({
                "Cliente": nom_resumen,
                "Lote": v,
                "Medio": mp, 
                "Contactado": "SÍ" if cf=="1" else "NO", 
                "Convenio": "SÍ" if cv=="1" else "NO",
                "Pago": "SÍ" if cp=="1" else "NO", 
                "Monto": pl.get("cantidad", "$0"), 
                "Forma Pago": pl.get("fpago", "N/A"),
                "Evidencias": archivos_nombres,
                "Comentario": user_text 
            })

            def ok(m):
                self._ok+=1
                database_core.log_gestion(v, idc, "OK", comentario=comentario, payload_resumen=resumen)
                if self.winfo_exists(): self.after(300, nxt)
                
            def er(m):
                if "encolado" in str(m).lower():
                    self._ok += 1
                    database_core.log_gestion(v, idc, "PENDIENTE", comentario=comentario + "[Cola]", payload_resumen=resumen)
                else:
                    self._err.append(f"{v}:{m}")
                    database_core.log_gestion(v, idc, "ERROR", error_msg=str(m), comentario=comentario, payload_resumen=resumen)
                if self.winfo_exists(): self.after(300, nxt)
                
            api_gph.enviar_gestion(pl, self.rutas_evidencia, 
                on_success=lambda m: self.after(0, lambda: ok(m)) if self.winfo_exists() else None, 
                on_error=lambda e: self.after(0, lambda: er(e)) if self.winfo_exists() else None)
        
        nxt()

class DialerFrame(ctk.CTkFrame):
    def __init__(self, master, mixer):
        super().__init__(master)
        self.mixer = mixer
        self._is_held   = False
        self._is_muted  = False
        self.current_contact_info = None
        self._search_timer = None
        self.current_offset = 0
        self.is_loading = False
        self.total_results = 0
        self.col_filter_entries = {}
        self._enlace_warning_shown = False # <--- NUEVA BANDERA
        self.pack(expand=True, fill="both")

        self.tabs = ctk.CTkTabview(self, segmented_button_fg_color="#f0f2f5", segmented_button_selected_color="#2b64d3", segmented_button_selected_hover_color="#1d4a99", segmented_button_unselected_hover_color="#e1e4e8", text_color="#011536")
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_dial = self.tabs.add("📞 Marcación")
        self.tab_card = self.tabs.add("📇 Cartera Contactos")

        self._setup_dialer_tab()
        self._setup_cartera_tab()
        
        self._refresh_phone_led_loop()

    def _setup_dialer_tab(self):
        container = self.tab_dial
        
        self.title_lbl = ctk.CTkLabel(container, text="Realizar Llamada", font=ctk.CTkFont(size=24, weight="bold"), text_color="#011536")
        self.title_lbl.pack(pady=(10, 5))

        # --- NUEVO BANNER GIGANTE DE ESTADO ---
        self.status_banner = ctk.CTkFrame(container, corner_radius=8, height=45, cursor="hand2")
        self.status_banner.pack(fill="x", padx=40, pady=(0, 15))
        self.status_banner.pack_propagate(False)
        
        self.lbl_status_banner = ctk.CTkLabel(self.status_banner, text="Buscando celular...", font=ctk.CTkFont(size=14, weight="bold"), text_color="white", cursor="hand2")
        self.lbl_status_banner.place(relx=0.5, rely=0.5, anchor="center")
        
        # Hacemos que el banner sea clickeable para ayudar al usuario
        self.status_banner.bind("<Button-1>", lambda e: self._handle_disconnected_click())
        self.lbl_status_banner.bind("<Button-1>", lambda e: self._handle_disconnected_click())

        self.input_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.input_frame.pack(pady=10)

        self.country_vars = {
            "México (+52)": "+52", "Estados Unidos/Canadá (+1)": "+1",
            "Colombia (+57)": "+57", "Argentina (+54)": "+54",
            "España (+34)": "+34", "Chile (+56)": "+56",
            "Perú (+51)": "+51", "Ecuador (+593)": "+593",
            "Guatemala (+502)": "+502", "Cuba (+53)": "+53",
            "Bolivia (+591)": "+591", "R. Dominicana (+1 809)": "+1809",
            "Honduras (+504)": "+504", "El Salvador (+503)": "+503",
            "Nicaragua (+505)": "+505", "Costa Rica (+506)": "+506",
            "Panamá (+507)": "+507", "Puerto Rico (+1)": "+1",
            "Uruguay (+598)": "+598", "Paraguay (+595)": "+595",
            "Venezuela (+58)": "+58", "Otra (Escribir Manualmente)": "+"
        }

        self.country_cmb = ttk.Combobox(self.input_frame, values=list(self.country_vars.keys()),
                                        state="normal", font=("Arial", 14, "bold"), width=22)
        self.country_cmb.set("México (+52)")
        self.country_cmb.pack(side="left", padx=(0, 10), ipady=8)

        self.number_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Número...",
                                          width=200, height=45,
                                          font=ctk.CTkFont(size=20, weight="bold"), justify="center",
                                          border_color="#2b64d3", text_color="#011536", border_width=2)
        self.number_entry.pack(side="left")

        self.dial_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.dial_frame.pack(pady=5)

        buttons = [['1','2','3'],['4','5','6'],['7','8','9'],['*','0','#']]
        for r, row in enumerate(buttons):
            for c, char in enumerate(row):
                btn = ctk.CTkButton(self.dial_frame, text=char, width=55, height=55,
                                    font=ctk.CTkFont(size=20, weight="bold"),
                                    fg_color="#f0f2f5", hover_color="#e1e4e8", text_color="#011536",
                                    border_width=1, border_color="#d0d5dd",
                                    command=lambda ch=char: self.append_char(ch))
                btn.grid(row=r, column=c, padx=4, pady=4)

        self.action_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.action_frame.pack(pady=10)

        self.call_btn = ctk.CTkButton(self.action_frame, text="📞 Llamar",
                                      fg_color="#2E8B57", hover_color="#1d663d", text_color="white",
                                      height=45, width=150, font=ctk.CTkFont(size=16, weight="bold"),
                                      command=self.start_api_call)
        self.call_btn.pack(side="left", padx=5)

        self.clear_btn = ctk.CTkButton(self.action_frame, text="Borrar",
                                       fg_color="#e74c3c", hover_color="#c0392b", text_color="white",
                                       height=45, width=80, font=ctk.CTkFont(size=16, weight="bold"),
                                       command=self.clear_number)
        self.clear_btn.pack(side="left", padx=5)

        self.test_modal_btn = ctk.CTkButton(container, text="🧪 Probar Modal de Gestión",
                                            fg_color="#3498DB", hover_color="#2980B9", text_color="white",
                                            height=30, width=180, font=ctk.CTkFont(size=11),
                                            command=self.test_modal)
        if getattr(database_core, 'CURRENT_USER_ROLE', 'Usuario') == 'Administrador':
            self.test_modal_btn.pack(pady=10)

        # Aquí quitamos el foquito y solo dejamos el texto de estado de la llamada activa
        self.lbl_record = ctk.CTkLabel(container, text="Estado: En Espera", text_color="gray", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_record.pack(pady=(5, 5))

        self.in_call_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.active_status_lbl = ctk.CTkLabel(self.in_call_frame,
            text="🔴 Llamando...",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="orange")
        self.timer_lbl = ctk.CTkLabel(self.in_call_frame, text="00:00",
            font=ctk.CTkFont(size=16, weight="bold"))
        self._timer_running = False
        self._timer_seconds = 0

        self.incall_controls_frame = ctk.CTkFrame(self.in_call_frame, fg_color="transparent")
        self.hold_btn = ctk.CTkButton(self.incall_controls_frame, text="⏸ Pausar",
            fg_color="#E67E22", hover_color="#A04000", height=45, width=140,
            font=ctk.CTkFont(size=12, weight="bold"), command=self.toggle_hold)
        self.hold_btn.pack(side="left", padx=5)
        self.mute_btn = ctk.CTkButton(self.incall_controls_frame, text="🎙 Silenciar",
            fg_color="#7D3C98", hover_color="#4A235A", height=45, width=140,
            font=ctk.CTkFont(size=12, weight="bold"), command=self.toggle_mute)
        self.mute_btn.pack(side="left", padx=5)
        
        self.hangup_btn = ctk.CTkButton(self.in_call_frame,
            text="⏹ FINALIZAR Y GUARDAR",
            fg_color="#D8000C", hover_color="#8B0000", height=55, width=320,
            font=ctk.CTkFont(size=16, weight="bold"), command=self.hang_up_and_save)
        self.hangup_btn.pack(pady=(20, 10))

    def _apply_banner_style(self, bg_color, text):
        if self.winfo_exists() and hasattr(self, 'status_banner'):
            self.status_banner.configure(fg_color=bg_color)
            self.lbl_status_banner.configure(text=text)

    def _setup_cartera_tab(self):
        container = self.tab_card
        
        # 1. HEADER (Reducido para ganar altura)
        header = ctk.CTkFrame(container, fg_color="#011536", corner_radius=8, height=45)
        header.pack(fill="x", padx=10, pady=(5, 5))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="📇 AGENDA ESTRATÉGICA DE CLIENTES", font=ctk.CTkFont(size=14, weight="bold"), text_color="white").place(relx=0.5, rely=0.5, anchor="center")
                    
        self.btn_export_excel = ctk.CTkButton(header, text="📊 DESCARGAR EXCEL", fg_color="#10B981", hover_color="#059669", width=140, height=30, font=ctk.CTkFont(size=11, weight="bold"), command=self._export_to_excel)
        self.btn_export_excel.pack(side="left", padx=10, pady=6)

        self.btn_sync_main = ctk.CTkButton(header, text="🔄 ACTUALIZAR CARTERA", fg_color="#3B82F6", hover_color="#2563EB", width=150, height=30, font=ctk.CTkFont(size=11, weight="bold"), command=self._sync_cartera_ui)
        self.btn_sync_main.pack(side="right", padx=10, pady=6)

        # 2. BARRA DE CONTROL LIGERA (Mejorada)
        ctrl_bar = ctk.CTkFrame(container, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0")
        ctrl_bar.pack(fill="x", padx=10, pady=5)
        
        # Proyecto con más espacio
        f_p = ctk.CTkFrame(ctrl_bar, fg_color="transparent")
        f_p.pack(side="left", padx=10, pady=5)
        ctk.CTkLabel(f_p, text="PROYECTO:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(side="left", padx=2)
        self.cmb_proy = ttk.Combobox(f_p, values=["Todos"], width=30, state="readonly")
        self.cmb_proy.set("Todos"); self.cmb_proy.pack(side="left")
        self.cmb_proy.bind("<<ComboboxSelected>>", lambda e: self._on_proy_selected())
        
        # Condominio
        f_c = ctk.CTkFrame(ctrl_bar, fg_color="transparent")
        f_c.pack(side="left", padx=10, pady=5)
        ctk.CTkLabel(f_c, text="CONDOMINIO:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(side="left", padx=2)
        self.cmb_cond = ttk.Combobox(f_c, values=["Todos"], width=20, state="readonly")
        self.cmb_cond.set("Todos"); self.cmb_cond.pack(side="left")
        self.cmb_cond.bind("<<ComboboxSelected>>", lambda e: self._on_cartera_search())
        
        # Sin Teléfono
        self.check_no_phone = ctk.CTkCheckBox(ctrl_bar, text="Sin Teléfono", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1e293b", command=self._on_cartera_search)
        self.check_no_phone.pack(side="left", padx=20)
        
        # Recuento y Limpieza (Ahora más notables)
        self.btn_limpiar = ctk.CTkButton(ctrl_bar, text="❌ Limpiar Filtros", width=140, height=32, fg_color="#F43F5E", hover_color="#BE123C", font=ctk.CTkFont(size=11, weight="bold"), command=self._clear_filter)
        self.btn_limpiar.pack(side="right", padx=10)
        
        self.lbl_record_count = ctk.CTkLabel(ctrl_bar, text="Total: 0", font=ctk.CTkFont(size=12, weight="bold"), text_color="#3B82F6")
        self.lbl_record_count.pack(side="right", padx=10)
        
        self.header_filters = {}

        # 3. EL FOOTER (Diseño Grid 100% Responsive)
        self.footer_card = ctk.CTkFrame(container, fg_color="#011536", height=40, corner_radius=0)
        self.footer_card.pack(fill="x", side="bottom")
        self.footer_card.pack_propagate(False)
        
        # Grid maestro: Reducimos el peso de la primera columna para quitar el hueco rojo
        self.footer_card.grid_columnconfigure(0, weight=2) # Nombre (Peso 3 en lugar de 4)
        self.footer_card.grid_columnconfigure(1, weight=1) # Adeudos
        self.footer_card.grid_columnconfigure(2, weight=1) # Suma
        self.footer_card.grid_columnconfigure(3, weight=1) # Meses (Flexible)
        self.footer_card.grid_columnconfigure(4, weight=1) # Fechas
        self.footer_card.grid_columnconfigure(5, weight=1) # Botón
        self.footer_card.grid_rowconfigure(0, weight=1)

        # ZONA 0: Info Cliente
        self.f_info_left = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_info_left.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=5) # Menos padding para ganar espacio vertical
        
        # wraplength=280 asegura que el nombre haga salto de línea si es largo
        # justify="left" asegura que los apellidos bajen pegados a la izquierda
        self.lbl_det_nombre = ctk.CTkLabel(self.f_info_left, text="Seleccione un cliente", font=ctk.CTkFont(size=12, weight="bold"), text_color="white", anchor="w", justify="left", wraplength=280)
        self.lbl_det_nombre.pack(fill="x", pady=(2, 0))
        
        self.f_sub_detail = ctk.CTkFrame(self.f_info_left, fg_color="transparent"); self.f_sub_detail.pack(fill="x")
        self.lbl_det_lote = ctk.CTkLabel(self.f_sub_detail, text="Lote: -", font=ctk.CTkFont(size=13), text_color="#94A3B8")
        self.lbl_det_lote.pack(side="left", padx=(0, 10))
        self.lbl_det_status = ctk.CTkLabel(self.f_sub_detail, text="-", font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", corner_radius=6, padx=6)
        self.lbl_det_status.pack(side="left")

        # ZONA 1: Adeudos Rojos
        self.f_adeudos = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_adeudos.grid(row=0, column=1, sticky="w", padx=(5, 10), pady=15)
        self.lbl_det_adeudo = ctk.CTkLabel(self.f_adeudos, text="Adeudo Total: $0.00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F87171")
        self.lbl_det_adeudo.pack(anchor="w")
        self.lbl_det_otros = ctk.CTkLabel(self.f_adeudos, text="Otros Adeudos: $0.00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F87171")
        self.lbl_det_otros.pack(anchor="w")

        # ZONA 2: Suma Verde
        self.f_suma = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_suma.grid(row=0, column=2, sticky="w", padx=(10, 15), pady=25)
        self.lbl_det_suma = ctk.CTkLabel(self.f_suma, text="Suma: $0.00", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981") 
        self.lbl_det_suma.pack(anchor="w")

        # ZONA 3: Meses de Adeudo
        self.f_meses = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_meses.grid(row=0, column=3, sticky="nsew", pady=25)
        self.lbl_det_meses = ctk.CTkLabel(self.f_meses, text="MESES: -", font=ctk.CTkFont(size=12, weight="bold"), text_color="#F59E0B")
        self.lbl_det_meses.pack(anchor="center")

        # ZONA 4: Fechas y Anualidad
        self.f_fechas = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_fechas.grid(row=0, column=4, sticky="e", padx=(5, 15), pady=15)
        self.lbl_det_pago = ctk.CTkLabel(self.f_fechas, text="Últ. Pago: -", font=ctk.CTkFont(size=11, weight="bold"), text_color="#E2E8F0")
        self.lbl_det_pago.pack(anchor="e")
        self.lbl_det_anualidad = ctk.CTkLabel(self.f_fechas, text="Anualidad: -", font=ctk.CTkFont(size=11, weight="bold"), text_color="#E2E8F0")
        self.lbl_det_anualidad.pack(anchor="e")

        # ZONA 5: Botones
        self.f_accion = ctk.CTkFrame(self.footer_card, fg_color="transparent")
        self.f_accion.grid(row=0, column=5, sticky="e", padx=(5, 10), pady=10)
        self.btn_call_card = ctk.CTkButton(self.f_accion, text="📞 LLAMAR", width=90, height=30, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(size=11, weight="bold"), command=self._on_call_from_agenda)
        self.btn_call_card.pack(side="right", padx=(5, 0))
        self.cmb_nums = ttk.Combobox(self.f_accion, values=[], width=14, state="readonly", font=("Segoe UI", 9))
        self.cmb_nums.pack(side="right")

        # 4. LA TABLA (Contenedor Elástico con Scrollbars)
        # Este contenedor es el que abraza todo. Si sobra espacio, lo toma.
        self.f_tree_container = ctk.CTkFrame(container, fg_color="white", corner_radius=8, border_width=1, border_color="#e2e8f0")
        self.f_tree_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="white", foreground="#334155", rowheight=26, fieldbackground="white", borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#f1f5f9", foreground="#475569", font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Treeview", background=[('selected', '#3B82F6')], foreground=[('selected', 'white')])

        # Creación de la tabla con scrollbars conectados ANTES de empaquetar
        self.tree_scroll_y = ttk.Scrollbar(self.f_tree_container, orient="vertical")
        self.tree_scroll_y.pack(side="right", fill="y")
        
        self.tree_scroll_x = ttk.Scrollbar(self.f_tree_container, orient="horizontal")
        self.tree_scroll_x.pack(side="bottom", fill="x")

        columns = ("ncliente", "lote", "statusTerreno", "nestatus", "mesesadeudo", "anualidad", "adeudo", "adeudoM", "adeudo_otros", "totalAdeudo", "totalAdeudoLL", "asesorNombre", "ugestion", "fultpago", "fechaFondoReserva", "fecha1erMensMtto")
        self.tree = ttk.Treeview(self.f_tree_container, columns=columns, show="headings", selectmode="browse", yscrollcommand=self.tree_scroll_y.set, xscrollcommand=self.tree_scroll_x.set)
        
        self.tree_scroll_y.config(command=self.tree.yview)
        self.tree_scroll_x.config(command=self.tree.xview)

        # Diccionario para mapear ID de columna con el título original (para Limpiar)
        self.col_titles = {
            "ncliente": "Nombre Cliente", "lote": "Lote", "statusTerreno": "Estatus Terreno",
            "nestatus": "Estatus Cliente", "mesesadeudo": "Meses", "anualidad": "Anualidad",
            "adeudo": "Mantenimiento", "adeudoM": "Moratorios", "adeudo_otros": "Otros Adeudos",
            "totalAdeudo": "Adeudo Total", "totalAdeudoLL": "Total + Otros",
            "asesorNombre": "Asesor Asignado", "ugestion": "Última Gestión",
            "fultpago": "Último Pago", "fechaFondoReserva": "FDR", "fecha1erMensMtto": "1er Pago"
        }
        
        for col, title in self.col_titles.items():
            self.tree.heading(col, text=title, command=lambda _col=col: self._show_column_filter(_col))

        self.tree.column("ncliente", width=220, minwidth=150)
        self.tree.column("lote", width=120, minwidth=100)
        self.tree.column("statusTerreno", width=110, minwidth=100)
        self.tree.column("nestatus", width=120, minwidth=100)
        self.tree.column("mesesadeudo", width=60, anchor="center", minwidth=50)
        self.tree.column("anualidad", width=90, anchor="e", minwidth=80)
        self.tree.column("adeudo", width=100, anchor="e", minwidth=90)
        self.tree.column("adeudoM", width=90, anchor="e", minwidth=80)
        self.tree.column("adeudo_otros", width=100, anchor="e", minwidth=90)
        self.tree.column("totalAdeudo", width=100, anchor="e", minwidth=90)
        self.tree.column("totalAdeudoLL", width=120, anchor="e", minwidth=100)
        self.tree.column("asesorNombre", width=160, minwidth=120)
        self.tree.column("ugestion", width=100, minwidth=90)
        self.tree.column("fultpago", width=100, minwidth=90)
        self.tree.column("fechaFondoReserva", width=100, minwidth=90)
        self.tree.column("fecha1erMensMtto", width=100, minwidth=90)

        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._show_details_modal())
        self.tree.bind("<Control-c>", self._copy_tree_row)

        self.tree.tag_configure("odd", background="#f5f5f5")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("moroso", background="#ffe5e5", foreground="#991b1b") 
        self.tree.tag_configure("riesgo", background="#fff5cc", foreground="#92400e") 
        self.tree.tag_configure("ok", background="#e5ffe5", foreground="#166534")     
        self.tree.tag_configure("rojo_alerta", background="#fca5a5", foreground="#7f1d1d")
        self.tree.tag_configure("amarillo_alerta", background="#fef08a", foreground="#92400e")

        self.cached_results = {}
        self.all_current_results = []
        self._search_timer = None

        # --- LÓGICA DE SALUDO Y CARTERA ---
        import database_core
        from datetime import datetime
        
        app_main = self.winfo_toplevel()
        lbl_estado = getattr(app_main, 'lbl_global_cartera', None)
        last_sync_str = database_core.get_config("cartera_last_sync")
        
        # 1er CANDADO: Verificamos si tiene credenciales de Google/SISCO
        if not database_core.has_sisco_profile():
            if lbl_estado:
                lbl_estado.configure(text="⚠️ Cuenta SISCO no vinculada", text_color="#EF4444")
            self.tree.insert("", "end", values=("🔒", "Requiere conexión SISCO", "Ve al menú 'Conexión SISCO'", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            self.btn_sync_main.configure(state="disabled")
            
        elif database_core.cartera_needs_refresh():
            if lbl_estado:
                lbl_estado.configure(text=f"⚠️ Cartera Desactualizada - ⏳ Preparando actualización...", text_color="#F59E0B")
            self.tree.insert("", "end", values=("⏳", "Iniciando descarga de la cartera...", "Por favor espere...", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            self.after(500, self._sync_cartera_ui)
        else:
            if lbl_estado:
                lbl_estado.configure(text=f"✅ Cartera sincronizada hoy a las: {last_sync_str}", text_color="#10B981")
            self._load_cartera_data()

    def _clear_filter(self):
        """Resetea TODOS los filtros (superiores y de cabecera)."""
        if hasattr(self, 'cmb_proy'): self.cmb_proy.set("Todos")
        if hasattr(self, 'cmb_cond'): self.cmb_cond.set("Todos")
        if hasattr(self, 'check_no_phone'): self.check_no_phone.deselect()
        
        # Restaurar títulos originales de cabeceras
        if hasattr(self, 'col_titles'):
            for col, title in self.col_titles.items():
                self.tree.heading(col, text=title)
        
        # Limpieza absoluta de filtros de cabecera
        if hasattr(self, 'header_filters'):
            self.header_filters.clear()
            
        print("[UI] Filtros reseteados.")
        self._on_cartera_search()
     
    def _show_column_filter(self, col):
        """Muestra un pequeño popup de búsqueda sobre el encabezado."""
        try:
            # Truco para headers: No tienen bbox, usamos el de su primer item
            x, y, w, h = self.tree.bbox(self.tree.get_children()[0], col)
        except:
            # Si no hay items, fallback simplificado
            x, y, w, h = (50, 50, 150, 25)

        root_x = self.tree.winfo_rootx() + x
        root_y = self.tree.winfo_rooty() - 5 
        
        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.geometry(f"{max(w, 150)}x35+{root_x}+{root_y}")
        pop.attributes("-topmost", True)
        pop.configure(bg="#3B82F6")
        
        f_in = tk.Frame(pop, bg="white")
        f_in.pack(fill="both", expand=True, padx=1, pady=1)
        
        ent = tk.Entry(f_in, font=("Segoe UI", 10), bd=0, highlightthickness=0)
        ent.pack(fill="both", expand=True, padx=5)
        ent.focus_set()
        
        # Cargar valor actual si existe
        if not hasattr(self, 'header_filters'): self.header_filters = {}
        curr = self.header_filters.get(col, "")
        ent.insert(0, curr)
        
        def apply(e=None):
            val = ent.get()
            self.header_filters[col] = val
            
            # Feedback visual en el header
            orig_title = self.col_titles.get(col, col)
            if val.strip():
                self.tree.heading(col, text=f"🔍 {orig_title}")
            else:
                self.tree.heading(col, text=orig_title)
                
            pop.destroy()
            self._on_cartera_search()

        ent.bind("<Return>", apply)
        ent.bind("<FocusOut>", lambda e: pop.destroy())
        ent.bind("<Escape>", lambda e: pop.destroy())

    def _get_active_col_filters(self):
        if not hasattr(self, 'header_filters'): return {}
        return {k: v for k, v in self.header_filters.items() if v.strip()}

    def _check_roles(self):
        if hasattr(self.master.master.master, 'current_user_role'):
            role = self.master.master.master.current_user_role
            if role != "Administrador":
                if hasattr(self, 'btn_delete_card'):
                    self.btn_delete_card.configure(state="disabled", fg_color="#94a3b8")

    def _sync_cartera_ui(self):
        import database_core
        
        if not database_core.has_sisco_profile():
            messagebox.showwarning("Faltan Credenciales", "Vincula tu cuenta SISCO primero.")
            return

        if database_core.AppState.syncing:
            messagebox.showwarning("Atención", "Ya hay una sincronización en curso.")
            return

        database_core.AppState.syncing = True
        self.btn_sync_main.configure(state="disabled", text="⏳ SINCRONIZANDO...")
        
        dialog = SyncProgressDialog(self.winfo_toplevel())
        dialog.lift()

        def finalizar_proceso(success, msg=""):
            database_core.AppState.syncing = False
            if self.winfo_exists():
                self.after(0, lambda: dialog.on_sync_complete(success, msg))
                self.after(0, lambda: self.btn_sync_main.configure(state="normal", text="🔄 ACTUALIZAR CARTERA"))
                if success:
                    self.after(0, self.refresh_data)

        def ejecutar_flujo():
            try:
                api_gph.sincronizar_contactos_posventa(
                    on_progress=lambda p, msg: self.after(0, lambda: dialog.update_progress(p, msg)),
                    on_success=lambda: api_gph.descargar_cartera_backend(
                        on_progress=lambda p, msg: self.after(0, lambda: dialog.update_progress(p, msg)),
                        on_success=lambda: finalizar_proceso(True),
                        on_error=lambda err: finalizar_proceso(False, err)
                    ),
                    on_error=lambda err: finalizar_proceso(False, err)
                )
            except Exception as e:
                finalizar_proceso(False, str(e))

        threading.Thread(target=ejecutar_flujo, daemon=True).start()

    def refresh_data(self):
        if not self.winfo_exists(): return
        
        # FIX: Evitar KeyError 'popdown' al usar focus_get()
        try:
            focused = self.focus_get()
            is_searching = (focused == self.ent_search._entry)
        except:
            is_searching = False
            
        if is_searching:
            self.after(2000, self.refresh_data)
            return
        
        # Volver a cargar la tabla
        self._load_cartera_data()
        
        # --- NUEVO: Refrescar el texto del Header superior inmediatamente ---
        app_main = self.winfo_toplevel()
        lbl_estado = getattr(app_main, 'lbl_global_cartera', None)
        if lbl_estado:
            import database_core
            last_sync = database_core.get_config("cartera_last_sync")
            lbl_estado.configure(text=f"✅ Cartera sincronizada hoy a las: {last_sync}", text_color="#10B981")

    def _copy_tree_row(self, event=None):
        selected = self.tree.selection()
        if not selected: return
        item = self.tree.item(selected[0])
        values = item['values']
        if values:
            text_to_copy = "\t".join([str(v) for v in values])
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            self.update() 
            messagebox.showinfo("Copiado", "Los datos de la fila se copiaron al portapeles.")

    def _show_details_modal(self):
        selected = self.tree.selection()
        if not selected: return
        iid = selected[0]
        contact = self.cached_results.get(iid)
        
        if contact:
            if not hasattr(self, 'detail_windows'):
                self.detail_windows =[]
            self.detail_windows = [w for w in self.detail_windows if w.winfo_exists()]
            modal = ui_modals.ContactDetailsModal(self.winfo_toplevel(), contact)
            self.detail_windows.append(modal)

    def _load_cartera_data(self):
        # Actualizamos Proyecto y Condominio del top bar
        proys = ["Todos"] + database_core.get_unique_values("nproyecto", table="contactos")
        self.cmb_proy.configure(values=proys)
        # Nota: Los filtros avanzados se cargan "bajo demanda" al hacer clic
        self._on_cartera_search()

    def _on_proy_selected(self):
        proy = self.cmb_proy.get()
        conds = ["Todos"] + database_core.get_condominios_list(proy if proy != "Todos" else None)
        self.cmb_cond.configure(values=conds)
        self.cmb_cond.set("Todos")
        self._on_cartera_search()

    def _on_tree_scroll(self, *args):
        self.y_scroll.set(*args)
        if float(args[1]) > 0.95 and not self.is_loading:
            self._load_more()

    def _on_cartera_search(self, event=None):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._do_search)

    def _do_search(self, append=False):
        if self.is_loading: return
        self.is_loading = True
        
        proy = self.cmb_proy.get()
        cond = self.cmb_cond.get()
        
        # ESTA LÍNEA ES LA MAGIA: Atrapa todo lo escrito en los nuevos filtros
        col_filters = self._get_active_col_filters()
        sin_tel = self.check_no_phone.get()

        if not append:
            self.current_offset = 0
            for item in self.tree.get_children(): self.tree.delete(item)
            self.tree.insert("", "end", values=("⏳", "Buscando..."))

        def fetch():
            if not append:
                self.total_results = database_core.get_total_contactos(
                    query=None, proyecto=proy if proy != "Todos" else None,
                    condominio=cond if cond != "Todos" else None,
                    col_filters=col_filters,
                    sin_telefono=self.check_no_phone.get()
                )
            results = database_core.get_contactos(
                query=None, proyecto=proy if proy != "Todos" else None,
                condominio=cond if cond != "Todos" else None,
                col_filters=col_filters,
                sin_telefono=self.check_no_phone.get(),
                limit=100, offset=self.current_offset
            )
            self.all_current_results = results
            if self.winfo_exists():
                self.after(0, lambda: self._finalize_search(results, append))
        threading.Thread(target=fetch, daemon=True).start()

    def _finalize_search(self, results, append):
        if not self.winfo_exists(): return
        self.is_loading = False
        self._populate_tree(results, append=append)

    def _load_more(self):
        if len(self.tree.get_children()) >= 1500:
            return
        self.current_offset += 100
        self._do_search(append=True)

    def _adjust_column_widths(self):
        if not self.winfo_exists(): return
        from tkinter import font
        f = font.Font(family="Segoe UI", size=10)
        
        for col in self.tree["columns"]:
            max_width = f.measure(self.tree.heading(col)["text"]) + 40
            for item in self.tree.get_children():
                cell_text = str(self.tree.set(item, col))
                cell_width = f.measure(cell_text) + 40
                if cell_width > max_width:
                    max_width = cell_width
            final_width = min(max_width, 450)
            self.tree.column(col, width=final_width, minwidth=final_width, stretch=False)

    def _populate_tree(self, results, append=False):
        if not self.winfo_exists(): return
        current_rows = self.tree.get_children()
        
        if not append:
            for item in current_rows:
                self.tree.delete(item)
            self.cached_results = {}
            self.cartera_data = [] # Reset data para exportar
        else:
            for item in current_rows:
                if self.tree.item(item)["values"][0] == "⏳":
                    self.tree.delete(item)

        if not append and not results:
            self.tree.insert("", "end", values=("❌", "Sin resultados", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            self.lbl_record_count.configure(text="Mostrando 0 de 0")
            return

        start_count = len(self.cached_results)
        if start_count >= 1500:
            return

        ST_MOROSO =["MOROSO", "VENCIDO", "COBRANZA"]
        ST_RIESGO = ["ATRASO", "PENDIENTE"]
        ST_OK     = ["AL CORRIENTE", "LIQUIDADO"]
        
        self.tree.tag_configure("odd", background="#f5f5f5")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("moroso", background="#ffe5e5", foreground="#991b1b") 
        self.tree.tag_configure("riesgo", background="#fff5cc", foreground="#92400e") 
        self.tree.tag_configure("ok", background="#e5ffe5", foreground="#166534")     
        self.tree.tag_configure("rojo_alerta", background="#fca5a5", foreground="#7f1d1d")
        self.tree.tag_configure("amarillo_alerta", background="#fef08a", foreground="#92400e")

        for i, c in enumerate(results):
            if len(self.cached_results) >= 1500:
                self.tree.insert("", "end", values=("⚠️", "Límite alcanzado (1500)", "Refina tu búsqueda", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
                break

            st_raw = str(c.get('nestatus', '')).upper()
            status_tag = "even" if (len(self.cached_results)) % 2 == 0 else "odd"
            
            if st_raw in ST_MOROSO: status_tag = "moroso"
            elif st_raw in ST_RIESGO: status_tag = "riesgo"
            elif st_raw in ST_OK: status_tag = "ok"

            st_terreno = str(c.get('statusTerreno', '')).upper()
            asesor = str(c.get('asesorNombre', '')).upper()
            
            celular = str(c.get('ccelular', '')).strip()
            fijo = str(c.get('cfijo', '')).strip()
            tiene_telefono = (celular and celular != "None") or (fijo and fijo != "None")

            if st_terreno == "JURÍDICO" or "NO GESTIONABLE" in asesor:
                status_tag = "rojo_alerta"
            elif not tiene_telefono:
                status_tag = "amarillo_alerta"

            def fmt_money(val):
                fval = database_core.normalize_numeric(val)
                if val is None: return "-"
                if fval == 0: return "$0.00"
                return f"${fval:,.2f}"

            def fmt_date(val):
                if not val or val == "0000-00-00": return "-"
                try:
                    from datetime import datetime
                    if "-" in val:
                        dt = datetime.strptime(val.split()[0], "%Y-%m-%d")
                        return dt.strftime("%d/%m/%Y")
                    return val
                except: return val

            vals = (
                c.get('ncliente') or "-",
                c.get('lote') or "-",
                c.get('statusTerreno') or "-",
                c.get('nestatus') or "-",
                str(c.get('mesesadeudo') or "0"),
                fmt_money(c.get('anualidad')),
                fmt_money(c.get('adeudo')), 
                fmt_money(c.get('adeudoM')), 
                fmt_money(c.get('adeudo_otros')),
                fmt_money(c.get('totalAdeudo')),
                fmt_money(c.get('totalAdeudoLL')),
                c.get('asesorNombre') or "-", 
                c.get('ugestion') or "-",
                fmt_date(c.get('fultpago')),
                fmt_date(c.get('fechaFondoReserva')),
                fmt_date(c.get('fecha1erMensMtto'))
            )
            iid = self.tree.insert("", "end", values=vals, tags=(status_tag,))
            self.cached_results[iid] = c
            if not hasattr(self, 'cartera_data'): self.cartera_data = []
            self.cartera_data.append(c)

        count = len(self.cached_results)
        self.lbl_record_count.configure(text=f"Mostrando {count:,} de {self.total_results:,}")
        self.after(50, self._adjust_column_widths)

    def _sort_treeview_column(self, col, reverse):
        l =[(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        num_cols =["anualidad", "adeudo_otros", "totalAdeudo", "totalAdeudoLL"]
        
        if col in num_cols:
            def clean_num(s):
                try: return float(s.replace("$", "").replace(",", "").replace("-", "0"))
                except: return 0.0
            l.sort(key=lambda t: clean_num(t[0]), reverse=reverse)
        else:
            l.sort(reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)

        self.tree.heading(col, command=lambda: self._sort_treeview_column(col, not reverse))

    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        iid = selected[0]
        contact = self.cached_results.get(iid)
        
        if contact:
            database_core.AppState.current_client = {
                "nombre": contact.get('ncliente'),
                "lote": contact.get('lote'),
                "ts": datetime.now(),
                "valid": True
            }
            
            self.current_contact_info = contact
            
            def fmt_mhex(val):
                fval = database_core.normalize_numeric(val)
                return f"$ {fval:,.2f}"

            nombre_crudo = str(contact.get('ncliente') or "CLIENTE DESCONOCIDO").upper()
            self.lbl_det_nombre.configure(text=nombre_crudo)
            self.lbl_det_lote.configure(text=f"Lote: {contact.get('lote') or '-'}")
            
            st_text = str(contact.get('nestatus') or "SIN ESTATUS").upper()
            self.lbl_det_status.configure(text=st_text)
            
            ST_MOROSO =["MOROSO", "VENCIDO", "COBRANZA"]
            ST_RIESGO = ["ATRASO", "PENDIENTE"]
            ST_OK     = ["AL CORRIENTE", "LIQUIDADO"]
            
            if st_text in ST_MOROSO: 
                self.lbl_det_status.configure(fg_color="#EF4444", text_color="white")
            elif st_text in ST_RIESGO:
                self.lbl_det_status.configure(fg_color="#F59E0B", text_color="black")
            elif st_text in ST_OK:
                self.lbl_det_status.configure(fg_color="#10B981", text_color="white")
            else:
                self.lbl_det_status.configure(fg_color="#334155", text_color="white")
            
            adeudo_tot = contact.get('totalAdeudo')
            otros = contact.get('adeudo_otros')
            suma = contact.get('totalAdeudoLL')
            self.lbl_det_adeudo.configure(text=f"Adeudo Total: {fmt_mhex(adeudo_tot)}")
            self.lbl_det_otros.configure(text=f"Otros Adeudos: {fmt_mhex(otros)}")
            self.lbl_det_suma.configure(text=f"Suma: {fmt_mhex(suma)}")
                
            meses_raw = contact.get('mesesadeudo') or 0
            try: meses_int = int(meses_raw)
            except: meses_int = 0
            
            color_meses = "#F59E0B" if meses_int > 0 else "#10B981"
            if meses_int >= 3: color_meses = "#EF4444"
            
            self.lbl_det_meses.configure(text=f"MESES DE ADEUDO: {meses_raw}", text_color=color_meses)
            
            f_pago = contact.get('fultpago')
            p_text = f_pago if f_pago and f_pago != '0000-00-00' else '-'
            self.lbl_det_pago.configure(text=f"Últ. Pago: {p_text}")
            
            anual = contact.get('anualidad')
            self.lbl_det_anualidad.configure(text=f"Anualidad: {fmt_mhex(anual)}")
            
            nums =[]
            for field in ['ccelular', 'cfijo']:
                val_str = str(contact.get(field, '')).strip()
                if val_str and val_str.lower() != 'none':
                    # Buscamos secuencias de 8 a 13 dígitos seguidos. 
                    # Esto ignora automáticamente "||", ",", espacios o texto basura.
                    found_numbers = re.findall(r'\d{8,13}', val_str)
                    
                    for num in found_numbers:
                        if num not in nums:
                            nums.append(num)
            
            if nums:
                self.cmb_nums.configure(values=nums)
                self.cmb_nums.set(nums[0])
                self.cmb_nums.pack(side="right") # Aseguramos que se muestre
                self.btn_call_card.configure(state="normal")
            else:
                self.cmb_nums.configure(values=[])
                self.cmb_nums.set("Sin números")
                self.cmb_nums.pack(side="left", padx=5)
                self.btn_call_card.configure(state="disabled")

    def _on_call_from_agenda(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Seleccione un cliente de la lista.")
            return
        num = self.cmb_nums.get()
        if not num:
            messagebox.showwarning("Atención", "El cliente no tiene números registrados.")
            return
        
        clean_num = ''.join(filter(str.isdigit, num))
        if clean_num.startswith("52") and len(clean_num) == 12:
            clean_num = clean_num[2:]
        elif clean_num.startswith("521") and len(clean_num) == 13:
            clean_num = clean_num[3:]
            
        print(f"[Dialer] Limpiando número de cartera: {num} -> {clean_num}")
        self._dial_from_cartera(clean_num)

    def _dial_from_cartera(self, number):
        self.number_entry.delete(0, 'end')
        self.number_entry.insert(0, number)
        self.start_api_call()

    def _on_export_excel(self):
        utils_export.export_contacts_to_excel(self.all_current_results)

    def test_modal(self):
        self.abrir_modal_con_sync("C:/Ruta/Falsa/Prueba.mp3",
                                   call_number="5218180001111",
                                   call_start=datetime.now(),
                                   call_duration=45)

    def _export_to_excel(self):
        """Exporta TODOS los datos que coinciden con los filtros actuales (no solo los visibles)."""
        if not hasattr(self, 'total_results') or self.total_results == 0:
            messagebox.showwarning("Sin datos", "Primero realiza una búsqueda con resultados para exportar.")
            return
            
        import utils_export
        import threading
        from tkinter import messagebox
        
        # Guardamos filtros actuales para re-consultar
        proy = self.cmb_proy.get()
        cond = self.cmb_cond.get()
        col_filters = self._get_active_col_filters()
        sin_tel = self.check_no_phone.get()
        
        print(f"[UI] Preparando exportación completa de {self.total_results} registros...")
        
        # Mostrar pequeño aviso de carga si son muchos
        if self.total_results > 500:
            self.btn_export_excel.configure(state="disabled", text="⏳ PROCESANDO...")
            
        def run_export():
            try:
                # Consultamos TODO sin límite
                full_data = database_core.get_contactos(
                    query=None, 
                    proyecto=proy if proy != "Todos" else None,
                    condominio=cond if cond != "Todos" else None,
                    col_filters=col_filters,
                    sin_telefono=sin_tel,
                    limit=200000, # Un límite absurdamente alto para "todos"
                    offset=0
                )
                
                if self.winfo_exists():
                    self.after(0, lambda: self._finalize_export(full_data))
            except Exception as e:
                print(f"[Export Error]: {e}")
                self.after(0, lambda: self.btn_export_excel.configure(state="normal", text="📊 DESCARGAR EXCEL"))

        threading.Thread(target=run_export, daemon=True).start()

    def _finalize_export(self, full_data):
        self.btn_export_excel.configure(state="normal", text="📊 DESCARGAR EXCEL")
        import utils_export
        utils_export.export_contacts_to_excel(full_data)

    def on_dial_click(self, char):
        current = self.number_entry.get()
        self.number_entry.delete(0, 'end')
        self.number_entry.insert(0, current + char)

    def clear_number(self):
        self.number_entry.delete(0, 'end')

    def _handle_disconnected_click(self):
        """Redirige al usuario al perfil si no está conectado y le explica qué hacer"""
        if AppState.phone_connected:
            return # Si está en verde, no pasa nada al hacer clic
            
        msg = (
            "⚠️ CELULAR NO DETECTADO\n\n"
            "Elige UNA de las siguientes opciones para conectar:\n\n"
            "📱 OPCIÓN 1: Por Cable USB (Recomendado si la red bloquea)\n"
            "1. Conecta el celular a la PC con el cable.\n"
            "2. Activa 'Anclaje de red USB' en los ajustes del celular.\n\n"
            "🌐 OPCIÓN 2: Por Wi-Fi\n"
            "1. Conecta el celular y la PC a la MISMA red Wi-Fi LIBRE.\n\n"
            "IMPORTANTE: En ambos casos, abre la app 'GPH Antena' en tu celular.\n"
            "Te llevaremos a la configuración para autodetectarlo."
        )
        messagebox.showwarning("Conexión Requerida", msg)
        
        # Redirigir a la pestaña Servidor Celular automáticamente
        app = self.winfo_toplevel()
        if hasattr(app, 'show_profile'):
            app.show_profile()

    def update_phone_status_ui(self, status):
        """Actualiza el color y texto del Banner Gigante"""
        if not self.winfo_exists(): return
        
        if status == "green":
            bg_color = "#10B981"
            text = "✅ CELULAR CONECTADO Y LISTO PARA MARCAR"
        elif status == "red":
            bg_color = "#EF4444"
            text = "⚠️ CELULAR DESCONECTADO (Clic aquí para solucionar)"
        else:
            bg_color = "#94A3B8"
            text = "⏳ Buscando conexión con el celular..."
            
        if hasattr(self, 'status_banner'):
            self.after(0, lambda: self.status_banner.configure(fg_color=bg_color))
            self.after(0, lambda: self.lbl_status_banner.configure(text=text))

    def handle_connection_failure(self, context="TEL"):
        if not self.winfo_exists(): return
        print(f"[UI] Gestionando fallo de conexión en: {context}")
        AppState.phone_connected = False
        self.update_phone_status_ui("red")
    
        msg = "⚠️ Error de conexión. Reintentando..."
        if context == "AUDIO": msg = "🔇 Fallo de audio stream. Reconectando..."
    
        if hasattr(self, 'lbl_record'):
            self.after(0, lambda: self.lbl_record.configure(text=msg, text_color="red"))
        database_core.log_telemetry(context, f"Fallo detectado en UI: {context}", "ERROR")

    def _refresh_phone_led_loop(self):
        if not self.winfo_exists(): return
        
        # Solo actualizamos si el estado es diferente al anterior para no forzar la GPU
        new_status = "green" if AppState.phone_connected else "red"
        if getattr(self, '_last_status', None) != new_status:
            self.update_phone_status_ui(new_status)
            self._last_status = new_status
            
        self.after(5000, self._refresh_phone_led_loop)

    def check_phone_connection(self):
        ip = database_core.get_config("phone_ip")
        if not ip: return False
        try:
            url = f"http://{ip}:8080/status"
            res = requests.get(url, timeout=5) 
            success = res.status_code == 200
            if success:
                AppState.phone_connected = True
                self.update_phone_led("green")
            else:
                self.handle_connection_failure("TEL")
            return success
        except Exception as e:
            database_core.log_telemetry("CALL", f"Fallo check_phone_connection: {e}", "ERROR")
            self.handle_connection_failure("TEL")
            return False

    def start_api_call(self):
        # En lugar de bloquear, forzamos un chequeo rápido
        if not AppState.phone_connected:
            self.lbl_record.configure(text="Intentando reconectar...", text_color="orange")
            # Forzamos una detección rápida de IP
            ip_recuperada = self._silent_udp_discovery()
            if ip_recuperada:
                database_core.set_config("phone_ip", ip_recuperada)
                AppState.phone_connected = True
            else:
                messagebox.showwarning("Sin conexión", "El celular no responde. Verifica que la App GPH Antena esté abierta.")
                return 

        # 2. VALIDACIÓN HÍBRIDA (SOLO LA PRIMERA VEZ)
        if not getattr(self, '_enlace_warning_shown', False):
            respuesta = messagebox.askyesno(
                "Verificación de Audio",
                "¿Ya tienes la aplicación 'Enlace Móvil' ABIERTA y CONECTADA al celular?\n\n"
                "⚠️ IMPORTANTE: Si marcas sin tener Enlace Móvil activo, tu llamada NO "
                "tendrá audio, no escucharás al cliente y la grabación quedará vacía.\n\n"
                "¿Deseas continuar y realizar la llamada?"
            )

            if not respuesta:
                # Si el usuario dice que "No", lo mandamos al panel de configuración
                app = self.winfo_toplevel()
                if hasattr(app, 'show_profile'):
                    app.show_profile()
                return
            
            # Marcamos que ya se le avisó, para no volver a molestarlo
            self._enlace_warning_shown = True

        # Si responde "Sí" o si ya se le había preguntado antes, procedemos
        number = self.number_entry.get().strip()
        if not number: return
        
        country_str = self.country_cmb.get().strip()
        code = self.country_vars.get(country_str, "+")
        raw_number = ''.join(filter(str.isdigit, number))

        if code == "+52" and len(raw_number) == 10:
            full_number = raw_number
            print(f"[Dialer] Detectado número mexicano. Marcando directo a 10 dígitos: {full_number}")
        else:
            full_number = f"{code}{raw_number}"
            print(f"[Dialer] Marcando número internacional o personalizado: {full_number}")
        
        self.lbl_record.configure(text="Iniciando llamada...", text_color="orange")

        def run_dial_with_retries():
            ip = database_core.get_config("phone_ip")
            if not ip:
                self.after(0, lambda: messagebox.showerror("Error", "Configura la IP del celular en Servidor Celular."))
                return

            MAX_RETRIES = 3
            success = False
            last_err = ""

            for attempt in range(1, MAX_RETRIES + 1):
                if not self.winfo_exists(): return
                try:
                    self.after(0, lambda att=attempt: self.lbl_record.configure(
                        text=f"Intentando llamada ({att}/{MAX_RETRIES})...", text_color="orange") if self.winfo_exists() else None)
                    
                    url = f"http://{ip}:8080/call?number={full_number}"
                    res = requests.get(url, timeout=5)
                    
                    if res.status_code == 200:
                        success = True
                        database_core.log_telemetry("CALL", f"Llamada exitosa al intento {attempt}", "OK", {"number": full_number})
                        break
                except requests.exceptions.Timeout:
                    last_err = "El celular no respondió a tiempo (Revisa cable o WiFi)"
                    database_core.log_telemetry("CALL", f"Intento {attempt} fallido: {last_err}", "WARNING")
                except requests.exceptions.ConnectionError:
                    last_err = "Conexión rechazada (App GPH Antena dormida o IP incorrecta)"
                    database_core.log_telemetry("CALL", f"Intento {attempt} fallido: {last_err}", "WARNING")
                except Exception as e:
                    last_err = f"Error general: str({e})"
                    database_core.log_telemetry("CALL", f"Intento {attempt} fallido: {last_err}", "WARNING")
                
                if attempt < MAX_RETRIES:
                    time.sleep(1)

            if not self.winfo_exists(): return

            if success:
                self.after(0, lambda: self.enter_in_call_mode(full_number) if self.winfo_exists() else None)
            else:
                self.after(0, lambda: self.lbl_record.configure(text=f"❌ Fallo al conectar ({last_err})", text_color="red") if self.winfo_exists() else None)
                database_core.log_telemetry("CALL", f"Llamada fallida tras {MAX_RETRIES} intentos", "ERROR")

        threading.Thread(target=run_dial_with_retries, daemon=True).start()
    
    def enter_in_call_mode(self, number):
        self.call_window = ctk.CTkToplevel(self.winfo_toplevel())
        self.call_window.title("Llamada en Curso")
        self.call_window.geometry("500x380")
        self.call_window.attributes("-topmost", True)
        self.call_window.protocol("WM_DELETE_WINDOW", lambda: None) 
        self.call_window.configure(fg_color="#011536") 

        info_header = f"⚡ Llamando: {number}"
        if self.current_contact_info:
            cliente_nm = self.current_contact_info.get('clienteNombre', self.current_contact_info.get('clientenombre', ''))
            vivienda = self.current_contact_info.get('vivienda', '')
            if cliente_nm:
                info_header += f"\n👤 {cliente_nm}"
            if vivienda:
                info_header += f" | 🏠 {vivienda}"

        ctk.CTkLabel(self.call_window, text=info_header, font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(pady=(25, 15))

        self.active_status_lbl = ctk.CTkLabel(self.call_window,
            text="⏳ Conectando señal...",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="orange")
        self.active_status_lbl.pack(pady=5)
        
        self.timer_lbl = ctk.CTkLabel(self.call_window, text="00:00",
            font=ctk.CTkFont(size=36, weight="bold"), text_color="white")
        self.timer_lbl.pack(pady=15)
        
        self.incall_controls_frame = ctk.CTkFrame(self.call_window, fg_color="transparent")
        self.incall_controls_frame.pack(pady=5)
        
        self.hold_btn = ctk.CTkButton(self.incall_controls_frame, text="⏸ Pausar",
            fg_color="#E67E22", hover_color="#A04000", height=45, width=140,
            font=ctk.CTkFont(size=12, weight="bold"), command=self.toggle_hold)
        self.hold_btn.pack(side="left", padx=10)
        
        self.mute_btn = ctk.CTkButton(self.incall_controls_frame, text="🎙 Silenciar",
            fg_color="#7D3C98", hover_color="#4A235A", height=45, width=140,
            font=ctk.CTkFont(size=12, weight="bold"), command=self.toggle_mute)
        self.mute_btn.pack(side="left", padx=10)
        
        self.hangup_btn = ctk.CTkButton(self.call_window,
            text="⏹ FINALIZAR Y GUARDAR",
            fg_color="#D8000C", hover_color="#8B0000", height=55, width=320,
            font=ctk.CTkFont(size=16, weight="bold"), command=self.hang_up_and_save)
        self.hangup_btn.pack(pady=(20, 10))

        self.number_entry.configure(state="disabled")
        self.mixer.phone_number = number
        self.mixer.start_time = datetime.now()
        
        self._stop_polling = False
        self._has_answered = False
        self._consecutive_errors = 0

        if not hasattr(self, 'call_attempts'):
            self.call_attempts = 1

        def poll_status():
            time.sleep(3)
            ip = database_core.get_config("phone_ip")
            while not self._stop_polling:
                if not self.winfo_exists(): break
                try:
                    with urllib.request.urlopen(f"http://{ip}:8080/status", timeout=3) as res:
                        st = res.read().decode().strip()
                        self._consecutive_errors = 0
                        
                        if st == "ACTIVE":
                            if not self._has_answered:
                                self._has_answered = True
                                if self.winfo_exists():
                                    self.after(0, lambda: self._on_call_answered(number) if self.winfo_exists() else None)
                        elif st == "DISCONNECTED":
                            if not self._stop_polling:
                                print("[Dialer] Celular reporta DISCONNECTED. Colgando...")
                                if self.winfo_exists():
                                    self.after(0, lambda: self.hang_up_and_save() if self.winfo_exists() else None)
                            break
                except Exception as e:
                    self._consecutive_errors += 1
                    print(f"[Dialer] Error de red consultando estado (Intento {self._consecutive_errors}): {e}")
                    if self._consecutive_errors >= 5:
                         print("[Dialer] Demasiados errores de red. Asumiendo desconexión.")
                         if not self._stop_polling and self.winfo_exists():
                             self.after(0, lambda: self.hang_up_and_save() if self.winfo_exists() else None)
                         break
                
                time.sleep(1)
        
        threading.Thread(target=poll_status, daemon=True).start()

    def _on_call_answered(self, number):
        if not self.winfo_exists(): return
        
        if getattr(self, '_audio_started', False): 
            return
        self._audio_started = True

        print("[Dialer] Llamada contestada. Iniciando audio y cronómetro.")
        
        self.mixer.start_recording(number)
        
        self.active_status_lbl.configure(text="🔴 Llamada Activa y Grabando...", text_color="red")
        self._timer_running = True
        self._timer_seconds = 0
        self._update_timer()

    def _update_timer(self):
        if not self.winfo_exists(): return
        if self._timer_running:
            m, s = divmod(self._timer_seconds, 60)
            self.timer_lbl.configure(text=f"{m:02d}:{s:02d}")
            self._timer_seconds += 1
            self.after(1000, self._update_timer)

    def hang_up_and_save(self):
        self.hangup_btn.configure(state="disabled")
        self._stop_polling = True
        self._timer_running = False
        self.lbl_record.configure(text="⏳ Finalizando...", text_color="orange")
        pc_filepath, duration = self.mixer.stop_recording()

        def hangup_and_download():
            ip = database_core.get_config("phone_ip")
            try:
                urllib.request.urlopen(f"http://{ip}:8080/endcall", timeout=5)
            except:
                pass

            def finalize():
                if not self.winfo_exists(): return
                MIN_VALID_DURATION = 4  
                safe_number = getattr(self.mixer, 'phone_number', 'Desconocido')
                safe_time = getattr(self.mixer, 'start_time', datetime.now())
                
                is_short_call = duration < MIN_VALID_DURATION

                # Registro en BD
                if not is_short_call and pc_filepath and os.path.exists(pc_filepath):
                    c_lote = self.current_contact_info.get('lote', '') if self.current_contact_info else ''
                    c_nombre = self.current_contact_info.get('clienteNombre', self.current_contact_info.get('ncliente', '')) if self.current_contact_info else ''
                    database_core.log_call(safe_number, pc_filepath, safe_time, duration, c_lote, c_nombre)

                # Lógica de reintento O gestión final
                if is_short_call and self.call_attempts < 2:
                    self.call_attempts += 1
                    self.after(500, self._retry_call_sequence)
                else:
                    self.call_attempts = 1
                    # Solo aquí abrimos la gestión, una sola vez.
                    self.after(0, lambda: self._abrir_gestion_final(pc_filepath, duration, is_short_call))

            self.after(0, finalize)
            
        threading.Thread(target=hangup_and_download, daemon=True).start()
    
    def _retry_call_sequence(self):
        """Secuencia limpia para reintento"""
        self.number_entry.configure(state="normal")
        # El start_api_call ya tiene su propia lógica, no llames a messagebox aquí
        self.start_api_call()

    def _abrir_gestion_final(self, path, dur, is_short):
        if self.winfo_exists():
            self.after(0, lambda: self.abrir_modal_con_sync(
                filepath=path, call_number=self.mixer.phone_number,
                call_duration=dur, is_short_call=is_short
            ))
            self._restore_ui()

    def toggle_hold(self):
        self._is_held = not self._is_held; self._update_hold_btn()
        ip = database_core.get_config("phone_ip")
        state = "true" if self._is_held else "false"
        threading.Thread(target=lambda: urllib.request.urlopen(f"http://{ip}:8080/hold?state={state}")).start()

    def _update_hold_btn(self):
        if self._is_held: self.hold_btn.configure(text="▶ Reanudar", fg_color="#27AE60")
        else: self.hold_btn.configure(text="⏸ Pausar", fg_color="#E67E22")

    def toggle_mute(self):
        self._is_muted = not self._is_muted; self.mixer.set_mute(self._is_muted); self._update_mute_btn()
        ip = database_core.get_config("phone_ip")
        state = "true" if self._is_muted else "false"
        threading.Thread(target=lambda: urllib.request.urlopen(f"http://{ip}:8080/mutemike?state={state}")).start()

    def _update_mute_btn(self):
        if self._is_muted: self.mute_btn.configure(text="🔇 Silenciado", fg_color="#E74C3C")
        else: self.mute_btn.configure(text="🎙 Silenciar", fg_color="#7D3C98")

    def _restore_ui(self):
        if not self.winfo_exists(): return
        self._audio_started = False
        if hasattr(self, 'call_window') and self.call_window:
            self.call_window.destroy()
            self.call_window = None
        self.number_entry.configure(state="normal")
        self.number_entry.delete(0, 'end')
        self.lbl_record.configure(text="Estado: En Espera", text_color="gray")

    def abrir_modal_con_sync(self, filepath, call_number="", call_start=None, call_duration=0, contact_info=None, is_short_call=False):
        self.modal_gestion = GestionForm(self.winfo_toplevel(), filepath, call_number=call_number, call_start=call_start, call_duration=call_duration, contact_info=contact_info, is_short_call=is_short_call)
        self.modal_gestion.grab_set()
        self.modal_gestion.focus()

    def _send_request(self, url, on_success=None, on_error=None):
        def go():
            try:
                with urllib.request.urlopen(url, timeout=3) as res:
                    if on_success and self.winfo_exists(): 
                        self.after(0, lambda: on_success(res.getcode()) if self.winfo_exists() else None)
            except Exception as e:
                err_str = str(e)
                if on_error and self.winfo_exists(): 
                    self.after(0, lambda msg=err_str: on_error(msg) if self.winfo_exists() else None)
        threading.Thread(target=go, daemon=True).start()