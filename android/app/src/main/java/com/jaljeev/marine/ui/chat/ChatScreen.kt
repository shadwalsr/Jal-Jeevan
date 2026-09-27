package com.jaljeev.marine.ui.chat

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOff
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jaljeev.marine.R
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.ui.common.ErrorCard
import com.jaljeev.marine.ui.common.EvidenceCard
import com.jaljeev.marine.ui.common.ExpandableSection
import com.jaljeev.marine.ui.common.LoadingRow
import com.jaljeev.marine.ui.common.SectionCard

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Navigation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle

private val SUGGESTIONS = listOf(
    "Is it safe to go out 20 km off Visakhapatnam today?",
    "Where is the safest place to fish within 30 km of me?",
    "What about six hours from now?",
    "What are the conditions at 17.65, 83.35?",
)

@Composable
fun ChatScreen(modifier: Modifier = Modifier) {
    val container = LocalContext.current.appContainer
    val vm: ChatViewModel = viewModel(factory = ChatViewModel.factory(container))
    val state by vm.state.collectAsStateWithLifecycle()

    var input by remember { mutableStateOf("") }
    var showVoiceDialog by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> vm.setAttachLocation(granted) }

    LaunchedEffect(state.messages.size, state.sending) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.lastIndex)
        }
    }

    Column(modifier.fillMaxSize().imePadding()) {
        Box(Modifier.weight(1f)) {
            if (state.messages.isEmpty()) {
                EmptyState(onPick = { suggestion -> vm.send(suggestion) })
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(state.messages, key = { it.id }) { message ->
                        MessageItem(message, onShowOnMap = vm::showOnMap)
                    }
                    if (state.sending) {
                        item { LoadingRow(stringResource(R.string.chat_thinking)) }
                    }
                }
            }
        }

        AnimatedVisibility(visible = state.locationUnavailable) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .background(
                        color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.6f),
                        shape = RoundedCornerShape(8.dp)
                    )
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Filled.LocationOff,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.tertiary,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        "No GPS fix available · sent without current location",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
                Icon(
                    Icons.Filled.Close,
                    contentDescription = "Dismiss",
                    tint = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = 0.7f),
                    modifier = Modifier
                        .size(16.dp)
                        .clickable { vm.dismissLocationWarning() }
                )
            }
        }

        InputBar(
            value = input,
            onValueChange = { input = it },
            enabled = !state.sending,
            attachLocation = state.attachLocation,
            onToggleLocation = {
                if (!state.attachLocation && !container.locationProvider.hasPermission()) {
                    permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                } else {
                    vm.setAttachLocation(!state.attachLocation)
                }
            },
            onVoiceClick = { showVoiceDialog = true },
            onSend = {
                vm.send(input)
                input = ""
            },
        )
    }

    if (showVoiceDialog) {
        com.jaljeev.ui.voice.VoiceInputDialog(
            onDismiss = { showVoiceDialog = false },
            onTranscriptReady = { transcript ->
                input = transcript
                vm.send(transcript)
                input = ""
            },
            onPutInChat = { transcript ->
                input = transcript
            }
        )
    }
}

@Composable
private fun EmptyState(onPick: (String) -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp, Alignment.CenterVertically),
    ) {
        Text(
            stringResource(R.string.chat_empty_title),
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            stringResource(R.string.chat_empty_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Box(
            Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(MaterialTheme.colorScheme.outline)
        )
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SUGGESTIONS.forEach { suggestion ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(3.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(3.dp))
                        .clickable { onPick(suggestion) }
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        suggestion,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
        }
    }
}

@Composable
fun FormattedMarkdownText(
    text: String,
    modifier: Modifier = Modifier,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyMedium
) {
    val annotatedString = remember(text) {
        buildAnnotatedString {
            var i = 0
            while (i < text.length) {
                val boldStart = text.indexOf("**", i)
                if (boldStart != -1) {
                    append(text.substring(i, boldStart))
                    val boldEnd = text.indexOf("**", boldStart + 2)
                    if (boldEnd != -1) {
                        withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) {
                            append(text.substring(boldStart + 2, boldEnd))
                        }
                        i = boldEnd + 2
                    } else {
                        append(text.substring(boldStart))
                        break
                    }
                } else {
                    append(text.substring(i))
                    break
                }
            }
        }
    }
    Text(
        text = annotatedString,
        modifier = modifier,
        style = style,
        color = MaterialTheme.colorScheme.onSurface,
        lineHeight = style.lineHeight,
    )
}

