package com.jaljeev.marine.ui.chat

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOff
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
            onSend = {
                vm.send(input)
                input = ""
            },
        )
    }
}

@Composable
private fun EmptyState(onPick: (String) -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
    ) {
        Text(stringResource(R.string.chat_empty_title), style = MaterialTheme.typography.titleLarge)
        Text(
            stringResource(R.string.chat_empty_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SUGGESTIONS.forEach { suggestion ->
            Text(
                suggestion,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(10.dp))
                    .clickable { onPick(suggestion) }
                    .padding(12.dp),
            )
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
                        withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
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
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Text(
                message.text,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier
                    .widthIn(max = 300.dp)
                    .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(16.dp))
                    .padding(horizontal = 16.dp, vertical = 10.dp),
            )
        }
        return
    }

    if (message.isError) {
        ErrorCard(message.text, message.errorDetail)
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionCard {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(bottom = 8.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.15f), CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Filled.Navigation,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(14.dp)
                    )
                }
                Text(
                    "JalJeev Navigator",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            FormattedMarkdownText(message.text, style = MaterialTheme.typography.bodyMedium)
            if (message.trace.isNotEmpty()) {
                ExpandableSection("Agent reasoning trace (${message.trace.size} steps)") {
                    com.jaljeev.marine.ui.common.BulletList(message.trace)
                }
            }
        }
        message.evidence?.let { EvidenceCard(it, onShowOnMap = onShowOnMap) }
    }
}

@Composable
private fun InputBar(
    value: String,
    onValueChange: (String) -> Unit,
    enabled: Boolean,
    attachLocation: Boolean,
    onToggleLocation: () -> Unit,
    onSend: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        IconButton(onClick = onToggleLocation) {
            Icon(
                if (attachLocation) Icons.Filled.MyLocation else Icons.Filled.LocationOff,
                contentDescription = stringResource(R.string.chat_use_location),
                tint = if (attachLocation) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
            )
        }
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.weight(1f),
            placeholder = { Text(stringResource(R.string.chat_hint)) },
            maxLines = 4,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
            keyboardActions = KeyboardActions(onSend = { if (enabled) onSend() }),
            shape = RoundedCornerShape(20.dp),
        )
        IconButton(onClick = onSend, enabled = enabled && value.isNotBlank()) {
            Icon(
                Icons.AutoMirrored.Filled.Send,
                contentDescription = stringResource(R.string.chat_send),
                modifier = Modifier.size(24.dp),
                tint = if (enabled && value.isNotBlank()) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
            )
        }
    }
}
