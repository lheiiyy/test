package com.tddprojectai.parentalmonitor.core

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

class ForegroundSessionTrackerTest {

    @Test
    fun `first foreground app produces no closed session yet`() {
        val tracker = ForegroundSessionTracker()

        val closed = tracker.onForegroundChanged("com.chrome", 1_000)

        assertNull(closed)
    }

    @Test
    fun `switching apps closes the previous session`() {
        val tracker = ForegroundSessionTracker()
        tracker.onForegroundChanged("com.chrome", 1_000)

        val closed = tracker.onForegroundChanged("com.roblox", 4_000)

        assertEquals(AppSession("com.chrome", 1_000, 4_000), closed)
    }

    @Test
    fun `repeated reports of the same package do not close or restart the session`() {
        val tracker = ForegroundSessionTracker()
        tracker.onForegroundChanged("com.chrome", 1_000)

        val closed = tracker.onForegroundChanged("com.chrome", 2_000)

        assertNull(closed)
        assertEquals(AppSession("com.chrome", 1_000, 5_000), tracker.closeOpenSession(5_000))
    }

    @Test
    fun `closeOpenSession flushes the current session and clears state`() {
        val tracker = ForegroundSessionTracker()
        tracker.onForegroundChanged("com.chrome", 1_000)

        val closed = tracker.closeOpenSession(3_000)

        assertEquals(AppSession("com.chrome", 1_000, 3_000), closed)
        assertNull(tracker.closeOpenSession(4_000))
    }
}
