package com.jaljeev.marine

import android.app.Application
import android.content.Context
import com.jaljeev.marine.data.cache.MarineStateCache
import com.jaljeev.marine.data.settings.SettingsRepository
import com.jaljeev.marine.domain.AppSession
import com.jaljeev.marine.domain.MarineRepository
import com.jaljeev.marine.location.LocationProvider
import com.jaljeev.marine.safety.Notifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

/**
 * Manual dependency container instead of an annotation-processing DI
 * framework. There are six singletons in this app; Hilt would add a KSP
 * round to every build and a version matrix to keep in step with Kotlin and
 * AGP, to solve a problem this size does not have.
 */
class AppContainer(context: Context) {

    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val settings = SettingsRepository(context, appScope)
    val locationProvider = LocationProvider(context)
    val session = AppSession()

    private val cache = MarineStateCache(context)
    val repository = MarineRepository(settings, cache)
}

class JalJeevApplication : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        Notifications.createChannels(this)
    }
}

/** Reaches the container from anywhere holding a Context (ViewModels, Service). */
val Context.appContainer: AppContainer
    get() = (applicationContext as JalJeevApplication).container
