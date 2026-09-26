package com.tddprojectai.parentalmonitor.core

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class SessionBuilderTest {

    @Test
    fun `single matched foreground-background pair becomes one session`() {
        val events = listOf(
            RawUsageEvent("com.youtube", RawEventType.FOREGROUND, 1_000),
            RawUsageEvent("com.youtube", RawEventType.BACKGROUND, 5_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 10_000)

        assertEquals(listOf(AppSession("com.youtube", 1_000, 5_000)), sessions)
    }

    @Test
    fun `interleaved apps produce sessions in chronological order`() {
        val events = listOf(
            RawUsageEvent("com.youtube", RawEventType.FOREGROUND, 0),
            RawUsageEvent("com.youtube", RawEventType.BACKGROUND, 1_000),
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 1_000),
            RawUsageEvent("com.chrome", RawEventType.BACKGROUND, 2_500),
            RawUsageEvent("com.roblox", RawEventType.FOREGROUND, 2_500),
            RawUsageEvent("com.roblox", RawEventType.BACKGROUND, 4_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 5_000)

        assertEquals(
            listOf(
                AppSession("com.youtube", 0, 1_000),
                AppSession("com.chrome", 1_000, 2_500),
                AppSession("com.roblox", 2_500, 4_000),
            ),
            sessions,
        )
    }

    @Test
    fun `missing background event is closed by the next app's foreground event`() {
        // Real devices sometimes drop a BACKGROUND event when the app is killed outright.
        val events = listOf(
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 0),
            RawUsageEvent("com.roblox", RawEventType.FOREGROUND, 3_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 10_000)

        assertEquals(
            listOf(
                AppSession("com.chrome", 0, 3_000),
                AppSession("com.roblox", 3_000, 10_000),
            ),
            sessions,
        )
    }

    @Test
    fun `still-foreground app at collection time yields an open session up to now`() {
        val events = listOf(
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 1_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 4_000)

        assertEquals(listOf(AppSession("com.chrome", 1_000, 4_000)), sessions)
    }

    @Test
    fun `duplicate foreground events for the same package without an intervening background are collapsed`() {
        val events = listOf(
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 0),
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 500),
            RawUsageEvent("com.chrome", RawEventType.BACKGROUND, 1_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 5_000)

        assertEquals(listOf(AppSession("com.chrome", 0, 1_000)), sessions)
    }

    @Test
    fun `spurious background event with no open session is ignored`() {
        val events = listOf(
            RawUsageEvent("com.chrome", RawEventType.BACKGROUND, 100),
            RawUsageEvent("com.roblox", RawEventType.FOREGROUND, 200),
            RawUsageEvent("com.roblox", RawEventType.BACKGROUND, 300),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 1_000)

        assertEquals(listOf(AppSession("com.roblox", 200, 300)), sessions)
    }

    @Test
    fun `unsorted input is sorted before processing`() {
        val events = listOf(
            RawUsageEvent("com.chrome", RawEventType.BACKGROUND, 2_500),
            RawUsageEvent("com.youtube", RawEventType.FOREGROUND, 0),
            RawUsageEvent("com.chrome", RawEventType.FOREGROUND, 1_000),
            RawUsageEvent("com.youtube", RawEventType.BACKGROUND, 1_000),
        )

        val sessions = SessionBuilder.buildSessions(events, openSessionEndMillis = 5_000)

        assertEquals(
            listOf(
                AppSession("com.youtube", 0, 1_000),
                AppSession("com.chrome", 1_000, 2_500),
            ),
            sessions,
        )
    }

    @Test
    fun `totalDurationByPackage sums and clips sessions to the requested range`() {
        val sessions = listOf(
            AppSession("com.youtube", 0, 2_000),
            AppSession("com.chrome", 2_000, 3_000),
            AppSession("com.youtube", 3_000, 6_000),
        )

        val totals = SessionBuilder.totalDurationByPackage(sessions, rangeStartMillis = 1_000, rangeEndMillis = 4_000)

        assertEquals(
            mapOf(
                "com.youtube" to (1_000L + 1_000L), // clipped [1000,2000) + [3000,4000)
                "com.chrome" to 1_000L,
            ),
            totals,
        )
    }

    @Test
    fun `totalDurationByPackage drops sessions entirely outside the range`() {
        val sessions = listOf(AppSession("com.chrome", 0, 100))

        val totals = SessionBuilder.totalDurationByPackage(sessions, rangeStartMillis = 200, rangeEndMillis = 300)

        assertEquals(emptyMap<String, Long>(), totals)
    }
}
