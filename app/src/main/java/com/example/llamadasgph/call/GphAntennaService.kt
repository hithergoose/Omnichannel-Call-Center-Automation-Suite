package com.example.llamadasgph.call

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.llamadasgph.MainActivity

class GphAntennaService : Service() {

    private var serverManager: HttpServerManager? = null
    private var wakeLock: PowerManager.WakeLock? = null

    companion object {
        const val TAG = "GphAntennaService"
        const val CHANNEL_ID = "GphAntennaChannel"
        const val NOTIFICATION_ID = 1001
        const val ACTION_STOP_SERVICE = "STOP_GPH_ANTENNA_SERVICE"

        // Para verificar si el servicio está activo desde fuera
        @Volatile
        var isRunning: Boolean = false
            private set

        fun start(context: Context) {
            val intent = Intent(context, GphAntennaService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, GphAntennaService::class.java)
            context.stopService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "Service onCreate")
        createNotificationChannel()
        acquireWakeLock()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "Service onStartCommand")

        if (intent?.action == ACTION_STOP_SERVICE) {
            Log.d(TAG, "Stop action received")
            isRunning = false
            releaseWakeLock()
            stopSelf()
            return START_NOT_STICKY
        }

        // Crear e iniciar como foreground INMEDIATAMENTE
        val notification = createNotification(isActive = false)
        startForeground(NOTIFICATION_ID, notification)

        // Ahora iniciar el servidor
        try {
            if (serverManager == null) {
                serverManager = HttpServerManager(this)
            }
            serverManager?.start()
            isRunning = true
            Log.d(TAG, "HTTP Server started successfully")

            // Actualizar notificación a "activo"
            updateNotification(true)

        } catch (e: Exception) {
            Log.e(TAG, "Error starting server: ${e.message}")
            e.printStackTrace()
            isRunning = false
        }

        // START_STICKY = si el sistema mata el servicio, lo reinicia
        return START_STICKY
    }

    override fun onDestroy() {
        Log.d(TAG, "Service onDestroy")
        isRunning = false
        releaseWakeLock()
        try {
            serverManager?.stop()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun acquireWakeLock() {
        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "GphAntennaService::WakeLock"
            )
            wakeLock?.acquire(10 * 60 * 1000L) // 10 minutos max, se renovará
            Log.d(TAG, "WakeLock acquired")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to acquire WakeLock: ${e.message}")
        }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
                Log.d(TAG, "WakeLock released")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to release WakeLock: ${e.message}")
        }
    }

    private fun updateNotification(isActive: Boolean) {
        val notification = createNotification(isActive)
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun createNotification(isActive: Boolean): Notification {
        // Intent para abrir la app cuando se toca la notificación
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
        }
        val openAppPendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        // Intent para detener el servicio
        val stopIntent = Intent(this, GphAntennaService::class.java).apply {
            action = ACTION_STOP_SERVICE
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val statusText = if (isActive) {
            "Activo - Puerto 8080 - IP: ${getLocalIpAddress()}"
        } else {
            "Iniciando servidor..."
        }

        val statusTextShort = if (isActive) "GPH Antena Activa" else "GPH Antena"

        // Construcción de la notificación
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(statusTextShort)
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(openAppPendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setColor(0xFF4CAF50.toInt())

        // Solo añadir acciones si está activo
        if (isActive) {
            builder.addAction(
                android.R.drawable.ic_menu_view,
                "Abrir",
                openAppPendingIntent
            )
            builder.addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Detener",
                stopPendingIntent
            )
        }

        return builder.build()
    }

    private fun getLocalIpAddress(): String {
        return try {
            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as android.net.wifi.WifiManager
            val ipInfo = wifiManager.connectionInfo
            val ip = ipInfo.ipAddress
            if (ip == 0) "Sin IP" else String.format(
                "%d.%d.%d.%d",
                ip and 0xff,
                ip shr 8 and 0xff,
                ip shr 16 and 0xff,
                ip shr 24 and 0xff
            )
        } catch (e: Exception) {
            "Error"
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Antena GPH",
                NotificationManager.IMPORTANCE_HIGH  // Alta prioridad = más visible
            ).apply {
                description = "Servicio de antena para recibir llamadas desde Windows"
                setShowBadge(true)
                enableVibration(false)
                setSound(null, null)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }
}
