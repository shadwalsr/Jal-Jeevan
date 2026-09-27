package com.jaljeev.ui.voice

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View

class WaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : View(context, attrs, defStyleAttr) {

    private val maxBars = 30
    private val amplitudes = FloatArray(maxBars)
    private var isListening = false

    private val activeColor = Color.parseColor("#E53935") // mic_active_red
    private val idleColor = Color.parseColor("#757575")   // text_secondary

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = idleColor
        strokeCap = Paint.Cap.ROUND
    }

    fun updateAmplitude(amplitude: Int) {
        // Shift left
        System.arraycopy(amplitudes, 1, amplitudes, 0, maxBars - 1)
        // Normalize 0..32767 -> 0.05..1.0f
        val norm = (amplitude.toFloat() / 32767f).coerceIn(0.05f, 1.0f)
        amplitudes[maxBars - 1] = norm
        isListening = true
        postInvalidateOnAnimation()
    }

    fun setListening(listening: Boolean) {
        isListening = listening
        paint.color = if (isListening) activeColor else idleColor
        postInvalidate()
    }

    fun reset() {
        for (i in amplitudes.indices) {
            amplitudes[i] = 0.05f
        }
        isListening = false
        paint.color = idleColor
        postInvalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        val centerY = h / 2f

        val totalBarWidth = w / maxBars
        val barWidth = (totalBarWidth * 0.6f).coerceAtLeast(2f)
        paint.strokeWidth = barWidth

        for (i in 0 until maxBars) {
            val x = i * totalBarWidth + totalBarWidth / 2f
            val barHeight = (amplitudes[i] * h * 0.85f).coerceAtLeast(4f)
            val top = centerY - barHeight / 2f
            val bottom = centerY + barHeight / 2f
            canvas.drawLine(x, top, x, bottom, paint)
        }
    }
}
