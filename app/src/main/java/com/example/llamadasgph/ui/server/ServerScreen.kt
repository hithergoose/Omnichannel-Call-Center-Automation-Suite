package com.example.llamadasgph.ui.server

import android.Manifest
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.CellTower
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.llamadasgph.OverlayPermissionActivity
import com.example.llamadasgph.call.GphAntennaService
import com.example.llamadasgph.ui.theme.Charcoal
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberMultiplePermissionsState

fun getLocalIpAddress(context: Context): String {
    return try {
        val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val ipInfo = wifiManager.connectionInfo
        val ip = ipInfo.ipAddress
        if (ip == 0) "No WiFi / Desconectado" else String.format(
            "%d.%d.%d.%d",
            ip and 0xff,
            ip shr 8 and 0xff,
            ip shr 16 and 0xff,
            ip shr 24 and 0xff
        )
    } catch (e: Exception) {
        "Error obteniendo IP"
    }
}

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun ServerScreen() {
    val context = LocalContext.current

    // Usar el estado real del servicio en lugar de estado local
    var isRunning by remember { mutableStateOf(GphAntennaService.isRunning) }
    var serverStatus by remember { mutableStateOf(
        if (GphAntennaService.isRunning) "ACTIVO: TRANSMITIENDO" else "Sistema en Espera"
    ) }
    var ipAddress by remember { mutableStateOf(getLocalIpAddress(context)) }
    var isDefaultDialer by remember { mutableStateOf(false) }
    var isBluetoothConnected by remember { mutableStateOf(false) }

    // Función para verificar si hay un dispositivo Bluetooth con canal de AUDIO/VOZ conectado
    fun checkBluetooth(ctx: android.content.Context): Boolean {
        val am = ctx.getSystemService(android.content.Context.AUDIO_SERVICE) as android.media.AudioManager
        
        // Forma moderna (API 31+)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            val devices = am.getDevices(android.media.AudioManager.GET_DEVICES_OUTPUTS)
            val hasBt = devices.any { 
                it.type == android.media.AudioDeviceInfo.TYPE_BLUETOOTH_SCO || 
                it.type == android.media.AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                it.type == android.media.AudioDeviceInfo.TYPE_HEARING_AID
            }
            if (hasBt) return true
        }
        
        // Forma compatible y mas fiable para llamadas
        return am.isBluetoothScoOn || am.isBluetoothA2dpOn
    }

    // Verificar si es dialer por defecto
    LaunchedEffect(Unit) {
        isDefaultDialer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = context.getSystemService(Context.ROLE_SERVICE) as RoleManager
            roleManager.isRoleHeld(RoleManager.ROLE_DIALER)
        } else {
            val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as android.telecom.TelecomManager
            telecomManager.defaultDialerPackage == context.packageName
        }
    }

    // Refrescar estado y polleo continuo de Bluetooth
    LaunchedEffect(Unit) {
        while(true) {
            val bt = checkBluetooth(context)
            if (bt != isBluetoothConnected) {
                isBluetoothConnected = bt
            }
            ipAddress = getLocalIpAddress(context)
            serverStatus = if (GphAntennaService.isRunning) {
                if (isBluetoothConnected) "LISTO PARA LLAMADAS" else "ACTIVO: TRANSMITIENDO"
            } else {
                "Sistema en Espera"
            }
            kotlinx.coroutines.delay(2000) // Actualizar cada 2 segundos
        }
    }
    
    var showBluetoothWarning by remember { mutableStateOf(false) }

    if (showBluetoothWarning) {
        AlertDialog(
            onDismissRequest = { showBluetoothWarning = false },
            title = { Text("Bluetooth Requerido") },
            text = { Text("Para que el audio de las llamadas llegue a la PC, el equipo debe estar conectado por Bluetooth.\n\n¿Deseas iniciar la antena de todos modos?") },
            confirmButton = {
                Button(onClick = {
                    showBluetoothWarning = false
                    GphAntennaService.start(context)
                    isRunning = true
                    serverStatus = "INICIANDO..."
                }) { Text("Continuar") }
            },
            dismissButton = {
                TextButton(onClick = { 
                    showBluetoothWarning = false 
                    val intent = Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
                    context.startActivity(intent)
                }) { Text("Ir a Configuración") }
            }
        )
    }

    val permissionsState = rememberMultiplePermissionsState(permissions = listOf(
        Manifest.permission.CALL_PHONE,
        Manifest.permission.ANSWER_PHONE_CALLS,
        Manifest.permission.RECORD_AUDIO
    ))

    val dialerRoleLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        // Verificar si ahora es dialer por defecto
        isDefaultDialer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = context.getSystemService(Context.ROLE_SERVICE) as RoleManager
            roleManager.isRoleHeld(RoleManager.ROLE_DIALER)
        } else {
            val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as android.telecom.TelecomManager
            telecomManager.defaultDialerPackage == context.packageName
        }
    }

    LaunchedEffect(Unit) {
        if (!permissionsState.allPermissionsGranted) {
            permissionsState.launchMultiplePermissionRequest()
        }
    }

    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "pulseScale"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(32.dp))

        Icon(
            imageVector = Icons.Default.CellTower,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .size(64.dp)
                .shadow(20.dp, CircleShape, spotColor = MaterialTheme.colorScheme.primary)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "GPH ANTENA",
            style = MaterialTheme.typography.headlineLarge.copy(fontSize = 32.sp),
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 4.sp,
            color = MaterialTheme.colorScheme.primary
        )
        Text(
            text = "PUERTA DE LLAMADA REMOTA",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Alerta si no es dialer por defecto
        if (!isDefaultDialer) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(2.dp, MaterialTheme.colorScheme.error, RoundedCornerShape(16.dp)),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                ),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "⚠ DIALER NO CONFIGURADO",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.error
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "Para que las llamadas funcionen correctamente, esta app debe ser el marcador predeterminado.",
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = {
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                                val roleManager = context.getSystemService(Context.ROLE_SERVICE) as RoleManager
                                val intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER)
                                dialerRoleLauncher.launch(intent)
                            } else {
                                val intent = Intent(android.telecom.TelecomManager.ACTION_CHANGE_DEFAULT_DIALER)
                                intent.putExtra(android.telecom.TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, context.packageName)
                                context.startActivity(intent)
                            }
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Text("Configurar como Marcador Predeterminado")
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Card(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, Color.White.copy(alpha = 0.1f), RoundedCornerShape(24.dp)),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
        ) {
            Column(
                modifier = Modifier
                    .padding(24.dp)
                    .fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                StatusIndicator(isRunning, if (isRunning) pulseScale else 1f)

                Spacer(modifier = Modifier.height(24.dp))

                InfoTile(
                    icon = Icons.Default.Wifi,
                    label = "DIRECCIÓN IP",
                    value = ipAddress
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp), color = Color.White.copy(alpha = 0.05f))

                InfoTile(
                    icon = Icons.Default.Info,
                    label = "ESTADO SERVIDOR",
                    value = serverStatus,
                    valueColor = if (isRunning) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp), color = Color.White.copy(alpha = 0.05f))

                InfoTile(
                    icon = Icons.Default.Bluetooth,
                    label = "EQUIPO BLUETOOTH",
                    value = if (isBluetoothConnected) "CONECTADO A PC" else "DESCONECTADO",
                    valueColor = if (isBluetoothConnected) Color(0xFF4CAF50) else Color.Gray
                )
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        // Texto de ayuda
        if (!isRunning) {
            Text(
                text = "Presiona el botón para activar la antena",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
            Spacer(modifier = Modifier.height(16.dp))
        } else {
            val footerText = if (isBluetoothConnected) 
                "Listo para llamadas: servidor conectado y equipo celular conectado por bluetooth" 
                else "Antena activa. Conecta Bluetooth para audio en la PC."
            
            Text(
                text = footerText,
                style = MaterialTheme.typography.bodyMedium,
                color = if (isBluetoothConnected) Color(0xFF4CAF50) else MaterialTheme.colorScheme.primary.copy(alpha = 0.8f),
                modifier = Modifier.padding(horizontal = 32.dp),
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        LargePowerButton(
            isRunning = isRunning,
            onClick = {
                if (!isRunning) {
                    // Verificar permiso de overlay
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        if (!Settings.canDrawOverlays(context)) {
                            val intent = android.content.Intent(context, OverlayPermissionActivity::class.java)
                            context.startActivity(intent)
                            return@LargePowerButton
                        }
                    }
                    // Validar Bluetooth antes de iniciar
                    if (!isBluetoothConnected) {
                        showBluetoothWarning = true
                        return@LargePowerButton
                    }

                    // Iniciar servicio
                    GphAntennaService.start(context)
                    isRunning = true
                    serverStatus = "INICIANDO..."
                    ipAddress = getLocalIpAddress(context)
                } else {
                    GphAntennaService.stop(context)
                    isRunning = false
                    serverStatus = "EN ESPERA"
                }
            }
        )

        Spacer(modifier = Modifier.height(48.dp))
    }
}

