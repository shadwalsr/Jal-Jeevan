package com.jaljeev.ui.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.speech.tts.TextToSpeech
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jaljeev.marine.R
import com.jaljeev.voice.AudioRecorder
import com.jaljeev.voice.IndianLanguage
import com.jaljeev.voice.SarvamApiClient
import com.jaljeev.voice.SarvamRepository
import com.jaljeev.voice.VoiceUiState
import com.jaljeev.voice.VoiceViewModel
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceInputDialog(
    onDismiss: () -> Unit,
    onTranscriptReady: (String) -> Unit,
    onPutInChat: ((String) -> Unit)? = null,
    vesselClass: String? = null,
) {
    val context = LocalContext.current
    val view = LocalView.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    val viewModel: VoiceViewModel = viewModel(
        factory = VoiceViewModel.factory(
            SarvamRepository(SarvamApiClient.create()),
            AudioRecorder(context.applicationContext)
        )
    )

    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val amplitude by viewModel.amplitude.collectAsStateWithLifecycle()
    val selectedLanguage by viewModel.selectedLanguage.collectAsStateWithLifecycle()
    val elapsedMs by viewModel.elapsedMs.collectAsStateWithLifecycle()

    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasMicPermission = granted
    }

    // TTS engine for readback
    var ttsEngine by remember { mutableStateOf<TextToSpeech?>(null) }
    var isTtsReady by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        val tts = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                isTtsReady = true
                ttsEngine?.setSpeechRate(0.85f)
            }
        }
        ttsEngine = tts
        onDispose {
            tts.stop()
            tts.shutdown()
        }
    }

    // Initialize voice language from app's selected language
    LaunchedEffect(Unit) {
        val appLangCode = com.jaljeev.marine.util.LocaleHelper.getPersistedLanguage(context)
        val matched = IndianLanguage.entries.find {
            it.bcp47Code.startsWith(appLangCode) || (appLangCode == "or" && it == IndianLanguage.ODIA)
        }
        if (matched != null) {
            viewModel.setLanguage(matched)
        }
    }

    // Readback on success
    LaunchedEffect(uiState) {
        if (uiState is VoiceUiState.Success) {
            val transcript = (uiState as VoiceUiState.Success).transcript
            if (isTtsReady && transcript.isNotBlank()) {
                val locale = if (selectedLanguage.bcp47Code != "unknown") {
                    Locale.forLanguageTag(selectedLanguage.bcp47Code)
                } else {
                    Locale("hi", "IN")
                }
                val available = ttsEngine?.isLanguageAvailable(locale) ?: TextToSpeech.LANG_NOT_SUPPORTED
                if (available >= TextToSpeech.LANG_AVAILABLE) {
                    ttsEngine?.language = locale
                    ttsEngine?.speak(transcript, TextToSpeech.QUEUE_FLUSH, null, "voice_readback")
                }
            }
        }
    }

    // Waveform history buffer
    val barHistory = remember { mutableStateListOf<Float>().apply { repeat(30) { add(0.05f) } } }
    LaunchedEffect(amplitude) {
        if (barHistory.size >= 30) {
            barHistory.removeAt(0)
        }
        val norm = (amplitude.toFloat() / 32767f).coerceIn(0.05f, 1.0f)
        barHistory.add(norm)
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Language selector dropdown
            var langExpanded by remember { mutableStateOf(false) }
            val coastalLangs = remember { IndianLanguage.coastalPriority() }

            Box(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                        .clickable { langExpanded = true }
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${selectedLanguage.nativeScript} (${selectedLanguage.displayName})",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        text = "▼",
                        fontSize = 10.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                DropdownMenu(
                    expanded = langExpanded,
                    onDismissRequest = { langExpanded = false },
                    modifier = Modifier.fillMaxWidth(0.88f)
                ) {
                    coastalLangs.forEach { lang ->
                        DropdownMenuItem(
                            text = {
                                Text(
                                    "${lang.nativeScript} — ${lang.displayName}",
                                    fontWeight = if (lang == selectedLanguage) FontWeight.Bold else FontWeight.Normal
                                )
                            },
                            onClick = {
                                viewModel.setLanguage(lang)
                                langExpanded = false
                            }
                        )
                    }
                }
            }

            Spacer(Modifier.height(16.dp))

            // Waveform visualizer
            val isListening = uiState is VoiceUiState.Listening
            if (isListening) {
                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(colorResource(R.color.white))
                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp))
                        .padding(horizontal = 8.dp, vertical = 6.dp)
                ) {
                    val count = barHistory.size
                    val barSpacing = size.width / count
                    val barWidth = (barSpacing * 0.6f).coerceAtLeast(3f)
                    val centerY = size.height / 2f

                    for (i in 0 until count) {
                        val x = i * barSpacing + barSpacing / 2f
                        val h = (barHistory[i] * size.height * 0.9f).coerceAtLeast(4f)
                        drawRoundRect(
                            color = Color(0xFFE53935), // mic active red
                            topLeft = Offset(x - barWidth / 2f, centerY - h / 2f),
                            size = Size(barWidth, h),
                            cornerRadius = CornerRadius(2f, 2f)
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                // Elapsed timer
                val seconds = (elapsedMs / 1000) % 60
                val minutes = (elapsedMs / 1000) / 60
                Text(
                    text = String.format(Locale.US, "%02d:%02d", minutes, seconds),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    color = colorResource(R.color.mic_active_red),
                )
            } else {
                Spacer(Modifier.height(16.dp))
            }

            Spacer(Modifier.height(12.dp))

            // Giant Push-To-Talk circular button (120dp)
            val btnColor = if (isListening) colorResource(R.color.mic_active_red) else colorResource(R.color.jaljeev_maritime_blue)

            Box(
                modifier = Modifier
                    .size(120.dp)
                    .clip(CircleShape)
                    .background(btnColor)
                    .pointerInput(hasMicPermission) {
                        detectTapGestures(
                            onPress = {
                                if (!hasMicPermission) {
                                    permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                    return@detectTapGestures
                                }
                                val pressStart = System.currentTimeMillis()
                                val wasListening = viewModel.uiState.value is VoiceUiState.Listening
                                if (!wasListening && viewModel.uiState.value !is VoiceUiState.Processing) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.startRecording()
                                }
                                tryAwaitRelease()
                                val duration = System.currentTimeMillis() - pressStart
                                if (wasListening) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.stopRecording()
                                } else if (duration > 400 && viewModel.uiState.value is VoiceUiState.Listening) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.stopRecording()
                                }
                            }
                        )
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.Mic,
                    contentDescription = stringResource(R.string.voice_idle_hint),
                    modifier = Modifier.size(52.dp),
                    tint = Color.White
                )
            }

            Spacer(Modifier.height(16.dp))

            // Status message
            val statusText = when (uiState) {
                is VoiceUiState.Idle -> stringResource(R.string.voice_idle_hint)
                is VoiceUiState.Listening -> stringResource(R.string.voice_listening)
                is VoiceUiState.Processing -> stringResource(R.string.voice_processing)
                is VoiceUiState.Success -> "✓ ${(uiState as VoiceUiState.Success).detectedLanguage ?: ""}"
                is VoiceUiState.Error -> (uiState as VoiceUiState.Error).error.message
                is VoiceUiState.PartialResult -> ""
            }

            Text(
                text = statusText,
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                color = if (uiState is VoiceUiState.Error) colorResource(R.color.mic_active_red) else MaterialTheme.colorScheme.onSurfaceVariant
            )

            // Transcript preview
            if (uiState is VoiceUiState.Success) {
                val transcript = (uiState as VoiceUiState.Success).transcript
                Spacer(Modifier.height(14.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                        .padding(14.dp)
                ) {
                    Text(
                        text = transcript,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontWeight = FontWeight.Medium
                    )
                }

                Spacer(Modifier.height(14.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (onPutInChat != null) {
                        Button(
                            onClick = {
                                onPutInChat(transcript)
                                onDismiss()
                            },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(999.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                                contentColor = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        ) {
                            Text(
                                "Put in Chat ✏️",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }

                    Button(
                        onClick = {
                            onTranscriptReady(transcript)
                            onDismiss()
                        },
                        modifier = Modifier
                            .weight(1.3f)
                            .height(48.dp),
                        shape = RoundedCornerShape(999.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = colorResource(R.color.safe_green),
                            contentColor = Color.White
                        )
                    ) {
                        Text(
                            "Send Now 🚀",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            TextButton(
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    stringResource(R.string.voice_cancel),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(Modifier.height(12.dp))
        }
    }
}
