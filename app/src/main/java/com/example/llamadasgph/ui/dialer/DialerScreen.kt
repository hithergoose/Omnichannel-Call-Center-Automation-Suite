package com.example.llamadasgph.ui.dialer

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Backspace
import androidx.compose.material.icons.filled.Call
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

import android.net.Uri
import android.os.Bundle
import android.telecom.TelecomManager
import androidx.compose.ui.platform.LocalContext
import android.content.Context
import android.Manifest
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState

import androidx.compose.material.icons.filled.List

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun DialerScreen() {
    var phoneNumber by remember { mutableStateOf("") }
    val context = LocalContext.current
    
    val callPermissionState = rememberPermissionState(permission = Manifest.permission.CALL_PHONE)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.weight(1f))

        Text(
            text = if (phoneNumber.isEmpty()) "Ingresa un número" else phoneNumber,
            style = MaterialTheme.typography.headlineLarge,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
            maxLines = 1
        )
        
        if (phoneNumber.isNotEmpty() && !phoneNumber.startsWith("+")) {
            Text(
                text = "Llamará a: +52 $phoneNumber",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        DialPad(
            onKeyPress = { key ->
                if (phoneNumber.length < 15) phoneNumber += key
            },
            onDelete = {
                if (phoneNumber.isNotEmpty()) {
                    phoneNumber = phoneNumber.dropLast(1)
                }
            },
            onCall = {
                if (!callPermissionState.status.isGranted) {
                    callPermissionState.launchPermissionRequest()
                } else {
                    val finalNumber = if (phoneNumber.startsWith("+")) phoneNumber else "+52$phoneNumber"
                    val uri = Uri.fromParts("tel", finalNumber, null)
                    try {
                        val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as TelecomManager
                        telecomManager.placeCall(uri, null)
                    } catch (e: SecurityException) {
                        e.printStackTrace()
                    }
                }
            }
        )
    }
}

@Composable
fun DialPad(
    onKeyPress: (String) -> Unit,
    onDelete: () -> Unit,
    onCall: () -> Unit
) {
    val rows = listOf(
        listOf("1", "2", "3"),
        listOf("4", "5", "6"),
        listOf("7", "8", "9"),
        listOf("*", "0", "#")
    )

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        for (row in rows) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                for (key in row) {
                    DialButton(
                        text = key,
                        onClick = { 
                            if (key == "0") {
                                // Default action, long press is usually handled differently, but a simple press is 0
                                onKeyPress(key)
                            } else {
                                onKeyPress(key)
                            }
                        },
                        onLongClick = {
                            if (key == "0") onKeyPress("+")
                        }
                    )
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Spacer(modifier = Modifier.weight(1f))
            
            FloatingActionButton(
                onClick = onCall,
                containerColor = MaterialTheme.colorScheme.primaryContainer,
                shape = CircleShape,
                modifier = Modifier.size(72.dp)
            ) {
                Icon(Icons.Filled.Call, contentDescription = "Llamar", modifier = Modifier.size(36.dp))
            }
            
            Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                IconButton(onClick = onDelete, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.AutoMirrored.Filled.Backspace, contentDescription = "Borrar")
                }
            }
        }
        Spacer(modifier = Modifier.height(32.dp))
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun DialButton(text: String, onClick: () -> Unit, onLongClick: () -> Unit = {}) {
    Button(
        onClick = onClick,
        shape = CircleShape,
        modifier = Modifier
            .size(80.dp)
            .padding(4.dp),
        contentPadding = PaddingValues(0.dp),
        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.surfaceVariant, contentColor = MaterialTheme.colorScheme.onSurface)
    ) {
        Text(text, style = MaterialTheme.typography.headlineMedium)
    }
}
