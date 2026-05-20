import os
import time
import subprocess
import threading
import requests
import numpy as np
from datetime import datetime

import pyaudiowpatch as pyaudio
import soundfile as sf
import database_core

SAMPLE_RATE   = 48000  # Calidad de Estudio para máxima fidelidad
CHANNELS      = 1
SAMPLE_FMT    = pyaudio.paInt16
CHUNK         = 1024

class AudioMixer:
    def __init__(self):
        print(f"[AudioMixer] Instancia creada en {datetime.now()}")
        self.p = pyaudio.PyAudio()
        self.is_recording   = False
        self.is_muted       = False
        user_folder = os.path.expanduser("~")
        self.output_dir = os.path.join(user_folder, "Grabaciones_GPH")
        os.makedirs(self.output_dir, exist_ok=True)

        self._frames_loopback = []
        self._frames_micro    = []
        self._lock_loopback   = threading.Lock()
        self._lock_micro      = threading.Lock()

        self.phone_number   = "Desconocido"
        self.start_time     = None
        self._thread_loop   = None
        self._thread_micro  = None

    def start_recording(self, phone_number):
        if self.is_recording:
            return True

        self.is_recording       = True
        self.is_muted           = False
        self._frames_loopback   = []
        self._frames_micro      = []
        self.phone_number       = phone_number
        self.start_time         = datetime.now()

        # --- Loopback (Voz del cliente) ---
        loopback_dev = self._get_loopback_device()
        if loopback_dev:
            try:
                stream_lb = self.p.open(
                    format=SAMPLE_FMT,
                    channels=loopback_dev["maxInputChannels"],
                    rate=int(loopback_dev["defaultSampleRate"]),
                    frames_per_buffer=CHUNK,
                    input=True,
                    input_device_index=loopback_dev["index"],
                )
                self._thread_loop = threading.Thread(
                    target=self._record_loopback_channel,
                    args=(stream_lb, loopback_dev["maxInputChannels"], int(loopback_dev["defaultSampleRate"])),
                    daemon=True,
                )
                self._thread_loop.start()
            except Exception as e:
                print(f"[AudioMixer] ERROR abriendo Loopback: {e}")
        else:
            print("[AudioMixer] ADVERTENCIA: No se encontró Loopback.")

        # --- Micrófono (Voz del agente) ---
        micro_dev_info = self._get_default_microphone()
        if micro_dev_info:
            try:
                stream_mic = self.p.open(
                    format=SAMPLE_FMT,
                    channels=1,
                    rate=SAMPLE_RATE, # Siempre 48000 Hz
                    frames_per_buffer=CHUNK,
                    input=True,
                    input_device_index=micro_dev_info["index"],
                )
                self._thread_micro = threading.Thread(
                    target=self._record_mic_channel,
                    args=(stream_mic,),
                    daemon=True,
                )
                self._thread_micro.start()
            except Exception as e:
                print(f"[AudioMixer] ERROR abriendo Micrófono: {e}")
        else:
            print("[AudioMixer] ADVERTENCIA: No se encontró micrófono.")

        return True

    def _record_loopback_channel(self, stream, channels, rate):
        try:
            while self.is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.int16)
                
                if channels > 1:
                    arr = arr.reshape(-1, channels).mean(axis=1).astype(np.int16)
                    
                if rate != SAMPLE_RATE:
                    n_out = int(len(arr) * SAMPLE_RATE / rate)
                    if n_out > 0:
                        indices_original = np.arange(len(arr))
                        indices_nuevos = np.linspace(0, len(arr) - 1, n_out)
                        arr = np.interp(indices_nuevos, indices_original, arr).astype(np.int16)

                with self._lock_loopback:
                    self._frames_loopback.append(arr.tobytes())
        except Exception as e:
            print(f"[AudioMixer] Error en hilo Loopback: {e}")
        finally:
            try: stream.stop_stream(); stream.close()
            except: pass

    def _record_mic_channel(self, stream):
        try:
            while self.is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                if self.is_muted:
                    data = b'\x00' * len(data)
                with self._lock_micro:
                    self._frames_micro.append(data)
        except Exception as e:
            print(f"[AudioMixer] Error en hilo Micrófono: {e}")
        finally:
            try: stream.stop_stream(); stream.close()
            except: pass

    def stop_recording(self):
        if not self.is_recording: return None, 0
        self.is_recording = False
        
        # Darle un respiro a los hilos para que terminen de guardar
        time.sleep(0.5)

        with self._lock_loopback: saved_lb  = list(self._frames_loopback)
        with self._lock_micro: saved_mic = list(self._frames_micro)

        duration  = int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S") if self.start_time else "error"
        filepath  = os.path.join(self.output_dir, f"Llamada_{self.phone_number}_{timestamp}.wav")

        try:
            n = max(len(saved_lb), len(saved_mic))
            if n == 0: return None, 0

            silence = b'\x00' * (CHUNK * 2) # Usamos un chunk de 16bits (2 bytes)
            mixed_frames = []
            
            for i in range(n):
                lb_data = saved_lb[i]  if i < len(saved_lb)  else silence
                mic_data = saved_mic[i] if i < len(saved_mic) else silence
                
                m = min(len(lb_data), len(mic_data))
                if m == 0: continue
                
                lb_arr  = np.frombuffer(lb_data[:m],  dtype=np.int16).astype(np.float32)
                mic_arr = np.frombuffer(mic_data[:m], dtype=np.int16).astype(np.float32)
                
                mixed_arr = np.clip(lb_arr + mic_arr, -32768, 32767).astype(np.int16)
                mixed_frames.append(mixed_arr.tobytes())

            raw_audio = b''.join(mixed_frames)
            audio_array = np.frombuffer(raw_audio, dtype=np.int16)
            
            filepath_mp3 = filepath.replace(".wav", ".mp3")
            
            try:
                sf.write(filepath_mp3, audio_array, SAMPLE_RATE, format='mp3')
                final_path = filepath_mp3
            except Exception as mp3_exc:
                print(f"[AudioMixer] Falló codificación MP3, usando WAV: {mp3_exc}")
                sf.write(filepath, audio_array, SAMPLE_RATE, format='wav')
                final_path = filepath
                
            print(f"[AudioMixer] Grabación guardada: {final_path} ({duration}s)")
            return final_path, duration

        except Exception as e:
            print(f"[AudioMixer] Error guardando archivo PC: {e}")
            return None, 0
    
    def set_mute(self, muted: bool):
        self.is_muted = muted

    def check_bluetooth_connected(self):
        """
        Verifica si hay un CELULAR Bluetooth conectado.
        Usa un filtro estricto para ignorar audífonos (TWS, Buds, etc) y drivers genéricos.
        """
        print("[AudioMixer] Iniciando escaneo ESTRICTO de celulares Bluetooth...")
        
        try:
            cmd =["powershell", "-NoProfile", "-Command", "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object { $_.Present -eq $true } | Select-Object FriendlyName | ConvertTo-Json -Compress"]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5).decode('cp850', errors='ignore').strip()
            
            if output and output != "null" and output != "":
                import json
                try:
                    devices = json.loads(output)
                except: # A veces PowerShell solo devuelve un string, no un JSON
                    devices = [{"FriendlyName": output.replace('"', '')}]
                
                if isinstance(devices, dict): devices = [devices]
                elif isinstance(devices, str): devices = [{"FriendlyName": devices}]
                elif isinstance(devices, list) and len(devices) > 0 and isinstance(devices[0], str):
                    devices = [{"FriendlyName": d} for d in devices]
                
                # LA LISTA NEGRA DEFINITIVA: Ignora todo lo que no sea un celular
                blacklist =["servicio", "enumerador", "le", "microsoft", "intel", "wireless", "adapter", "red", "personal", "avrcp", "gatt", "a2dp", "hid", "realtek", "qualcomm", "mediatek", "rfcomm", "protocol", "tdi", "system", "tws", "buds", "earbuds", "airpods", "headset", "headphone", "bocina", "speaker", "audio", "stereo", "hands-free", "manos libres"]
                
                for d in devices:
                    fname = d.get('FriendlyName', '')
                    if not fname: continue
                    
                    fname_lower = fname.lower()
                    if any(b in fname_lower for b in blacklist):
                        continue # Si contiene una palabra prohibida, no es un celular, lo ignoramos.
                        
                    # Si pasó todos los filtros, es el nombre del celular. ¡Lo encontramos!
                    print(f"[AudioMixer] ✅ Celular Detectado: {fname}")
                    return True, fname
                    
        except Exception as e:
            print(f"[AudioMixer] Error en escaneo BT estricto: {e}")

        print("[AudioMixer] ❌ No se detectó ningún celular válido.")
        return False, "Ninguno"

    def _get_loopback_device(self):
        """Captura el audio de la PC usando WASAPI Loopback (Ignorando Mezcla Estéreo)"""
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out_index = wasapi_info.get('defaultOutputDevice')
            
            if default_out_index is None:
                print("[AudioMixer] ❌ No hay audífonos o altavoces conectados.")
                return None
                
            default_out_info = self.p.get_device_info_by_index(default_out_index)
            print(f"[AudioMixer] Salida de audio actual: '{default_out_info['name']}'")

            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('hostApi') == wasapi_info['index'] and dev.get('isLoopbackDevice'):
                    if default_out_info['name'] in dev['name']:
                        print(f"[AudioMixer] ✅ Capturador WASAPI anclado: '{dev['name']}'")
                        return dev
                        
            print("[AudioMixer] ❌ CRÍTICO: Windows no permitió el Loopback digital.")
        except Exception as e:
            print(f"[AudioMixer] Error configurando WASAPI Loopback: {e}")
        return None

    def _get_default_microphone(self):
        """
        Busca el micrófono, priorizando la API MME para obtener la señal "cruda"
        y evitar filtros de cancelación de eco de diademas gaming.
        """
        try:
            print("[AudioMixer] Buscando micrófono en modo 'RAW' (MME)...")
            
            # Buscamos el dispositivo predeterminado en la API MME
            mme_api_info = self.p.get_host_api_info_by_type(pyaudio.paMME)
            default_mic_index = mme_api_info.get('defaultInputDevice')

            if default_mic_index is not None and default_mic_index != -1:
                dev = self.p.get_device_info_by_index(default_mic_index)
                if dev["maxInputChannels"] > 0:
                    print(f"[AudioMixer] ✅ Micrófono MME (RAW) anclado: '{dev['name']}'")
                    return dev

            print("[AudioMixer] ⚠️ No se encontró MME. Buscando por nombre...")
            # Si MME falla, buscamos manualmente el nombre "OMEN" o "Headset"
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                name = dev.get("name", "").lower()
                if "omen" in name and dev["maxInputChannels"] > 0:
                     print(f"[AudioMixer] ✅ Micrófono OMEN encontrado por nombre: '{dev['name']}'")
                     return dev

            # Como último recurso, el predeterminado del sistema
            default_mic_info = self.p.get_default_input_device_info()
            print(f"[AudioMixer] Usando micrófono del sistema como fallback: '{default_mic_info['name']}'")
            return default_mic_info

        except Exception as e:
            print(f"[AudioMixer] Error crítico buscando micrófono: {e}")
        return None

    def terminate(self):
        self.is_recording = False
        try:
            self.p.terminate()
        except Exception:
            pass