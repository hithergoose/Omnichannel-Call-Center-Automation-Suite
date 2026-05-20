import webview
import database_core
import os
import threading
import customtkinter as ctk
import ui_modals
import utils_export

# --- CONFIGURACIÓN PARA QUE TKINTER NO CHOCUE CON LA WEB ---
class TkinterEngine(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.root = None
        self.ready = threading.Event()

    def run(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.ready.set()
        self.root.mainloop()

    def abrir_ficha(self, cliente_data):
        if self.root:
            self.root.after(0, lambda: self._dibujar_modal(cliente_data))

    def _dibujar_modal(self, cliente_data):
        modal = ui_modals.ContactDetailsModal(self.root, cliente_data)
        modal.attributes("-topmost", True)
        modal.grab_set()
        modal.focus()

    def lanzar_excel(self, datos):
        if self.root:
            # Lo ejecutamos en el hilo de Tkinter para que la ventana de "Guardar como..." no falle
            self.root.after(0, lambda: utils_export.export_contacts_to_excel(datos))

tk_engine = TkinterEngine()
tk_engine.start()
tk_engine.ready.wait() 

class WebApi:
    def __init__(self):
        print("[Python] Iniciando API Web...")
        database_core.init_db()

    def get_filtros_iniciales(self):
        proyectos = ["Todos"] + database_core.get_unique_values("nproyecto", table="contactos")
        return {"proyectos": proyectos}

    def get_condominios(self, proyecto):
        return ["Todos"] + database_core.get_condominios_list(proyecto if proyecto != "Todos" else None)

    def get_cartera_data(self, filtros=None):
        if not filtros: filtros = {}
        proy = filtros.get("proyecto", "Todos")
        cond = filtros.get("condominio", "Todos")
        sin_tel = filtros.get("sinTelefono", False)
        
        contactos = database_core.get_contactos(
            query=None, proyecto=proy if proy != "Todos" else None,
            condominio=cond if cond != "Todos" else None,
            col_filters=None, sin_telefono=sin_tel,
            limit=200000, offset=0
        )
        
        for c in contactos:
            c['totalAdeudoLL_raw'] = database_core.normalize_numeric(c.get('totalAdeudoLL'))
            c['totalAdeudoLL'] = f"${c['totalAdeudoLL_raw']:,.2f}"
            c['adeudo'] = f"${database_core.normalize_numeric(c.get('adeudo')):,.2f}"
            c['adeudoM'] = f"${database_core.normalize_numeric(c.get('adeudoM')):,.2f}"
            c['adeudo_otros'] = f"${database_core.normalize_numeric(c.get('adeudo_otros')):,.2f}"
            c['anualidad'] = f"${database_core.normalize_numeric(c.get('anualidad')):,.2f}"
            c['totalAdeudo'] = f"${database_core.normalize_numeric(c.get('totalAdeudo')):,.2f}"
            
            for key, val in c.items():
                if val is None or val == "None": c[key] = "-"
                
        print(f"[Python] ¡{len(contactos)} registros enviados a la web!")
        import json
        return json.dumps(contactos) # <--- EL TRUCO: Lo convertimos en un solo texto

    def exportar_excel_datos(self, datos):
        """Recibe los datos EXACTOS que el usuario filtró en la pantalla web y abre Excel"""
        print(f"[Python] Exportando {len(datos)} registros a Excel...")
        tk_engine.lanzar_excel(datos)
        return True

    def hacer_llamada(self, numero, cliente_data):
        print(f"\n[Python] 📞 ¡ORDEN DE LLAMADA RECIBIDA DESDE LA WEB!")
        print(f"Marcando al: {numero}")
        if tk_engine.root:
            tk_engine.root.after(0, lambda: self._alerta_llamada(numero, cliente_data))
        return True
        
    def _alerta_llamada(self, num, data):
        import tkinter.messagebox as msgbox
        msgbox.showinfo("Llamada en Curso", f"Simulando llamada al: {num}\nCliente: {data.get('ncliente')}")

    def abrir_modal_detalles(self, cliente_data):
        tk_engine.abrir_ficha(cliente_data)

if __name__ == '__main__':
    api = WebApi()
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')
    
    window = webview.create_window(
        title='Central Telefónica GPH (Web Edition)', 
        url=html_path, js_api=api, width=1400, height=900, background_color='#011536'
    )
    webview.start(debug=False)