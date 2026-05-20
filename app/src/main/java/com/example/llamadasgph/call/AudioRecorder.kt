package com.example.llamadasgph.call

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Environment
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.io.RandomAccessFile
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import android.media.audiofx.NoiseSuppressor
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl

/**
 * Audio recorder that uses AudioRecord (low-level API) instead of MediaRecorder.
 * As the InCallService (default dialer), AudioRecord can capture call audio
 * on most devices running Android 10+.
 *
 * Also provides a streaming InputStream for real-time audio to the PC.
 */
class AudioRecorder(private val context: Context) {

    companion object {
        private const val TAG = "AudioRecorder"
        const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }

    private var audioRecord: AudioRecord? = null
    @Volatile
    var isRecording = false
        private set
    private var currentFilePath: String? = null
    private var recordThread: Thread? = null

    // ── Ring buffer for real-time streaming to PC ────────────────────────────
    private val RING_SIZE = SAMPLE_RATE * 2 * 30  // 30 seconds of 16kHz mono 16-bit
    private val ringBuffer = ByteArray(RING_SIZE)
    @Volatile
    private var ringWritePos = 0L
    private val streamLock = Object()

    // ── Recording ───────────────────────────────────────────────────────────

    fun startRecording(phoneNumber: String): Boolean {
        if (isRecording) return true

        val dir = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "Gestiones GPH")
        if (!dir.exists()) dir.mkdirs()

        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        val file = File(dir, "Llamada_${phoneNumber}_${timestamp}.wav")
        currentFilePath = file.absolutePath

        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        if (bufferSize == AudioRecord.ERROR_BAD_VALUE || bufferSize == AudioRecord.ERROR) {
            Log.e(TAG, "Buffer size inválido para la configuración de audio")
            return false
        }

        // Intentar fuentes de audio. VOICE_COMMUNICATION es la fuente correcta para capturar
        // el audio de la llamada en Android 10+. MIC solo captura el altavoz con eco.
        val sources = intArrayOf(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            MediaRecorder.AudioSource.MIC,
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            MediaRecorder.AudioSource.DEFAULT
        )

        for (source in sources) {
            val sourceName = when (source) {
                MediaRecorder.AudioSource.MIC -> "MIC"
                MediaRecorder.AudioSource.VOICE_COMMUNICATION -> "VOICE_COMMUNICATION"
                MediaRecorder.AudioSource.VOICE_RECOGNITION -> "VOICE_RECOGNITION"
                else -> "DEFAULT"
            }

            try {
                val ar = AudioRecord(source, SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT, bufferSize * 4)
                if (ar.state == AudioRecord.STATE_INITIALIZED) {
                    // Activar mejoras de audio si el hardware lo permite
                    if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(ar.audioSessionId)?.enabled = true
                    if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(ar.audioSessionId)?.enabled = true
                    if (AutomaticGainControl.isAvailable()) AutomaticGainControl.create(ar.audioSessionId)?.enabled = true

                    ar.startRecording()
                    audioRecord = ar
                    isRecording = true
                    ringWritePos = 0

                    recordThread = Thread {
                        writePcmToWav(file, bufferSize)
                    }
                    recordThread!!.start()

                    Log.d(TAG, "✅ Grabación iniciada con fuente $sourceName → ${file.absolutePath}")
                    return true
                } else {
                    ar.release()
                    Log.w(TAG, "Fuente $sourceName no se pudo inicializar")
                }
            } catch (e: Exception) {
                Log.w(TAG, "Fuente $sourceName falló: ${e.message}")
                try { audioRecord?.release() } catch (_: Exception) {}
                audioRecord = null
            }
        }

