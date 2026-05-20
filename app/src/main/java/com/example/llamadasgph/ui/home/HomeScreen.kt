package com.example.llamadasgph.ui.home

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.CallLog
import android.provider.ContactsContract
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.foundation.Image
import androidx.compose.ui.text.font.FontWeight
import com.example.llamadasgph.R
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.llamadasgph.ui.server.ServerScreen
import com.example.llamadasgph.ui.theme.Charcoal
import com.example.llamadasgph.ui.theme.GoldPrimary
import com.example.llamadasgph.ui.theme.SurfaceDark
import com.example.llamadasgph.call.CallManager
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberMultiplePermissionsState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun HomeScreen() {
    var selectedTab by remember { mutableIntStateOf(0) }
    
    val permissions = rememberMultiplePermissionsState(
        listOf(
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.RECORD_AUDIO
        )
    )

    LaunchedEffect(Unit) {
        if (!permissions.allPermissionsGranted) {
            permissions.launchMultiplePermissionRequest()
        }
    }

    val currentCall by CallManager.currentCall.collectAsState()
    val outgoingNumber by CallManager.outgoingNumber.collectAsState()

    Scaffold(
        containerColor = Charcoal,
        bottomBar = {
            if (currentCall == null && outgoingNumber == null) {
                NavigationBar(
                    containerColor = SurfaceDark,
                    contentColor = GoldPrimary,
                    tonalElevation = 8.dp
                ) {
                    val tabs = listOf(
                        Triple(0, Icons.Default.Dialpad, "Teclado"),
                        Triple(1, Icons.Default.History, "Recientes"),
                        Triple(2, Icons.Default.Contacts, "Contactos"),
                        Triple(3, Icons.Default.SettingsEthernet, "Antena")
                    )
                    tabs.forEach { (index, icon, label) ->
                        NavigationBarItem(
                            selected = selectedTab == index,
                            onClick = { selectedTab = index },
                            icon = { Icon(icon, contentDescription = label) },
                            label = { Text(label) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = GoldPrimary,
                                selectedTextColor = GoldPrimary,
                                unselectedIconColor = Color.Gray,
                                unselectedTextColor = Color.Gray,
                                indicatorColor = GoldPrimary.copy(alpha = 0.1f)
                            )
                        )
                    }
                }
            }
        }
    ) { paddingValues ->
        Box(modifier = Modifier.padding(paddingValues).fillMaxSize()) {
            AnimatedContent(
                targetState = selectedTab,
                transitionSpec = { fadeIn() togetherWith fadeOut() }, 
                label = "tabTransition"
            ) { targetTab ->
                when (targetTab) {
                    0 -> DialpadScreen()
                    1 -> RecentsScreen()
                    2 -> ContactsScreen()
                    3 -> ServerScreen()
                }
            }

            // --- IN-CALL UI OVERLAY ---
            currentCall?.let { call ->
                // Usamos un estado local que se actualiza cuando la llamada cambia de estado
                var callState by remember(call) { mutableIntStateOf(call.state) }
                
                DisposableEffect(call) {
                    val callback = object : android.telecom.Call.Callback() {
                        override fun onStateChanged(call: android.telecom.Call, state: Int) {
                            callState = state
                        }
                    }
                    call.registerCallback(callback)
                    onDispose {
                        call.unregisterCallback(callback)
                    }
                }

                InCallUI(call, callState)
            }
            
            // Si el InCallService aún no tiene la llamada pero Windows ya la inició
            if (currentCall == null && outgoingNumber != null) {
                FakeInCallUI(outgoingNumber!!)
            }
        }
    }
}

