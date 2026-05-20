package com.example.llamadasgph.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
fun ProfileScreen() {
    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Mi Perfil") })
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = Icons.Filled.Person,
                contentDescription = "Perfil",
                modifier = Modifier.size(100.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(text = "Información del Usuario", style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(16.dp))
            
            Spacer(modifier = Modifier.height(24.dp))
            
            val context = LocalContext.current
            val recorder = remember { com.example.llamadasgph.call.AudioRecorder(context) }
            var isTesting by remember { mutableStateOf(false) }
            val recordPermissionState = rememberPermissionState(permission = android.Manifest.permission.RECORD_AUDIO)

            Button(onClick = {
                if (!recordPermissionState.status.isGranted) {
                    recordPermissionState.launchPermissionRequest()
                } else {
                    if (isTesting) {
                        recorder.stopRecording()
                        isTesting = false
                        android.widget.Toast.makeText(context, "Grabación local guardada", android.widget.Toast.LENGTH_SHORT).show()
                    } else {
                        if (recorder.startRecording("Prueba_Usuario")) {
                            isTesting = true
                            android.widget.Toast.makeText(context, "Grabando prueba...", android.widget.Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }) {
                Text(if (isTesting) "Detener Prueba Local" else "Testear Micrófono de Grabación")
            }
        }
    }
}