        Log.e(TAG, "❌ Ninguna fuente de audio funcionó")
        return false
    }

    // ── Capture loop: writes to WAV file AND ring buffer ────────────────────

    private fun writePcmToWav(file: File, bufferSize: Int) {
        var totalDataSize = 0
        try {
            FileOutputStream(file).use { fos ->
                // Write placeholder WAV header (44 bytes, will be updated later)
                fos.write(ByteArray(44))

                val buffer = ByteArray(bufferSize)
                while (isRecording) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: -1
                    if (read > 0) {
                        // 1. Write to WAV file
                        fos.write(buffer, 0, read)
                        totalDataSize += read

                        // 2. Copy to ring buffer for streaming
                        synchronized(streamLock) {
                            for (i in 0 until read) {
                                ringBuffer[((ringWritePos + i) % RING_SIZE).toInt()] = buffer[i]
                            }
                            ringWritePos += read
                            streamLock.notifyAll()
                        }
                    }
                }
            }

            // Update WAV header with final sizes
            updateWavHeader(file, totalDataSize)
            Log.d(TAG, "✅ WAV guardado: ${file.absolutePath} (${file.length()} bytes, $totalDataSize datos PCM)")

        } catch (e: Exception) {
            Log.e(TAG, "Error escribiendo WAV: ${e.message}")
        }
    }

    private fun updateWavHeader(file: File, dataSize: Int) {
        try {
            RandomAccessFile(file, "rw").use { raf ->
                val fileSize = raf.length()
                raf.seek(0)

                // RIFF header
                raf.writeBytes("RIFF")
                raf.write(intToLE((fileSize - 8).toInt()))
                raf.writeBytes("WAVE")

                // fmt sub-chunk
                raf.writeBytes("fmt ")
                raf.write(intToLE(16))           // sub-chunk size
                raf.write(shortToLE(1))          // PCM format
                raf.write(shortToLE(1))          // mono
                raf.write(intToLE(SAMPLE_RATE))  // sample rate
                raf.write(intToLE(SAMPLE_RATE * 2))  // byte rate
                raf.write(shortToLE(2))          // block align
                raf.write(shortToLE(16))         // bits per sample

                // data sub-chunk
                raf.writeBytes("data")
                raf.write(intToLE(dataSize))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error actualizando header WAV: ${e.message}")
        }
    }

    private fun intToLE(value: Int) = byteArrayOf(
        (value and 0xFF).toByte(),
        (value shr 8 and 0xFF).toByte(),
        (value shr 16 and 0xFF).toByte(),
        (value shr 24 and 0xFF).toByte()
    )

    private fun shortToLE(value: Int) = byteArrayOf(
        (value and 0xFF).toByte(),
        (value shr 8 and 0xFF).toByte()
    )

    // ── Streaming InputStream for /audiostream endpoint ─────────────────────

    /**
     * Creates a blocking InputStream that yields audio data in real-time
     * from the ring buffer. Each HTTP client gets its own read position.
     */
    fun createStreamInputStream(): InputStream? {
        if (!isRecording) return null

        val startPos = ringWritePos  // Start reading from current position
        return object : InputStream() {
            private var readPos = startPos

            override fun read(): Int {
                val buf = ByteArray(1)
                val n = read(buf, 0, 1)
                return if (n <= 0) -1 else buf[0].toInt() and 0xFF
            }

            override fun read(b: ByteArray, off: Int, len: Int): Int {
                if (!isRecording && readPos >= ringWritePos) return -1

                synchronized(streamLock) {
                    // Wait until new data is available
                    while (readPos >= ringWritePos) {
                        if (!isRecording) return -1
                        try {
                            (streamLock as Object).wait(500)
                        } catch (_: InterruptedException) {
                            return -1
                        }
                    }

                    val available = (ringWritePos - readPos).toInt().coerceAtMost(len)
                        .coerceAtMost(RING_SIZE)  // Never read more than ring buffer
                    for (i in 0 until available) {
                        b[off + i] = ringBuffer[((readPos + i) % RING_SIZE).toInt()]
                    }
                    readPos += available
                    return available
                }
            }
        }
    }

    // ── Stop ────────────────────────────────────────────────────────────────

    fun stopRecording() {
        if (!isRecording) return
        isRecording = false

        // Wake up any streaming readers
        synchronized(streamLock) { streamLock.notifyAll() }

        try {
            recordThread?.join(3000)
            audioRecord?.stop()
            audioRecord?.release()
            Log.d(TAG, "Grabación detenida: $currentFilePath")
        } catch (e: Exception) {
            Log.e(TAG, "Error deteniendo: ${e.message}")
        } finally {
            audioRecord = null
            recordThread = null
        }
    }

    fun getRecordingPath(): String? = currentFilePath
}
