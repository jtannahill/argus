import Foundation
import CoreLocation
import Observation

@Observable
@MainActor
class BuildingIdentifier {
    var currentBuilding: BuildingCandidate?
    var candidates: [BuildingCandidate] = []
    var isIdentifying = false
    var error: String?

    private var lastIdentifyTime: Date = .distantPast
    private let debounceInterval: TimeInterval = 1.0

    func identify(location: CLLocation, heading: CLLocationDirection, radius: Double = 100, force: Bool = false) async {
        let now = Date()
        guard force || now.timeIntervalSince(lastIdentifyTime) >= debounceInterval else { return }
        guard !isIdentifying else { return }

        lastIdentifyTime = now
        isIdentifying = true
        error = nil

        do {
            await AuthManager.shared.ensureToken()
            let response = try await ApiClient.shared.identify(
                latitude: location.coordinate.latitude,
                longitude: location.coordinate.longitude,
                heading: heading,
                radius: radius
            )
            candidates = response.candidates
            if let top = response.candidates.first {
                currentBuilding = top
            }
        } catch {
            self.error = error.localizedDescription
        }

        isIdentifying = false
    }

    func selectCandidate(_ candidate: BuildingCandidate) {
        currentBuilding = candidate
    }

    func dismiss() {
        currentBuilding = nil
    }
}
