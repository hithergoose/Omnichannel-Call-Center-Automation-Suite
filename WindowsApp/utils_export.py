import pandas as pd
import os
from tkinter import filedialog, messagebox

def export_contacts_to_excel(contacts_list, filename="cartera_exportada.xlsx"):
    """Exporta una lista de contactos (diccionarios) a un archivo Excel."""
    if not contacts_list:
        messagebox.showwarning("Atención", "No hay datos para exportar.")
        return
        
    try:
        # Convertir a DataFrame
        df = pd.DataFrame(contacts_list)
        
        # Seleccionar columnas relevantes y renombrarlas
        cols = {
            'ncliente': 'Nombre Cliente',
            'lote': 'Lote',
            'nproyecto': 'Proyecto',
            'condominio': 'Condominio',
            'ccelular': 'Celular(es)',
            'cfijo': 'Tel. Fijo(s)',
            'statusTerreno': 'Estatus Terreno',
            'nestatus': 'Estatus Cliente',
            'mesesadeudo': 'Meses Adeudo',
            'anualidad': 'Anualidad',
            'adeudo': 'Mantenimiento',
            'adeudoM': 'Moratorios',
            'adeudo_otros': 'Otros Adeudos',
            'totalAdeudo': 'Adeudo Total',
            'totalAdeudoLL': 'Total + Otros',
            'asesorNombre': 'Asesor',
            'ugestion': 'Última Gestión',
            'fultpago': 'Últ. Pago',
            'fechaFondoReserva': 'Fondo Reserva',
            'fecha1erMensMtto': '1er Mens. Mtto',
            'cemail': 'Email'
        }
        
        # Filtrar solo las que existan en el DF
        existing_cols = [c for c in cols.keys() if c in df.columns]
        df_final = df[existing_cols].rename(columns={c: cols[c] for c in existing_cols})
        
        # Diálogo para guardar archivo
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=filename,
            title="Guardar Exportación"
        )
        
        if filepath:
            df_final.to_excel(filepath, index=False)
            messagebox.showinfo("Éxito", f"Datos exportados correctamente a:\n{filepath}")
            return True
            
    except ImportError:
        messagebox.showerror("Error de Dependencias", "No se encontró la librería 'pandas' o 'openpyxl'.\nPor favor, contacte a soporte o ejecute 'pip install pandas openpyxl'.")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error al exportar: {e}")
        
    return False