@Composable
fun InCallUI(call: android.telecom.Call, state: Int) {
    val outgoingNumber by CallManager.outgoingNumber.collectAsState()
    val number = call.details.handle?.schemeSpecificPart ?: outgoingNumber ?: "Desconocido"
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Charcoal.copy(alpha = 0.95f))
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(
                shape = CircleShape,
                color = GoldPrimary.copy(alpha = 0.1f),
                modifier = Modifier.size(120.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(64.dp), tint = GoldPrimary)
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(text = number, fontSize = 28.sp, fontWeight = FontWeight.Bold, color = Color.White)
            
            val statusText = when(state) {
                android.telecom.Call.STATE_ACTIVE -> "Llamada Activa"
                android.telecom.Call.STATE_RINGING -> "Llamada Entrante"
                android.telecom.Call.STATE_DIALING -> "Marcando..."
                android.telecom.Call.STATE_PULLING_CALL -> "Marcando..."
                android.telecom.Call.STATE_CONNECTING -> "Conectando..."
                android.telecom.Call.STATE_HOLDING -> "Llamada en Pausa"
                else -> "Finalizando..."
            }
            
            Text(text = statusText, fontSize = 16.sp, color = GoldPrimary)

            if (state == android.telecom.Call.STATE_ACTIVE) {
                var duration by remember { mutableLongStateOf(0L) }
                val startTime = call.details.connectTimeMillis
                
                LaunchedEffect(Unit) {
                    while(true) {
                        val current = System.currentTimeMillis()
                        if (startTime > 0) {
                            duration = (current - startTime) / 1000
                        }
                        kotlinx.coroutines.delay(1000)
                    }
                }
                
                val minutes = duration / 60
                val seconds = duration % 60
                Text(
                    text = String.format("%02d:%02d", minutes, seconds),
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Medium,
                    color = Color.White,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }

            Spacer(modifier = Modifier.height(48.dp))

            // -- CONTROLES DINÁMICOS --
            if (state == android.telecom.Call.STATE_ACTIVE || state == android.telecom.Call.STATE_HOLDING) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    // Botón Silenciar
                    val am = LocalContext.current.getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
                    var isMuted by remember { mutableStateOf(am.isMicrophoneMute) }
                    
                    CallControlButton(
                        icon = if (isMuted) Icons.Default.MicOff else Icons.Default.Mic,
                        label = "Silenciar",
                        active = isMuted
                    ) {
                        isMuted = !isMuted
                        am.isMicrophoneMute = isMuted
                    }

                    // Botón Pausar (Hold)
                    val isOnHold = state == android.telecom.Call.STATE_HOLDING
                    CallControlButton(
                        icon = if (isOnHold) Icons.Default.PlayArrow else Icons.Default.Pause,
                        label = if (isOnHold) "Reanudar" else "Pausar",
                        active = isOnHold
                    ) {
                        CallManager.setHold(!isOnHold)
                    }
                }
            }
            
            Spacer(modifier = Modifier.height(48.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (state == android.telecom.Call.STATE_RINGING) {
                    // Botón Contestar
                    FloatingActionButton(
                        onClick = { CallManager.answerCall() },
                        containerColor = Color(0xFF4CAF50),
                        contentColor = Color.White,
                        shape = CircleShape
                    ) {
                        Icon(Icons.Default.Call, contentDescription = "Contestar")
                    }
                }
                
                // Botón Colgar
                FloatingActionButton(
                    onClick = { CallManager.disconnectCall() },
                    containerColor = Color.Red,
                    contentColor = Color.White,
                    shape = CircleShape
                ) {
                    Icon(Icons.Default.CallEnd, contentDescription = "Colgar")
                }
            }
        }
    }
}

@Composable
fun FakeInCallUI(number: String) {
    Box(
        modifier = Modifier.fillMaxSize().background(Charcoal.copy(alpha = 0.95f)).padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(shape = CircleShape, color = GoldPrimary.copy(alpha = 0.1f), modifier = Modifier.size(120.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(64.dp), tint = GoldPrimary)
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text(text = number, fontSize = 28.sp, fontWeight = FontWeight.Bold, color = Color.White)
            Text(text = "Marcando...", fontSize = 16.sp, color = GoldPrimary)
            Spacer(modifier = Modifier.height(64.dp))
            FloatingActionButton(
                onClick = { /* El colgar se maneja por telecom si es posible, o esperar a InCallService */ },
                containerColor = Color.Red, contentColor = Color.White, shape = CircleShape
            ) {
                Icon(Icons.Default.CallEnd, contentDescription = "Cancelar")
            }
        }
    }
}

