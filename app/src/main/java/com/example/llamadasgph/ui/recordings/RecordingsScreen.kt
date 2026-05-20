package com.example.llamadasgph.ui.recordings

import android.os.Environment
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Audiotrack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.io.File
import android.media.MediaPlayer
import android.widget.Toast
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordingsScreen() {
    val context = LocalContext.current
    var files by remember { mutableStateOf(emptyList<File>()) }
    var mediaPlayer by remember { mutableStateOf<MediaPlayer?>(null) }
    var playingFile by remember { mutableStateOf<File?>(null) }

    LaunchedEffect(Unit) {
        val dir = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "Gestiones GPH")
        if (dir.exists()) {
            files = dir.listFiles()?.filter { it.extension == "m4a" || it.extension == "mp3" }?.sortedByDescending { it.lastModified() } ?: emptyList()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            mediaPlayer?.release()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Grabaciones GPH") })
        }
    ) { paddingValues ->
        if (files.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize().padding(paddingValues), contentAlignment = Alignment.Center) {
                Text("No hay llamadas grabadas.", style = MaterialTheme.typography.bodyLarge)
            }
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
                items(files) { file ->
                    val isPlaying = playingFile == file
                    
                    ListItem(
                        headlineContent = { Text(file.name) },
                        supportingContent = { Text("${file.length() / 1024} KB") },
                        leadingContent = {
                            Icon(Icons.Filled.Audiotrack, contentDescription = "Audio")
                        },
                        trailingContent = {
                            Button(onClick = {
                                if (isPlaying) {
                                    mediaPlayer?.stop()
                                    mediaPlayer?.release()
                                    mediaPlayer = null
                                    playingFile = null
                                } else {
                                    mediaPlayer?.release()
                                    mediaPlayer = MediaPlayer().apply {
                                        setDataSource(file.absolutePath)
                                        prepare()
                                        start()
                                        setOnCompletionListener {
                                            playingFile = null
                                            release()
                                            mediaPlayer = null
                                        }
                                    }
                                    playingFile = file
                                    Toast.makeText(context, "Reproduciendo...", Toast.LENGTH_SHORT).show()
                                }
                            }) {
                                Text(if (isPlaying) "Stop" else "Play")
                            }
                        },
                        modifier = Modifier.clickable { }
                    )
                    Divider()
                }
            }
        }
    }
}
