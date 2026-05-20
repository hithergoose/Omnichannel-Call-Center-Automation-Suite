import customtkinter as ctk
import database_core
import threading
import subprocess
import re
import requests
import socket
import concurrent.futures
import os
import time

class ProfileFrame(ctk.CTkFrame):
    def __init__(self, master, mixer=None):
        super().__init__(master)
        self.mixer = mixer
        self.pack(expand=True, fill="both")
        
        self.title_lbl = ctk.CTkLabel(self, text="Configuración del Sistema", font=ctk.CTkFont(size=28, weight="bold"), text_color="#011536")
        self.title_lbl.pack(pady=(40, 20))
        
        desc_lbl = ctk.CTkLabel(self, text="Abre la App GPH Antena en tu celular y usa la Autodetección\n(O ingresa la IP manualmente si estás por Wi-Fi):", font=ctk.CTkFont(size=16), text_color="#333333", justify="center")
        desc_lbl.pack(pady=10)
        
        self.ip_entry = ctk.CTkEntry(self, placeholder_text="La IP aparecerá aquí...", width=320, height=50, font=ctk.CTkFont(size=20, weight="bold"), justify="center", border_color="#2b64d3", text_color="#011536", border_width=2)
        self.ip_entry.pack(pady=15)
        
        current_ip = database_core.get_config("phone_ip")
        if current_ip:
            self.ip_entry.insert(0, current_ip)
            
        btns_frame = ctk.CTkFrame(self, fg_color="transparent")
        btns_frame.pack(pady=(10, 20))

        # --- BOTÓN DE CABLE USB / HOTSPOT ---
        self.auto_usb_btn = ctk.CTkButton(btns_frame, text="⚡ Autodetectar Celular (Por CABLE USB)", fg_color="#F59E0B", hover_color="#D97706", text_color="white", command=self.autodetectar_usb, height=45, width=320, font=ctk.CTkFont(size=14, weight="bold"))
        self.auto_usb_btn.pack(pady=(0, 10))

        # --- BOTÓN WI-FI ---
        self.auto_wifi_btn = ctk.CTkButton(btns_frame, text="🌐 Autodetectar Celular (Por WI-FI)", fg_color="#8B5CF6", hover_color="#7C3AED", text_color="white", command=self.autodetectar_wifi, height=45, width=320, font=ctk.CTkFont(size=14, weight="bold"))
        # self.auto_wifi_btn.pack() # Oculto por petición previa
            
        # --- BOTÓN ABRIR ENLACE MÓVIL ---
        self.btn_abrir_enlace = ctk.CTkButton(self, text="📱 Abrir App 'Enlace Móvil'", fg_color="#0EA5E9", hover_color="#0284C7", text_color="white", command=self.abrir_enlace_movil, height=50, width=300, font=ctk.CTkFont(size=15, weight="bold"))
        self.btn_abrir_enlace.pack(pady=(20, 5))
        
        self.save_btn = ctk.CTkButton(self, text="💾 Guardar IP Manualmente", fg_color="#2b64d3", hover_color="#1d4a99", text_color="white", command=self.save_config, height=40, width=250, font=ctk.CTkFont(size=13, weight="bold"))
        self.save_btn.pack(pady=15)

        self.status_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.status_lbl.pack(pady=20)
        
    def abrir_enlace_movil(self):
        def task():
            try:
                self.after(0, lambda: self.status_lbl.configure(text="Cerrando procesos fantasma...", text_color="orange"))
                subprocess.run('taskkill /F /IM PhoneExperienceHost.exe', shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)
                self.after(0, lambda: self.status_lbl.configure(text="Abriendo Enlace Móvil...", text_color="green"))
                os.system("start ms-phone:")
            except Exception as e:
                self.after(0, lambda: self.status_lbl.configure(text=f"❌ Error al intentar abrir la app: {e}", text_color="red"))
        threading.Thread(target=task, daemon=True).start()
        
    def save_config(self):
        ip = self.ip_entry.get().strip()
        if ip:
            database_core.set_config("phone_ip", ip)
            self.status_lbl.configure(text="⏳ Probando conexión...", text_color="orange")
            
            def test_conn():
                try:
                    res = requests.get(f"http://{ip}:8080/status", timeout=2.0)
                    if res.status_code == 200:
                        self.after(0, lambda: self.status_lbl.configure(text="✅ Guardado. ¡Conexión Exitosa!", text_color="green"))
                    else:
                        self.after(0, lambda: self.status_lbl.configure(text="⚠️ Guardado, pero el celular rechazó la conexión.", text_color="#D97706"))
                except:
                    self.after(0, lambda: self.status_lbl.configure(text="⚠️ Guardado. Asegúrate de que el celular tenga la pantalla encendida.", text_color="#EF4444"))
            
            threading.Thread(target=test_conn, daemon=True).start()
        else:
            self.status_lbl.configure(text="❌ Escribe una IP válida.", text_color="red")

    def autodetectar_usb(self):
        self._set_loading_state(self.auto_usb_btn, "⏳ Escaneando dispositivos locales...")
        def task():
            try:
                # 1. Buscamos Gateways (Por si es Anclaje USB directo)
                result_ip = subprocess.run("ipconfig", shell=True, capture_output=True, text=True, timeout=5, encoding='cp850', errors='ignore')
                gateways = re.findall(r"(?:Puerta de enlace|Gateway)[^\d]*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", result_ip.stdout, re.IGNORECASE)
                
                # 2. Buscamos en la tabla ARP (Por si es Hotspot de Windows o invitados)
                result_arp = subprocess.run("arp -a", shell=True, capture_output=True, text=True, timeout=5, encoding='cp850', errors='ignore')
                arp_ips = re.findall(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s+(?:din|dyn|dinámico|dynamic)", result_arp.stdout, re.IGNORECASE)
                
                # Juntamos todas las IPs sospechosas
                todas_ips = list(set(gateways + arp_ips))
                # Limpiamos IPs internas de Windows que no nos sirven
                todas_ips =[ip for ip in todas_ips if not ip.startswith("224.") and not ip.startswith("239.") and not ip.endswith(".255")]

                if not todas_ips:
                    self.after(0, lambda: self._on_auto_fail(self.auto_usb_btn, "⚡ Autodetectar Celular (Por CABLE USB)", "No se detectaron dispositivos conectados."))
                    return

                # Probamos a cuál de todos los dispositivos responde la App
                found_ip = self._find_responsive_ip(todas_ips)

                if found_ip:
                    self.after(0, lambda: self._on_auto_success(self.auto_usb_btn, "⚡ Autodetectar Celular (Por CABLE USB)", found_ip))
                else:
                    self.after(0, lambda: self._on_auto_fail(self.auto_usb_btn, "⚡ Autodetectar Celular (Por CABLE USB)", "Celular no responde. Mantén la pantalla ENCENDIDA y la app abierta."))
            
            except subprocess.TimeoutExpired:
                 self.after(0, lambda: self._on_auto_fail(self.auto_usb_btn, "⚡ Autodetectar Celular (Por CABLE USB)", "El escaneo tardó demasiado. Reintenta."))
            except Exception as e:
                self.after(0, lambda: self._on_auto_fail(self.auto_usb_btn, "⚡ Autodetectar Celular (Por CABLE USB)", f"Error del sistema: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def autodetectar_wifi(self):
        # ... (Mantengo la función por si la reactivas después)
        pass

    def _set_loading_state(self, btn, text):
        btn.configure(state="disabled", text=text)
        self.status_lbl.configure(text=text, text_color="orange")

    def _on_auto_success(self, btn, original_text, ip):
        btn.configure(state="normal", text=original_text)
        self.ip_entry.delete(0, 'end')
        self.ip_entry.insert(0, ip)
        self.save_config()
        self.status_lbl.configure(text=f"✅ ¡Celular encontrado! IP: {ip}", text_color="green")

    def _on_auto_fail(self, btn, original_text, msg):
        btn.configure(state="normal", text=original_text)
        self.status_lbl.configure(text=f"❌ Falló: {msg}", text_color="red")

    def _get_my_local_ip(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
            except: return "127.0.0.1"

    def _find_responsive_ip(self, ip_list):
        def check_ip(ip):
            try:
                if requests.get(f"http://{ip}:8080/status", timeout=1.5).status_code == 200: return ip
            except: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            for res in executor.map(check_ip, ip_list):
                if res: return res
        return None