package com.jaljeev.ui.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.speech.tts.TextToSpeech
import android.view.HapticFeedbackConstants
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.ImageButton
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import com.jaljeev.marine.R
import com.jaljeev.voice.AudioRecorder
import com.jaljeev.voice.IndianLanguage
import com.jaljeev.voice.SarvamApiClient
import com.jaljeev.voice.SarvamRepository
import com.jaljeev.voice.VoiceUiState
import com.jaljeev.voice.VoiceViewModel
import kotlinx.coroutines.launch
import java.util.Locale

interface VoiceInputListener {
    fun onTranscriptReady(transcript: String)
}

class VoiceInputBottomSheet : BottomSheetDialogFragment() {

    private var listener: VoiceInputListener? = null
    private var vesselClass: String? = null
    private var textToSpeech: TextToSpeech? = null
    private var isTtsReady = false

    private val languages = IndianLanguage.coastalPriority()

    private val viewModel: VoiceViewModel by viewModels {
        val repo = SarvamRepository(SarvamApiClient.create())
        val recorder = AudioRecorder(requireContext().applicationContext)
        VoiceViewModel.factory(repo, recorder)
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            view?.findViewById<TextView>(R.id.statusText)?.setText(R.string.voice_error_mic)
        }
    }

    override fun onAttach(context: Context) {
        super.onAttach(context)
        if (context is VoiceInputListener) {
            listener = context
        } else if (parentFragment is VoiceInputListener) {
            listener = parentFragment as VoiceInputListener
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        vesselClass = arguments?.getString(ARG_VESSEL_CLASS)

        textToSpeech = TextToSpeech(requireContext().applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                isTtsReady = true
                textToSpeech?.setSpeechRate(0.85f)
            }
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View? {
        return inflater.inflate(R.layout.bottom_sheet_voice_input, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val spinner = view.findViewById<Spinner>(R.id.languageSpinner)
        val waveformView = view.findViewById<WaveformView>(R.id.waveformView)
        val elapsedTimer = view.findViewById<TextView>(R.id.elapsedTimer)
        val pttButton = view.findViewById<ImageButton>(R.id.pttButton)
        val statusText = view.findViewById<TextView>(R.id.statusText)
        val transcriptPreview = view.findViewById<TextView>(R.id.transcriptPreview)
        val sendButton = view.findViewById<Button>(R.id.sendButton)
        val cancelButton = view.findViewById<Button>(R.id.cancelButton)

        // Setup spinner
        val adapter = ArrayAdapter(
            requireContext(),
            android.R.layout.simple_spinner_dropdown_item,
            languages.map { "${it.nativeScript} (${it.displayName})" }
        )
        spinner.adapter = adapter
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                viewModel.setLanguage(languages[position])
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }

        // PTT Touch Listener
        pttButton.setOnTouchListener { v, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    if (ContextCompat.checkSelfPermission(
                            requireContext(),
                            Manifest.permission.RECORD_AUDIO
                        ) != PackageManager.PERMISSION_GRANTED
                    ) {
                        permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        return@setOnTouchListener false
                    }
                    v.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    viewModel.startRecording()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    viewModel.stopRecording()
                    true
                }
                else -> false
            }
        }

        cancelButton.setOnClickListener {
            dismiss()
        }

        sendButton.setOnClickListener {
            val transcript = transcriptPreview.text.toString()
            if (transcript.isNotBlank()) {
                listener?.onTranscriptReady(transcript)
                dismiss()
            }
        }

        // Collect state
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.uiState.collect { state ->
                        when (state) {
                            is VoiceUiState.Idle -> {
                                pttButton.setImageResource(R.drawable.ic_mic_jaljeev)
                                pttButton.setBackgroundResource(R.drawable.mic_button_bg)
                                waveformView.visibility = View.GONE
                                waveformView.reset()
                                elapsedTimer.visibility = View.GONE
                                transcriptPreview.visibility = View.GONE
                                sendButton.visibility = View.GONE
                                statusText.setText(R.string.voice_idle_hint)
                            }
                            is VoiceUiState.Listening -> {
                                pttButton.setImageResource(R.drawable.ic_mic_active)
                                waveformView.visibility = View.VISIBLE
                                waveformView.setListening(true)
                                elapsedTimer.visibility = View.VISIBLE
                                transcriptPreview.visibility = View.GONE
                                sendButton.visibility = View.GONE
                                statusText.setText(R.string.voice_listening)
                            }
                            is VoiceUiState.Processing -> {
                                pttButton.setImageResource(R.drawable.ic_mic_jaljeev)
                                waveformView.setListening(false)
                                waveformView.visibility = View.GONE
                                elapsedTimer.visibility = View.GONE
                                statusText.setText(R.string.voice_processing)
                            }
                            is VoiceUiState.Success -> {
                                pttButton.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                                pttButton.setImageResource(R.drawable.ic_mic_jaljeev)
                                waveformView.visibility = View.GONE
                                elapsedTimer.visibility = View.GONE
                                statusText.text = state.detectedLanguage ?: ""
                                transcriptPreview.text = state.transcript
                                transcriptPreview.visibility = View.VISIBLE
                                sendButton.visibility = View.VISIBLE

                                // TTS readback
                                speakTranscript(state.transcript)
                            }
                            is VoiceUiState.Error -> {
                                pttButton.performHapticFeedback(HapticFeedbackConstants.REJECT)
                                pttButton.setImageResource(R.drawable.ic_mic_jaljeev)
                                waveformView.visibility = View.GONE
                                elapsedTimer.visibility = View.GONE
                                statusText.text = state.error.message
                                transcriptPreview.visibility = View.GONE
                                sendButton.visibility = View.GONE
                            }
                            is VoiceUiState.PartialResult -> {}
                        }
                    }
                }

                launch {
                    viewModel.amplitude.collect { amp ->
                        waveformView.updateAmplitude(amp)
                    }
                }

                launch {
                    viewModel.elapsedMs.collect { ms ->
                        val seconds = (ms / 1000) % 60
                        val minutes = (ms / 1000) / 60
                        elapsedTimer.text = String.format(Locale.US, "%02d:%02d", minutes, seconds)
                    }
                }
            }
        }
    }

    private fun speakTranscript(text: String) {
        if (!isTtsReady || text.isBlank()) return
        val lang = viewModel.selectedLanguage.value
        val locale = if (lang.bcp47Code != "unknown") Locale.forLanguageTag(lang.bcp47Code) else Locale("hi", "IN")
        val available = textToSpeech?.isLanguageAvailable(locale) ?: TextToSpeech.LANG_NOT_SUPPORTED
        if (available >= TextToSpeech.LANG_AVAILABLE) {
            textToSpeech?.language = locale
            textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "voice_readback")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        textToSpeech = null
    }

    fun setVoiceInputListener(listener: VoiceInputListener) {
        this.listener = listener
    }

    companion object {
        private const val ARG_VESSEL_CLASS = "vessel_class"

        fun newInstance(vesselClass: String? = null): VoiceInputBottomSheet {
            return VoiceInputBottomSheet().apply {
                arguments = Bundle().apply {
                    putString(ARG_VESSEL_CLASS, vesselClass)
                }
            }
        }
    }
}
