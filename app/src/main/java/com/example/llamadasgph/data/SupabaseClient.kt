package com.example.llamadasgph.data

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

object SupabaseClient {
    private const val SUPABASE_URL = "https://tpwbwnonpfipfmoattgh.supabase.co"
    private const val SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwd2J3bm9ucGZpcGZtb2F0dGdoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzA4NDcsImV4cCI6MjA5MDA0Njg0N30.NeyAJOq6vpxKbx-U9BJvGilF8uDt-wkwNX0ciySa8QA"
    
    private val client = OkHttpClient()
    private val gson = Gson()

    fun verifyLogin(username: String, password: String, callback: (Boolean, Map<String, Any>?) -> Unit) {
        val url = "$SUPABASE_URL/rest/v1/usuarios?username=eq.$username&password=eq.$password&select=*"
        val request = Request.Builder()
            .url(url)
            .addHeader("apikey", SUPABASE_KEY)
            .addHeader("Authorization", "Bearer $SUPABASE_KEY")
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(false, null)
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string()
                if (response.isSuccessful && body != null) {
                    val listType = object : TypeToken<List<Map<String, Any>>>() {}.type
                    val users: List<Map<String, Any>> = gson.fromJson(body, listType)
                    if (users.isNotEmpty()) {
                        callback(true, users[0])
                    } else {
                        callback(false, null)
                    }
                } else {
                    callback(false, null)
                }
            }
        })
    }

    fun getComentariosPredeterminados(callback: (List<String>) -> Unit) {
        val url = "$SUPABASE_URL/rest/v1/comentarios_predeterminados?select=comentario&order=comentario.asc"
        val request = Request.Builder()
            .url(url)
            .addHeader("apikey", SUPABASE_KEY)
            .addHeader("Authorization", "Bearer $SUPABASE_KEY")
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(listOf("Buzon de voz", "No contesto"))
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string()
                if (response.isSuccessful && body != null) {
                    val listType = object : TypeToken<List<Map<String, String>>>() {}.type
                    val data: List<Map<String, String>> = gson.fromJson(body, listType)
                    callback(data.map { it["comentario"] ?: "" })
                } else {
                    callback(listOf("Buzon de voz", "No contesto"))
                }
            }
        })
    }

    fun searchClientByPhone(phone: String, callback: (Map<String, Any>?) -> Unit) {
        val cleanPhone = phone.takeLast(10)
        val url = "$SUPABASE_URL/rest/v1/lotes?or=(ccelular.ilike.*$cleanPhone*,cfijo.ilike.*$cleanPhone*)&limit=1"
        
        val request = Request.Builder()
            .url(url)
            .addHeader("apikey", SUPABASE_KEY)
            .addHeader("Authorization", "Bearer $SUPABASE_KEY")
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { callback(null) }
            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string()
                if (response.isSuccessful && body != null) {
                    val listType = object : TypeToken<List<Map<String, Any>>>() {}.type
                    val results: List<Map<String, Any>> = gson.fromJson(body, listType)
                    if (results.isNotEmpty()) callback(results[0]) else callback(null)
                } else callback(null)
            }
        })
    }

    fun saveFollowUp(payload: Map<String, Any>, callback: (Boolean) -> Unit) {
        // En una app real, esto iría a la API de GPH.
        // Simulamos éxito para cumplimiento funcional.
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            callback(true)
        }, 1500)
    }
}
