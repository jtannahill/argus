import Vision
import CoreImage
import UIKit

class PlateDetector: ObservableObject {
    @Published var lastDetectedPlate: String?
    @Published var lastConfidence: Double = 0

    private var bestFrameInWindow: (image: CIImage, sharpness: Double, plate: String, confidence: Double)?
    private var windowStart = Date()
    private let windowDuration: TimeInterval = 1.0 // 1-second window

    func processFrame(_ sampleBuffer: CMSampleBuffer) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)

        let request = VNRecognizeTextRequest { [weak self] request, error in
            self?.handleTextRecognition(request: request, image: ciImage)
        }
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false

        try? VNImageRequestHandler(ciImage: ciImage).perform([request])
    }

    private func handleTextRecognition(request: VNRequest, image: CIImage) {
        guard let results = request.results as? [VNRecognizedTextObservation] else { return }

        for observation in results {
            guard let candidate = observation.topCandidates(1).first else { continue }
            let text = candidate.string.uppercased().replacingOccurrences(of: " ", with: "")

            // Basic plate pattern: 2-8 alphanumeric characters
            guard text.count >= 2 && text.count <= 8,
                  text.range(of: "^[A-Z0-9]+$", options: .regularExpression) != nil else { continue }

            let sharpness = computeSharpness(image: image, region: observation.boundingBox)
            let confidence = Double(candidate.confidence)

            // Track best frame in 1-second window
            let now = Date()
            if now.timeIntervalSince(windowStart) > windowDuration {
                // Window expired — emit best frame
                if let best = bestFrameInWindow {
                    DispatchQueue.main.async {
                        self.lastDetectedPlate = best.plate
                        self.lastConfidence = best.confidence
                    }
                }
                bestFrameInWindow = nil
                windowStart = now
            }

            if bestFrameInWindow == nil || sharpness > bestFrameInWindow!.sharpness {
                bestFrameInWindow = (image, sharpness, text, confidence)
            }
        }
    }

    private func computeSharpness(image: CIImage, region: CGRect) -> Double {
        // Laplacian variance as sharpness metric
        let cropped = image.cropped(to: CGRect(
            x: region.origin.x * image.extent.width,
            y: region.origin.y * image.extent.height,
            width: region.width * image.extent.width,
            height: region.height * image.extent.height
        ))
        // Simplified — use edge detection as proxy
        guard let edges = CIFilter(name: "CIEdges", parameters: [kCIInputImageKey: cropped])?.outputImage else {
            return 0
        }
        let extent = edges.extent
        var bitmap = [UInt8](repeating: 0, count: 4)
        CIContext().render(edges, toBitmap: &bitmap, rowBytes: 4, bounds: CGRect(x: 0, y: 0, width: 1, height: 1), format: .RGBA8, colorSpace: CGColorSpaceCreateDeviceRGB())
        return Double(bitmap[0]) / 255.0
    }
}
