package com.example.llamadasgph.call

import android.telecom.Call
import android.telecom.InCallService

class CallService : InCallService() {

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        CallManager.updateCall(call)
        
        // Ensure the app comes to foreground to meet InCallService requirements and enable mic
        val intent = android.content.Intent(this, com.example.llamadasgph.MainActivity::class.java).apply {
            flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
        }
        startActivity(intent)
        
        call.registerCallback(callCallback)
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        CallManager.updateCall(null)
        call.unregisterCallback(callCallback)
    }

    private val callCallback = object : Call.Callback() {
        override fun onStateChanged(call: Call, state: Int) {
            super.onStateChanged(call, state)
            // Trigger recomposition by re-emitting the call or tracking state locally
            CallManager.updateCall(call)
        }
    }

    override fun onCallAudioStateChanged(audioState: android.telecom.CallAudioState?) {
        super.onCallAudioStateChanged(audioState)
        audioState?.let {
            // Si Bluetooth está soportado y no está seleccionado, forzarlo
            if ((it.supportedRouteMask and android.telecom.CallAudioState.ROUTE_BLUETOOTH) != 0 &&
                 it.route != android.telecom.CallAudioState.ROUTE_BLUETOOTH) {
                setAudioRoute(android.telecom.CallAudioState.ROUTE_BLUETOOTH)
                android.util.Log.d("CallService", "Forzando ruta de audio por BLUETOOTH")
            }
        }
    }
}
