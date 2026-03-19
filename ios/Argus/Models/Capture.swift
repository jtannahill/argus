import Foundation
import CoreLocation

struct Capture: Codable, Identifiable {
    let id: UUID
    let plate: String
    let confidence: Double
    let latitude: Double
    let longitude: Double
    let timestamp: Date
    let mode: CaptureMode
    var synced: Bool = false

    enum CaptureMode: String, Codable {
        case drive, point, watch
    }
}

struct PresignResponse: Codable {
    let sightingId: String
    let plateUploadUrl: String
    let vehicleUploadUrl: String
}
