package com.example.llamadasgph.call

import android.telecom.Call
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

object CallManager {
    private val _currentCall = MutableStateFlow<Call?>(null)
    val currentCall: StateFlow<Call?> = _currentCall.asStateFlow()

    // Para rastrear llamadas salientes iniciadas desde Windows via HTTP
    private val _outgoingNumber = MutableStateFlow<String?>(null)
    val outgoingNumber: StateFlow<String?> = _outgoingNumber.asStateFlow()

    fun updateCall(call: Call?) {
        _currentCall.value = call
        if (call != null) {
            _outgoingNumber.value = null
        }
    }

    fun setOutgoingNumber(number: String) {
        _outgoingNumber.value = number
    }

    fun clearOutgoingNumber() {
        _outgoingNumber.value = null
    }

    fun answerCall() {
        _currentCall.value?.answer(0)
    }

    fun rejectCall() {
        _currentCall.value?.reject(false, null)
    }

    fun disconnectCall() {
        _currentCall.value?.disconnect()
    }

    fun setHold(hold: Boolean) {
        val call = _currentCall.value ?: return
        if (hold) {
            if (call.state != Call.STATE_HOLDING) call.hold()
        } else {
            if (call.state == Call.STATE_HOLDING) call.unhold()
        }
    }
}
