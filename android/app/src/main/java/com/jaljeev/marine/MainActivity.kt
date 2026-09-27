package com.jaljeev.marine

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import com.jaljeev.marine.ui.nav.JalJeevNavHost
import com.jaljeev.marine.ui.theme.JalJeevTheme
import com.jaljeev.marine.util.LocaleHelper

class MainActivity : ComponentActivity() {

    override fun attachBaseContext(newBase: Context) {
        LocaleHelper.init(newBase)
        super.attachBaseContext(LocaleHelper.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        LocaleHelper.init(this)

        setContent {
            val currentLang by LocaleHelper.currentLanguageFlow.collectAsState()
            key(currentLang.code) {
                JalJeevTheme {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background,
                    ) {
                        JalJeevNavHost()
                    }
                }
            }
        }
    }
}

