package com.example.llamadasgph.ui.call

import android.Manifest
import android.content.Context
import android.os.Build
import android.telecom.Call
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.FiberManualRecord
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.llamadasgph.call.AudioRecorder
import com.example.llamadasgph.call.CallManager
import kotlinx.coroutines.delay
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun CallScreen(
    onCallEnded: () -> Unit
) {
    val context = LocalContext.current
    val call by CallManager.currentCall.collectAsState()
    
    val recordPermissionState = rememberPermissionState(permission = Manifest.permission.RECORD_AUDIO)

    var isMuted by remember { mutableStateOf(false) }
    var isHolding by remember { mutableStateOf(false) }
    var isRecording by remember { mutableStateOf(false) }
    var durationSeconds by remember { mutableStateOf(0) }
    
    val audioRecorder = remember { AudioRecorder(context) }

    LaunchedEffect(call) {
        if (call == null || call?.state == Call.STATE_DISCONNECTED) {
            if (isRecording) {
                audioRecorder.stopRecording()
            }
            onCallEnded()
        }
    }

    LaunchedEffect(call?.state) {
        if (call?.state == Call.STATE_ACTIVE) {
            while (true) {
                delay(1000)
                durationSeconds++
            }
        }
    }

    val phoneNumber = call?.details?.handle?.schemeSpecificPart ?: "Desconocido"
    val callStateLabel = when (call?.state) {
        Call.STATE_RINGING -> "Llamada entrante..."
        Call.STATE_DIALING -> "Marcando..."
        Call.STATE_ACTIVE -> "Llamada en curso"
        Call.STATE_HOLDING -> "En espera"
        Call.STATE_DISCONNECTED -> "Llamada finalizada"
        else -> "Conectando..."
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.weight(1f))

        Text(
            text = phoneNumber,
            style = MaterialTheme.typography.headlineLarge,
            textAlign = TextAlign.Center
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Text(
            text = callStateLabel,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        if (call?.state == Call.STATE_ACTIVE || call?.state == Call.STATE_HOLDING) {
            val minutes = durationSeconds / 60
            val seconds = durationSeconds % 60
            Text(
                text = String.format("%02d:%02d", minutes, seconds),
                style = MaterialTheme.typography.headlineMedium
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        if (isRecording) {
            Text(
                text = "Grabando llamada...",
                color = Color.Red,
                style = MaterialTheme.typography.bodyMedium
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            // Mute Button
            CallActionButton(
                icon = if (isMuted) Icons.Filled.MicOff else Icons.Filled.Mic,
                label = "Silenciar",
                isActive = isMuted,
                onClick = {
                    isMuted = !isMuted
                    // CallManager needs a mute function, for now we will assume the OS handles via AudioManager or Telecom
                }
            )

            // Hold Button
            CallActionButton(
                icon = if (isHolding) Icons.Filled.PlayArrow else Icons.Filled.Pause,
                label = "Espera",
                isActive = isHolding,
                onClick = {
                    isHolding = !isHolding
                    CallManager.setHold(isHolding)
                }
            )

            // Record Button
            CallActionButton(
                icon = if (isRecording) Icons.Filled.Stop else Icons.Filled.FiberManualRecord,
                label = "Grabar",
                isActive = isRecording,
                iconTint = if (isRecording) Color.Red else LocalContentColor.current,
                onClick = {
                    if (!recordPermissionState.status.isGranted) {
                        recordPermissionState.launchPermissionRequest()
                    } else {
                        if (isRecording) {
                            audioRecorder.stopRecording()
                            isRecording = false
                            Toast.makeText(context, "Grabación guardada", Toast.LENGTH_SHORT).show()
                        } else {
                            if (audioRecorder.startRecording(phoneNumber)) {
                                isRecording = true
                                val path = audioRecorder.getRecordingPath() ?: "desconocida"
                                Toast.makeText(context, "Grabando en: $path", Toast.LENGTH_LONG).show()
                                android.util.Log.d("CallScreen", "Grabando en: $path")
                            } else {
                                Toast.makeText(context, "Error al grabar", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                }
            )
        }

        Spacer(modifier = Modifier.height(48.dp))

        // End Call Button
        FloatingActionButton(
            onClick = {
                if (isRecording) {
                    audioRecorder.stopRecording()
                }
                if (call?.state == Call.STATE_RINGING) {
                    CallManager.rejectCall()
                } else {
                    CallManager.disconnectCall()
                }
            },
            containerColor = Color.Red,
            contentColor = Color.White,
            shape = CircleShape,
            modifier = Modifier.size(72.dp)
        ) {
            Icon(Icons.Filled.CallEnd, contentDescription = "Colgar", modifier = Modifier.size(36.dp))
        }
        
        if (call?.state == Call.STATE_RINGING) {
             Spacer(modifier = Modifier.height(16.dp))
             FloatingActionButton(
                onClick = {
                    CallManager.answerCall()
                },
                containerColor = Color.Green,
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(72.dp)
            ) {
                Icon(Icons.Filled.Call, contentDescription = "Contestar", modifier = Modifier.size(36.dp))
            }
        }
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
fun CallActionButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    isActive: Boolean,
    iconTint: Color = LocalContentColor.current,
    onClick: () -> Unit
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Button(
            onClick = onClick,
            shape = CircleShape,
            modifier = Modifier.size(64.dp),
            contentPadding = PaddingValues(0.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (isActive) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                contentColor = if (isActive) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
            )
        ) {
            Icon(icon, contentDescription = label, tint = iconTint)
        }
        Spacer(modifier = Modifier.height(8.dp))
        Text(text = label, style = MaterialTheme.typography.bodySmall)
    }
}