@Composable
fun DialpadScreen() {
    var number by remember { mutableStateOf("") }
    val context = LocalContext.current

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(32.dp))
        
        Image(
            painter = painterResource(id = R.drawable.logo_gph),
            contentDescription = "Logo GPH",
            modifier = Modifier.size(100.dp).clip(RoundedCornerShape(12.dp))
        )

        Spacer(modifier = Modifier.weight(1f))
        
        Text(
            text = number,
            fontSize = 48.sp,
            fontWeight = FontWeight.Light,
            textAlign = TextAlign.Center,
            color = GoldPrimary,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 32.dp),
            maxLines = 1
        )
        
        Box(modifier = Modifier.height(48.dp), contentAlignment = Alignment.Center) {
            if (number.isNotEmpty()) {
                TextButton(onClick = {
                    val intent = Intent(Intent.ACTION_INSERT).apply {
                        type = ContactsContract.RawContacts.CONTENT_TYPE
                        putExtra(ContactsContract.Intents.Insert.PHONE, number)
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    try { context.startActivity(intent) } catch (_: Exception) {}
                }) {
                    Text("+ Crear Contacto", color = GoldPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                }
            }
        }

        val keys = listOf(
            listOf("1", "2", "3"),
            listOf("4", "5", "6"),
            listOf("7", "8", "9"),
            listOf("*", "0", "#")
        )

        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            keys.forEach { row ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    row.forEach { key ->
                        DialButton(key) { number += key }
                    }
                }
            }
        }
        
        Spacer(modifier = Modifier.height(48.dp))
        
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(
                onClick = { if (number.isNotEmpty()) number = number.dropLast(1) },
                modifier = Modifier.size(64.dp)
            ) {
                Icon(Icons.Default.Backspace, contentDescription = "Borrar", tint = Color.Gray)
            }

            FloatingActionButton(
                onClick = {
                    if (number.isNotEmpty()) {
                        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        }
                        try { context.startActivity(intent) } catch (e: Exception) {}
                    }
                },
                containerColor = GoldPrimary,
                contentColor = Charcoal,
                shape = CircleShape,
                modifier = Modifier.size(80.dp)
            ) {
                Icon(Icons.Default.Phone, contentDescription = "Llamar", modifier = Modifier.size(36.dp))
            }

            Spacer(modifier = Modifier.size(64.dp))
        }
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
fun DialButton(text: String, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = SurfaceDark,
        modifier = Modifier.size(80.dp)
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(text, fontSize = 28.sp, fontWeight = FontWeight.Normal, color = Color.White)
        }
    }
}

@SuppressLint("Range")
suspend fun fetchCallLogs(context: Context): List<CallLogEntry> = withContext(Dispatchers.IO) {
    val list = mutableListOf<CallLogEntry>()
    try {
        val cursor = context.contentResolver.query(
            CallLog.Calls.CONTENT_URI,
            null, null, null, CallLog.Calls.DATE + " DESC LIMIT 50"
        )
        cursor?.use {
            val nameIdx = it.getColumnIndex(CallLog.Calls.CACHED_NAME)
            val numberIdx = it.getColumnIndex(CallLog.Calls.NUMBER)
            val typeIdx = it.getColumnIndex(CallLog.Calls.TYPE)
            val dateIdx = it.getColumnIndex(CallLog.Calls.DATE)
            
            while (it.moveToNext()) {
                val name = it.getString(nameIdx)
                val number = it.getString(numberIdx)
                val type = it.getInt(typeIdx)
                val dateMs = it.getLong(dateIdx)
                val dateStr = SimpleDateFormat("HH:mm • dd MMM", Locale.getDefault()).format(Date(dateMs))
                list.add(CallLogEntry(name, number, type, dateStr, ""))
            }
        }
    } catch (_: Exception) {}
    list
}

@Composable
fun RecentsScreen() {
    val context = LocalContext.current
    var logs by remember { mutableStateOf<List<CallLogEntry>>(emptyList()) }
    
    LaunchedEffect(Unit) {
        logs = fetchCallLogs(context)
    }

    LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp)) {
        item { 
            Text(
                "Recientes", 
                style = MaterialTheme.typography.displaySmall, 
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(vertical = 32.dp),
                color = GoldPrimary
            ) 
        }
        items(logs) { log ->
            CallLogItem(log) {
                val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:${log.number}")).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK }
                try { context.startActivity(intent) } catch (_: Exception) {}
            }
        }
    }
}

