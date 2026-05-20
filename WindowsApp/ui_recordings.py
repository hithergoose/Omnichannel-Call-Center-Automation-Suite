import customtkinter as ctk
import database_core
import os

class RecordingsFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(expand=True, fill="both")
        
        self.title_lbl = ctk.CTkLabel(self, text="Historial de Grabaciones", font=ctk.CTkFont(size=26, weight="bold"), text_color="#011536")
        self.title_lbl.pack(pady=20)
        
        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=650, height=400, fg_color="#f0f2f5", scrollbar_button_color="#2b64d3")
        self.scrollable_frame.pack(pady=10, padx=20, expand=True, fill="both")
        
        self.refresh_btn = ctk.CTkButton(self, text="Actualizar Lista", fg_color="#011536", hover_color="#1d4a99", text_color="white", command=self.load_data)
        self.refresh_btn.pack(pady=15)
        
        self.load_data()

    def load_data(self):
        # Clear existing
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        calls = database_core.get_all_calls()
        
        # Filtramos para mostrar SOLO archivos que existen localmente y que son .mp3
        valid_calls = [c for c in calls if os.path.exists(c[4]) and c[4].endswith(".mp3")]

        if not valid_calls:
            # Removed 'slant="italic"' as it can cause crashes with CTkFont on some systems.
            ctk.CTkLabel(self.scrollable_frame, text="No hay grabaciones MP3 disponibles.", text_color="#011536", font=ctk.CTkFont(size=14)).pack(pady=40)
            return

        for call in valid_calls:
            # call tuple: (id, phone_number, start_time, duration_sec, file_path)
            cid, phone, time, dur, path = call
            
            item_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="white", corner_radius=8)
            item_frame.pack(fill="x", pady=6, padx=10)
            
            info_text = f"📞 {phone}   |   🕒 {time}   |   ⏱ {dur}s"
            lbl = ctk.CTkLabel(item_frame, text=info_text, font=ctk.CTkFont(size=14, weight="bold"), text_color="#011536")
            lbl.pack(side="left", padx=15, pady=12)
            
            # Botón de Reproducir
            play_btn = ctk.CTkButton(item_frame, text="▶ Reproducir", width=100, fg_color="#2b64d3", hover_color="#1d4a99", command=lambda p=path: self.play_audio(p))
            play_btn.pack(side="right", padx=15, pady=12)

    def play_audio(self, filepath):
        if os.path.exists(filepath):
            # En Windows esto abre el reproductor predeterminado de Medios
            os.startfile(filepath)
        else:
            print(f"El archivo no existe: {filepath}")