@Composable
private fun MessageItem(message: ChatMessage, onShowOnMap: (com.jaljeev.marine.domain.GeoPoint) -> Unit) {
    if (message.fromUser) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 10.dp, bottom = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                message.text,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outline)
            )
        }
        return
    }

    if (message.isError) {
        ErrorCard(message.text, message.errorDetail)
        return
    }

    var showTrace by remember { mutableStateOf(false) }
    val evidence = message.evidence
    val level = evidence?.let { com.jaljeev.marine.domain.RiskLevel.from(it.riskLevel) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        FormattedMarkdownText(
            text = message.text,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.fillMaxWidth(),
        )

        // Risk chip & coordinates meta row matching .reply__meta
        if (level != null && !level.isVeto && level.isScored) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                com.jaljeev.marine.ui.common.RiskBadge(level = level, score = evidence.riskScore)
                val lat = evidence.locationLat
                val lon = evidence.locationLon
                if (lat != null && lon != null) {
                    Box(
                        Modifier
                            .width(1.dp)
                            .height(12.dp)
                            .background(MaterialTheme.colorScheme.outline)
                    )
                    Text(
                        String.format("%.4f, %.4f", lat, lon),
                        fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        } else if (level != null && level.isVeto) {
            com.jaljeev.marine.ui.common.RiskBadge(level = level, score = null)
        }

        // Reply footer matching .reply__footer: N sources | N gaps | Reasoning | Open in Maps
        if (evidence != null) {
            val context = androidx.compose.ui.platform.LocalContext.current
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        width = 1.dp,
                        color = MaterialTheme.colorScheme.outline,
                        shape = androidx.compose.foundation.shape.RoundedCornerShape(0.dp)
                    )
                    .padding(vertical = 6.dp, horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    "${evidence.sourcesUsed.size} sources",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (evidence.dataGaps.isNotEmpty()) {
                    Box(Modifier.width(1.dp).height(12.dp).background(MaterialTheme.colorScheme.outline))
                    Text(
                        "${evidence.dataGaps.size} gaps",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.tertiary,
                    )
                }
                if (message.trace.isNotEmpty()) {
                    Box(Modifier.width(1.dp).height(12.dp).background(MaterialTheme.colorScheme.outline))
                    Text(
                        if (showTrace) "Hide reasoning" else "Reasoning",
                        style = MaterialTheme.typography.labelSmall,
                        textDecoration = androidx.compose.ui.text.style.TextDecoration.Underline,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.clickable { showTrace = !showTrace }
                    )
                }
                evidence.locationMapsUrl?.let { url ->
                    Box(Modifier.width(1.dp).height(12.dp).background(MaterialTheme.colorScheme.outline))
                    Text(
                        "Open in Maps",
                        style = MaterialTheme.typography.labelSmall,
                        textDecoration = androidx.compose.ui.text.style.TextDecoration.Underline,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.clickable {
                            runCatching {
                                context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)))
                            }
                        }
                    )
                }
            }
        }

        if (showTrace && message.trace.isNotEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(3.dp))
                    .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(3.dp))
                    .padding(10.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    "PLANNER TRACE",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                com.jaljeev.marine.ui.common.BulletList(message.trace, isMonospace = true)
            }
        }

        evidence?.let { EvidenceCard(it, onShowOnMap = onShowOnMap) }

        Box(
            Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
                .height(1.dp)
                .background(MaterialTheme.colorScheme.outline)
        )
    }
}

@Composable
private fun InputBar(
    value: String,
    onValueChange: (String) -> Unit,
    enabled: Boolean,
    attachLocation: Boolean,
    onToggleLocation: () -> Unit,
    onVoiceClick: () -> Unit,
    onSend: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(999.dp))
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(999.dp))
            .padding(start = 6.dp, end = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        IconButton(
            onClick = onToggleLocation,
            modifier = Modifier.size(36.dp),
        ) {
            Icon(
                if (attachLocation) Icons.Filled.MyLocation else Icons.Filled.LocationOff,
                contentDescription = stringResource(R.string.chat_use_location),
                modifier = Modifier.size(18.dp),
                tint = if (attachLocation) MaterialTheme.colorScheme.secondary
                else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
            )
        }
        IconButton(
            onClick = onVoiceClick,
            modifier = Modifier.size(36.dp),
        ) {
            Icon(
                Icons.Filled.Mic,
                contentDescription = "Voice input",
                modifier = Modifier.size(20.dp),
                tint = MaterialTheme.colorScheme.primary,
            )
        }
        androidx.compose.foundation.text.BasicTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier
                .weight(1f)
                .padding(vertical = 12.dp),
            textStyle = MaterialTheme.typography.bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
            maxLines = 4,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
            keyboardActions = KeyboardActions(onSend = { if (enabled && value.isNotBlank()) onSend() }),
            decorationBox = { innerTextField ->
                if (value.isEmpty()) {
                    Text(
                        stringResource(R.string.chat_hint),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                innerTextField()
            },
        )
        androidx.compose.material3.Button(
            onClick = onSend,
            enabled = enabled && value.isNotBlank(),
            shape = RoundedCornerShape(999.dp),
            colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
                disabledContainerColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.2f),
                disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
            ),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 0.dp),
            modifier = Modifier.height(34.dp),
        ) {
            Text(
                stringResource(R.string.chat_send),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}
