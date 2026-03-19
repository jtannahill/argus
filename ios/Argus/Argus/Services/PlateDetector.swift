import Vision
import CoreImage
import UIKit
import Observation

@Observable
class PlateDetector {
    var lastDetectedPlate: String?
    var lastConfidence: Double = 0
    var boundingBox: CGRect?  // Vision normalized coords (0-1, origin bottom-left)
    var smoothedBox: CGRect?  // Smoothed for display
    private let smoothing: CGFloat = 0.3  // 0 = no smoothing, 1 = frozen

    private var bestFrameInWindow: (image: CIImage, sharpness: Double, plate: String, confidence: Double)?
    private var windowStart = Date()
    private let windowDuration: TimeInterval = 1.0

    nonisolated func processFrame(_ sampleBuffer: CMSampleBuffer) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)

        let request = VNRecognizeTextRequest { [weak self] request, error in
            self?.handleTextRecognition(request: request, image: ciImage)
        }
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false

        try? VNImageRequestHandler(ciImage: ciImage).perform([request])
    }

    private nonisolated func handleTextRecognition(request: VNRequest, image: CIImage) {
        guard let results = request.results as? [VNRecognizedTextObservation] else { return }

        for observation in results {
            guard let candidate = observation.topCandidates(1).first else { continue }
            let text = candidate.string.uppercased().replacingOccurrences(of: " ", with: "")

            guard text.count >= 2 && text.count <= 8,
                  text.range(of: "^[A-Z0-9]+$", options: .regularExpression) != nil else { continue }

            let sharpness = computeSharpness(image: image, region: observation.boundingBox)
            let confidence = Double(candidate.confidence)
            let detectedText = text
            let box = observation.boundingBox

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.boundingBox = box
                if let prev = self.smoothedBox {
                    let s = self.smoothing
                    self.smoothedBox = CGRect(
                        x: prev.origin.x * s + box.origin.x * (1 - s),
                        y: prev.origin.y * s + box.origin.y * (1 - s),
                        width: prev.width * s + box.width * (1 - s),
                        height: prev.height * s + box.height * (1 - s)
                    )
                } else {
                    self.smoothedBox = box
                }

                let now = Date()
                if now.timeIntervalSince(self.windowStart) > self.windowDuration {
                    if let best = self.bestFrameInWindow {
                        self.lastDetectedPlate = best.plate
                        self.lastConfidence = best.confidence
                    }
                    self.bestFrameInWindow = nil
                    self.windowStart = now
                }

                if self.bestFrameInWindow == nil || sharpness > self.bestFrameInWindow!.sharpness {
                    self.bestFrameInWindow = (image, sharpness, detectedText, confidence)
                }
            }
        }
    }

    private nonisolated func computeSharpness(image: CIImage, region: CGRect) -> Double {
        let cropped = image.cropped(to: CGRect(
            x: region.origin.x * image.extent.width,
            y: region.origin.y * image.extent.height,
            width: region.width * image.extent.width,
            height: region.height * image.extent.height
        ))
        guard let edges = CIFilter(name: "CIEdges", parameters: [kCIInputImageKey: cropped])?.outputImage else {
            return 0
        }
        var bitmap = [UInt8](repeating: 0, count: 4)
        CIContext().render(edges, toBitmap: &bitmap, rowBytes: 4, bounds: CGRect(x: 0, y: 0, width: 1, height: 1), format: .RGBA8, colorSpace: CGColorSpaceCreateDeviceRGB())
        return Double(bitmap[0]) / 255.0
    }
}
