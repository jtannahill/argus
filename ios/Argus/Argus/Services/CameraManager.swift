import AVFoundation
import UIKit
import Observation

@Observable
class CameraManager: NSObject {
    var isRunning = false
    var errorMessage: String?

    let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private let queue = DispatchQueue(label: "camera.queue")

    // Stored outside @Observable to allow nonisolated access from delegate
    nonisolated(unsafe) static var _onFrame: (@Sendable (CMSampleBuffer) -> Void)?

    func setup() {
        // Check permission first
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            startSession()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                if granted {
                    self.startSession()
                } else {
                    Task { @MainActor in
                        self.errorMessage = "Camera access denied"
                    }
                }
            }
        default:
            Task { @MainActor in
                self.errorMessage = "Camera access denied. Go to Settings → Argus → Camera"
            }
        }
    }

    private func startSession() {
        queue.async { [self] in
            session.beginConfiguration()
            session.sessionPreset = .high

            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
                Task { @MainActor in self.errorMessage = "No back camera found" }
                session.commitConfiguration()
                return
            }

            guard let input = try? AVCaptureDeviceInput(device: device) else {
                Task { @MainActor in self.errorMessage = "Cannot create camera input" }
                session.commitConfiguration()
                return
            }

            if session.canAddInput(input) { session.addInput(input) }

            output.setSampleBufferDelegate(self, queue: queue)
            output.alwaysDiscardsLateVideoFrames = true
            if session.canAddOutput(output) { session.addOutput(output) }

            session.commitConfiguration()
            session.startRunning()

            Task { @MainActor in
                self.isRunning = true
                self.errorMessage = nil
            }
        }
    }

    func stop() {
        queue.async { [self] in
            session.stopRunning()
            Task { @MainActor in
                self.isRunning = false
            }
        }
    }
}

extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        CameraManager._onFrame?(sampleBuffer)
    }
}
