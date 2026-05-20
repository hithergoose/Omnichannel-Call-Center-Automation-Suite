package com.example.llamadasgph.call

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.util.Log
import androidx.core.app.ActivityCompat
import fi.iki.elonen.NanoHTTPD
import java.io.File
import java.io.FileInputStream

class HttpServerManager(private val context: Context, port: Int = 8080) : NanoHTTPD(port) {

    private val audioRecorder = AudioRecorder(context)
    private val TAG = "HttpServerManager"

    val isServerRunning: Boolean
        get() = isAlive()

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri
        val params = session.parameters

        Log.d(TAG, "Petición recibida: $uri")

        // Si es una llamada y no hay call activo, iniciar tracking
        if (uri == "/call" && CallManager.currentCall.value == null) {
            CallManager.setOutgoingNumber(params["number"]?.firstOrNull() ?: "")
        }

        return when (uri) {
            "/call"      -> handleCall(params)
            "/endcall"   -> handleEndCall()
            "/hold"      -> handleHold(params)
            "/mutemike"  -> handleMuteMike(params)
            "/getaudio"  -> handleGetAudio()
            "/status"    -> handleStatus()
            "/audiostream" -> handleAudioStream()
            "/ping"      -> newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, "Pong! El sistema GPH está escuchando.")
            else         -> newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Ruta no encontrada. Intenta /call, /endcall, /hold, /mutemike, /getaudio, /status o /ping")
        }
    }

    // ── LLAMAR ──────────────────────────────────────────────────────────────

    private fun handleCall(params: Map<String, List<String>>): Response {
        val numberList = params["number"]
        if (numberList.isNullOrEmpty()) {
            return newFixedLengthResponse(Response.Status.BAD_REQUEST, MIME_PLAINTEXT, "Falta el parámetro 'number'. Ej: /call?number=+528180001111")
        }

        val number = numberList[0]
        Log.d(TAG, "Intentando llamar a: $number")

        return try {
            // ACTION_CALL hace la llamada directamente (requiere CALL_PHONE permission)
            val intent = Intent(Intent.ACTION_CALL).apply {
                data = Uri.parse("tel:$number")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            Log.d(TAG, "Llamada iniciada exitosamente")

            // Eliminado: La activación forzada del altavoz causaba que Android colgara
            // la llamada por conflicto de permisos/estado con InCallService.
            // TelecomManager/InCallService maneja el audio de forma nativa.

            // INICIAR GRABACIÓN DESPUÉS DE UN DELAY
            // No dependemos de CallManager porque ACTION_CALL no siempre pasa por CallService
            Thread {
                Thread.sleep(4000) // Esperar 4 segundos a que la llamada se establezca
                try {
                    if (!audioRecorder.isRecording) {
                        val started = audioRecorder.startRecording(number)
                        Log.d(TAG, "Grabación iniciada tras delay: $started")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error iniciando grabación: ${e.message}")
                }
            }.start()

            newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, "✅ Llamando a $number (altavoz activado)")
        } catch (e: Exception) {
            Log.e(TAG, "Error al llamar: $e")
            newFixedLengthResponse(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Error del servidor: ${e.message}")
        }
    }

    // ── COLGAR ───────────────────────────────────────────────────────────────

    private fun handleEndCall(): Response {
        // 1. Detener grabación local
        try {
            audioRecorder.stopRecording()
            Log.d(TAG, "Grabación detenida. Archivo: ${audioRecorder.getRecordingPath()}")
        } catch (e: Exception) {
            Log.e(TAG, "Error deteniendo grabación: $e")
        }

        // 2. Intentar colgar: Método A → CallManager (InCallService)
        var disconnected = false
        try {
            val call = CallManager.currentCall.value
            if (call != null) {
                CallManager.disconnectCall()
                CallManager.clearOutgoingNumber()
                disconnected = true
                Log.d(TAG, "Llamada colgada vía CallManager")
            } else {
                // Si no hay llamada activa pero hay un número saliente marcándose, limpiarlo
                CallManager.clearOutgoingNumber()
            }
        } catch (e: Exception) {
            Log.e(TAG, "CallManager.disconnectCall falló: $e")
        }

        // 3. Intentar colgar: Método B → TelecomManager (fallback para API < 28 o si no somos dialer default)
        if (!disconnected) {
            try {
                val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as android.telecom.TelecomManager
                if (ActivityCompat.checkSelfPermission(context, android.Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED) {
                    @Suppress("DEPRECATION")
                    val success = telecomManager.endCall()
                    disconnected = success
                    Log.d(TAG, "Llamada colgada vía TelecomManager: $success")
                }
            } catch (e: Exception) {
                Log.e(TAG, "TelecomManager.endCall falló: $e")
            }
        }

        // 4. Restaurar modo de audio
        try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.isSpeakerphoneOn = false
            am.mode = AudioManager.MODE_NORMAL
            Log.d(TAG, "Audio restaurado a NORMAL")
        } catch (_: Exception) {}

        return if (disconnected) {
            newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, "✅ Llamada finalizada en el celular.")
        } else {
            newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, "⚠ No se pudo colgar automáticamente. Cuelga manualmente en el celular.")
        }
    }

    // ── PAUSAR ───────────────────────────────────────────────────────────────

    private fun handleHold(params: Map<String, List<String>>): Response {
        val hold = params["state"]?.firstOrNull() == "true"
        return try {
            val call = CallManager.currentCall.value
            if (call != null) {
                CallManager.setHold(hold)
                val msg = if (hold) "✅ Llamada en espera." else "✅ Llamada reanudada."
                newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, msg)
            } else {
                // Fallback: si no tenemos InCallService, no podemos pausar
                newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, "⚠ Pausar no disponible (configura la app como dialer predeterminado).")
            }
        } catch (e: Exception) {
            newFixedLengthResponse(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Error al pausar: ${e.message}")
        }
    }

    // ── SILENCIAR ────────────────────────────────────────────────────────────

    private fun handleMuteMike(params: Map<String, List<String>>): Response {
        val mute = params["state"]?.firstOrNull() == "true"
        return try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.isMicrophoneMute = mute
            val msg = if (mute) "✅ Micrófono silenciado." else "✅ Micrófono activado."
            newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, msg)
        } catch (e: Exception) {
            newFixedLengthResponse(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Error al silenciar: ${e.message}")
        }
    }

    // ── DESCARGAR AUDIO GRABADO ─────────────────────────────────────────────

    private fun handleGetAudio(): Response {
        val path = audioRecorder.getRecordingPath()
        if (path != null) {
            val file = File(path)
            if (file.exists()) {
                Log.d(TAG, "Sirviendo archivo de audio: $path (${file.length()} bytes)")
                val fis = FileInputStream(file)
                return newFixedLengthResponse(Response.Status.OK, "audio/mp4", fis, file.length())
            }
        }
        return newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "No hay grabación disponible.")
    }

    // ── ESTADO DE LA LLAMADA ────────────────────────────────────────────────

    private fun handleStatus(): Response {
        val call = CallManager.currentCall.value
        val state = call?.state ?: android.telecom.Call.STATE_DISCONNECTED
        
        var statusStr = when (state) {
            android.telecom.Call.STATE_ACTIVE -> "ACTIVE"
            android.telecom.Call.STATE_DIALING -> "DIALING"
            android.telecom.Call.STATE_RINGING -> "RINGING"
            android.telecom.Call.STATE_HOLDING -> "HOLDING"
            else -> "DISCONNECTED"
        }
        
        // Fix para evitar corte falso al instante:
        // Si no hay Call activo aún, pero tenemos un número en marcación, significa que
        // InCallService está apenas levantándose.
        if (statusStr == "DISCONNECTED" && CallManager.outgoingNumber.value != null) {
            statusStr = "STARTING"
        }

        return newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, statusStr)
    }

    // ── STREAMING DE AUDIO EN TIEMPO REAL ────────────────────────────────────

    private fun handleAudioStream(): Response {
        val stream = audioRecorder.createStreamInputStream()
        return if (stream != null) {
            Log.d(TAG, "Iniciando streaming de audio en tiempo real...")
            // Usamos audio/pcm en lugar de audio/wav porque es PCM directo, no un archivo WAV con headers
            newFixedLengthResponse(Response.Status.OK, "audio/pcm", stream, -1)
        } else {
            newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "No hay grabación activa para streamear.")
        }
    }
}
