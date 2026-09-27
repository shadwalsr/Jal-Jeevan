package com.jaljeev.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MaritimeVocabularyTest {

    @Test
    fun test_keyterms_count_lte_50() {
        val keyterms = MaritimeVocabulary.getKeyterms()
        assertTrue("Keyterms count must be <= 50, but was ${keyterms.size}", keyterms.size <= 50)
    }

    @Test
    fun test_apply_corrections_paradip() {
        val input = "Is it safe near para deep or para dip today?"
        val corrected = MaritimeVocabulary.applyCorrections(input)
        assertEquals("Is it safe near Paradip or Paradip today?", corrected)
    }

    @Test
    fun test_apply_corrections_vizag() {
        val input = "Weather condition at vizag port"
        val corrected = MaritimeVocabulary.applyCorrections(input)
        assertEquals("Weather condition at Visakhapatnam port", corrected)
    }

    @Test
    fun test_apply_corrections_case_insensitive() {
        val input = "heading to VIZAG and PARA DEEP"
        val corrected = MaritimeVocabulary.applyCorrections(input)
        assertEquals("heading to Visakhapatnam and Paradip", corrected)
    }

    @Test
    fun test_no_term_longer_than_64_chars() {
        val keyterms = MaritimeVocabulary.getKeyterms()
        for (term in keyterms) {
            assertTrue("Term '$term' is longer than 64 characters", term.length <= 64)
        }
    }
}
