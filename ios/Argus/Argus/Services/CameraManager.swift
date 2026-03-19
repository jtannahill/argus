import AVFoundation
import UIKit
import Observation

@Observable
class CameraManager: NSObject {
    var isRunning = false

    let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private let queue = DispatchQueue(label: "camera.queue")

    @ObservationIgnored
    var onFrame: (@Sendable (CMSampleBuffer) -> Void)?

    func setup() {
        queue.async { [self] in
            session.beginConfiguration()
            session.sessionPreset = .high

            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: device) else {
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
        onFrame?(sampleBuffer)
    }
}