@Composable
fun CallLogItem(log: CallLogEntry, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .clickable { onClick() }
            .padding(vertical = 16.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        val icon = when (log.type) {
            CallLog.Calls.MISSED_TYPE -> Icons.Default.CallMissed
            CallLog.Calls.OUTGOING_TYPE -> Icons.Default.CallMade
            else -> Icons.Default.CallReceived
        }
        val iconColor = if (log.type == CallLog.Calls.MISSED_TYPE) Color.Red else GoldPrimary
        
        Icon(icon, contentDescription = null, tint = iconColor, modifier = Modifier.size(24.dp))
        Spacer(modifier = Modifier.width(20.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(text = log.name ?: log.number, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Color.White)
            Text(text = "${log.number} • ${log.date}", fontSize = 14.sp, color = Color.Gray)
        }
    }
}

@SuppressLint("Range")
suspend fun fetchContacts(context: Context): List<ContactEntry> = withContext(Dispatchers.IO) {
    val list = mutableListOf<ContactEntry>()
    try {
        val cursor = context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            null, null, null, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC"
        )
        cursor?.use {
            val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numberIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (it.moveToNext()) {
                val name = it.getString(nameIdx)
                val number = it.getString(numberIdx)
                if (!name.isNullOrEmpty() && !number.isNullOrEmpty()) list.add(ContactEntry(name, number))
            }
        }
    } catch (_: Exception) {}
    list.distinctBy { it.name }.sortedBy { it.name }
}

@Composable
fun ContactsScreen() {
    val context = LocalContext.current
    var contacts by remember { mutableStateOf<List<ContactEntry>>(emptyList()) }
    
    LaunchedEffect(Unit) {
        contacts = fetchContacts(context)
    }

    Box(modifier = Modifier.fillMaxSize()) {
        LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp)) {
            item { 
                Text(
                    "Contactos", 
                    style = MaterialTheme.typography.displaySmall, 
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(vertical = 32.dp),
                    color = GoldPrimary
                ) 
            }
            items(contacts) { contact ->
                ContactItem(contact) {
                    val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:${contact.number}")).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK }
                    try { context.startActivity(intent) } catch (_: Exception) {}
                }
            }
            item {
                Spacer(modifier = Modifier.height(100.dp)) // Espacio para que el FAB no tape el último contacto
            }
        }
        
        FloatingActionButton(
            onClick = {
                val intent = Intent(Intent.ACTION_INSERT).apply {
                    type = ContactsContract.RawContacts.CONTENT_TYPE
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                try { context.startActivity(intent) } catch (_: Exception) {}
            },
            containerColor = GoldPrimary,
            contentColor = Charcoal,
            shape = CircleShape,
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = 24.dp, bottom = 24.dp).size(64.dp)
        ) {
            Icon(Icons.Default.Add, contentDescription = "Agregar Contacto", modifier = Modifier.size(28.dp))
        }
    }
}

@Composable
fun ContactItem(contact: ContactEntry, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .clickable { onClick() }
            .padding(vertical = 12.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(shape = CircleShape, color = GoldPrimary.copy(alpha = 0.1f), modifier = Modifier.size(48.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Text(contact.name.take(1).uppercase(), color = GoldPrimary, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(text = contact.name, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Color.White)
            Text(text = contact.number, fontSize = 14.sp, color = Color.Gray)
        }
    }
}

@Composable
fun CallControlButton(icon: ImageVector, label: String, active: Boolean, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Surface(
            onClick = onClick,
            shape = CircleShape,
            color = if (active) GoldPrimary else SurfaceDark.copy(alpha = 0.5f),
            modifier = Modifier.size(64.dp),
            border = BorderStroke(1.dp, GoldPrimary.copy(alpha = 0.3f))
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = label, tint = if (active) Charcoal else Color.White)
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Text(label, fontSize = 12.sp, color = Color.Gray)
    }
}

data class CallLogEntry(val name: String?, val number: String, val type: Int, val date: String, val duration: String)
data class ContactEntry(val name: String, val number: String)
