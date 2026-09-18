package com.droidbridge.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.droidbridge.companion.databinding.ActivityMainBinding
import com.google.android.material.snackbar.Snackbar

/**
 * The DroidBridge Companion app's one and only screen for Phase 2.
 *
 * Deliberately minimal and fully transparent: it always shows what it's
 * connected to (nothing, yet), what permission it holds, and gives the user
 * a way to disconnect. There is no background service, no hidden state, and
 * no permission requested until the user taps the button that needs it.
 * See docs/UI_SPEC.md and the project brief's Android requirements.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val requestCameraPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            updatePermissionStatus(granted)
            if (granted) {
                // Phase 2 scope: no real QR decoding/camera pipeline yet — see
                // docs/FEATURE_SPEC.md and ScrcpyService's "Not implemented in
                // Phase 2" convention on the desktop side. We tell the user the
                // truth instead of pretending to scan.
                Snackbar.make(binding.root, R.string.scan_qr_not_implemented, Snackbar.LENGTH_LONG).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        updatePermissionStatus(hasCameraPermission())
        updateConnectionStatus(connectedDeviceLabel = null)

        binding.scanQrButton.setOnClickListener {
            if (hasCameraPermission()) {
                Snackbar.make(binding.root, R.string.scan_qr_not_implemented, Snackbar.LENGTH_LONG).show()
            } else {
                requestCameraPermission.launch(Manifest.permission.CAMERA)
            }
        }

        binding.disconnectButton.setOnClickListener {
            // No live connection exists yet in Phase 2; this just re-asserts
            // the disconnected state so the control's behavior is honest and
            // wired up ahead of the real pairing/session feature.
            updateConnectionStatus(connectedDeviceLabel = null)
        }
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    private fun updatePermissionStatus(cameraGranted: Boolean) {
        binding.permissionStatus.text = getString(
            if (cameraGranted) R.string.permission_status_camera_granted
            else R.string.permission_status_camera_denied,
        )
    }

    private fun updateConnectionStatus(connectedDeviceLabel: String?) {
        binding.disconnectButton.isEnabled = connectedDeviceLabel != null
        binding.connectionStatus.text = if (connectedDeviceLabel != null) {
            getString(R.string.connection_status_connected, connectedDeviceLabel)
        } else {
            getString(R.string.connection_status_disconnected)
        }
    }
}
