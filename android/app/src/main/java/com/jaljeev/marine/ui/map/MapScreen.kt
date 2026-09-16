package com.jaljeev.marine.ui.map

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jaljeev.marine.R
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.ui.common.ErrorCard
import com.jaljeev.marine.ui.common.LoadingRow
import com.jaljeev.marine.ui.common.MarineStateDetails
import com.jaljeev.marine.ui.common.StaleDataBanner

@Composable
fun MapScreen(modifier: Modifier = Modifier) {
    val container = LocalContext.current.appContainer
    val vm: MapViewModel = viewModel(factory = MapViewModel.factory(container))
    val ui by vm.ui.collectAsStateWithLifecycle()
    val route by vm.route.collectAsStateWithLifecycle()
    val focus by vm.focus.collectAsStateWithLifecycle()

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> vm.onLocationPermissionResult(granted) }

    Box(modifier.fillMaxSize()) {

        MarineMapView(
            selected = ui.selected,
            route = route,
            focusRequest = focus,
            onMapClick = vm::onMapClick,
            boundaries = ui.boundaries,
            onCameraIdle = vm::onCameraIdle,
            modifier = Modifier.fillMaxSize(),
        )

        // Camera focus is a one-shot request; clearing it (after the map has
        // been handed this frame's value) lets the user pan freely afterwards
        // without being yanked back on every recomposition.
        LaunchedEffect(focus) { if (focus != null) vm.consumeFocus() }

        Column(
            Modifier
                .align(Alignment.TopStart)
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (ui.selected == null) {
                Pill(stringResource(R.string.map_tap_hint))
            }
            route?.let { overlay ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Pill(overlay.label)
                    TextButton(onClick = vm::clearRoute) {
                        Icon(Icons.Filled.Close, contentDescription = null)
                        Text("Clear", Modifier.padding(start = 4.dp))
                    }
                }
            }
        }

        SmallFloatingActionButton(
            onClick = {
                if (container.locationProvider.hasPermission()) {
                    vm.useMyLocation()
                } else {
                    permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                }
            },
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(12.dp),
        ) {
            Icon(Icons.Filled.MyLocation, contentDescription = stringResource(R.string.map_my_location))
        }

        val hasPanelContent = ui.selected != null || ui.error != null || ui.locationDenied
        if (hasPanelContent) {
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .fillMaxHeight(0.55f),
                color = MaterialTheme.colorScheme.background,
                shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp),
                tonalElevation = 3.dp,
            ) {
                Column(
                    Modifier
                        .verticalScroll(rememberScrollState())
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    if (ui.locationDenied) {
                        Text(
                            "Location permission is off, so this screen cannot centre on your position. " +
                                "You can still tap any point on the map.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.tertiary,
                        )
                    }
                    ui.boundaryNote?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.tertiary,
                        )
                    }
                    ui.staleAgeMillis?.let { StaleDataBanner(it) }
                    if (ui.loading) LoadingRow("Querying weather, ocean and geo agents…")
                    ui.error?.let { ErrorCard(it, ui.errorDetail, onRetry = vm::retry) }
                    ui.state?.let { MarineStateDetails(it) }
                }
            }
        }
    }
}

@Composable
private fun Pill(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier
            .background(
                MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
                RoundedCornerShape(20.dp),
            )
            .padding(horizontal = 12.dp, vertical = 8.dp),
    )
}