@Composable
fun StatusIndicator(active: Boolean, scale: Float) {
    Box(contentAlignment = Alignment.Center) {
        if (active) {
            Box(
                modifier = Modifier
                    .size(12.dp * scale)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.3f), CircleShape)
            )
        }
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(if (active) MaterialTheme.colorScheme.primary else Color.Gray, CircleShape)
        )
    }
}

@Composable
fun InfoTile(icon: ImageVector, label: String, value: String, valueColor: Color = MaterialTheme.colorScheme.onSurface) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.6f))
        Spacer(modifier = Modifier.width(12.dp))
        Column {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = valueColor)
        }
    }
}

private fun Modifier.size(size: androidx.compose.ui.unit.Dp) = this.then(Modifier.width(size).height(size))

@Composable
fun LargePowerButton(isRunning: Boolean, onClick: () -> Unit) {
    val color = if (isRunning) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    val shadowColor = color.copy(alpha = 0.4f)

    Surface(
        onClick = onClick,
        modifier = Modifier
            .size(100.dp)
            .shadow(24.dp, CircleShape, spotColor = shadowColor),
        shape = CircleShape,
        color = Charcoal,
        border = BorderStroke(2.dp, color)
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = Icons.Default.PowerSettingsNew,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(48.dp)
            )
        }
    }
}
