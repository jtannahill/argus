import AVFoundation
import UIKit

class CameraManager: NSObject, ObservableObject {
    @Published var isRunning = false

    let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private let queue = DispatchQueue(label: "camera.queue")

    private var _onFrame: (@Sendable (CMSampleBuffer) -> Void)?

    @MainActor
    func setOnFrame(_ handler: @escaping @Sendable (CMSampleBuffer) -> Void) {
        _onFrame = handler
    }

    @MainActor
    func setup() {
        session.sessionPreset = .high
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else { return }

        if session.canAddInput(input) { session.addInput(input) }

        output.setSampleBufferDelegate(self, queue: queue)
        output.alwaysDiscardsLateVideoFrames = true
        if session.canAddOutput(output) { session.addOutput(output) }

        session.startRunning()
        isRunning = true
    }

    @MainActor
    func stop() {
        session.stopRunning()
        isRunning = false
    }
}

extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        _onFrame?(sampleBuffer)
    }
}
