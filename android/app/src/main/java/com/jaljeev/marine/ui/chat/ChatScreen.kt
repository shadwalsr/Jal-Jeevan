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

        if (state.locationUnavailable) {
            Text(
                "No position fix available, so this question was sent without your location.",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.tertiary,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
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
private fun MessageItem(message: ChatMessage, onShowOnMap: (com.jaljeev.marine.domain.GeoPoint) -> Unit) {
    if (message.fromUser) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Text(
                message.text,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier
                    .widthIn(max = 300.dp)
                    .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(14.dp))
                    .padding(horizontal = 14.dp, vertical = 10.dp),
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
            Text(message.text, style = MaterialTheme.typography.bodyLarge)
            if (message.trace.isNotEmpty()) {
                ExpandableSection(stringResource(R.string.planner_trace)) {
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
                tint = if (attachLocation) MaterialTheme.colorScheme.secondary
                else MaterialTheme.colorScheme.onSurfaceVariant,
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
            shape = RoundedCornerShape(14.dp),
        )
        IconButton(onClick = onSend, enabled = enabled && value.isNotBlank()) {
            Icon(
                Icons.AutoMirrored.Filled.Send,
                contentDescription = stringResource(R.string.chat_send),
                modifier = Modifier.size(24.dp),
                tint = if (enabled && value.isNotBlank()) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
