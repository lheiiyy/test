package com.tddprojectai.parentalmonitor.core

import java.time.ZoneId
import java.time.ZonedDateTime
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class AlertsTest {

    private val zone = ZoneId.of("UTC")

    @Test
    fun `formats install alert with zero-padded time`() {
        val timestamp = ZonedDateTime.of(2026, 1, 1, 9, 42, 0, 0, zone).toInstant().toEpochMilli()

        val formatted = AlertDisplayFormatter.format(timestamp, AlertMessages.newAppInstalled("Roblox"), zone)

        assertEquals("09:42  New application installed: Roblox", formatted)
    }

    @Test
    fun `formats disable attempt alert`() {
        val timestamp = ZonedDateTime.of(2026, 1, 1, 10, 31, 0, 0, zone).toInstant().toEpochMilli()

        val formatted = AlertDisplayFormatter.format(timestamp, AlertMessages.disableAttempt(), zone)

        assertEquals("10:31  Attempt to disable device administrator", formatted)
    }

    @Test
    fun `pads single-digit hour and minute`() {
        val timestamp = ZonedDateTime.of(2026, 1, 1, 1, 5, 0, 0, zone).toInstant().toEpochMilli()

        val formatted = AlertDisplayFormatter.format(timestamp, AlertMessages.appRemoved("Chrome"), zone)

        assertEquals("01:05  Application removed: Chrome", formatted)
    }
}
