import Foundation
import Network
import CoreLocation
import Observation

@Observable
@MainActor
class OfflineQueue {
    static let shared = OfflineQueue()
    var isOnline = true
    var lastError: String?
    var isSyncing = false

    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "offline.queue.monitor")

    // Building scan queue — stores pending identify requests for when connectivity returns
    struct PendingScan: Codable, Identifiable {
        let id: UUID
        let latitude: Double
        let longitude: Double
        let heading: Double
        let timestamp: Date
    }

    private var pendingScans: [PendingScan] = []

    // Legacy plate capture queue (kept for backward compatibility)
    private var pendingCaptures: [(capture: Capture, plateImage: Data, vehicleImage: Data)] = []

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let satisfied = path.status == .satisfied
            Task { @MainActor [weak self] in
                self?.isOnline = satisfied
                if satisfied {
                    self?.syncPending()
                }
            }
        }
        monitor.start(queue: monitorQueue)
    }

    // MARK: - Building Scans

    func enqueueScan(latitude: Double, longitude: Double, heading: Double) {
        let scan = PendingScan(
            id: UUID(),
            latitude: latitude,
            longitude: longitude,
            heading: heading,
            timestamp: Date()
        )
        pendingScans.append(scan)
        pendingScans.sort { $0.timestamp < $1.timestamp }
        lastError = nil

        if isOnline {
            syncPending()
        }
    }

    var pendingScanCount: Int {
        return pendingScans.count
    }

    // MARK: - Legacy Plate Captures

    func enqueue(capture: Capture, plateImage: Data, vehicleImage: Data) {
        pendingCaptures.append((capture, plateImage, vehicleImage))
        pendingCaptures.sort { $0.capture.timestamp < $1.capture.timestamp }
        lastError = nil

        if isOnline {
            syncPending()
        }
    }

    var pendingCount: Int {
        return pendingCaptures.count + pendingScans.count
    }

    // MARK: - Sync

    private func syncPending() {
        guard !isSyncing else { return }
        let scansToSync = pendingScans
        let capturesToSync = pendingCaptures
        guard !scansToSync.isEmpty || !capturesToSync.isEmpty else { return }
        isSyncing = true

        Task {
            await AuthManager.shared.ensureToken()

            // Sync building scans
            for scan in scansToSync {
                do {
                    let _ = try await ApiClient.shared.identify(
                        latitude: scan.latitude,
                        longitude: scan.longitude,
                        heading: scan.heading
                    )
                    pendingScans.removeAll { $0.id == scan.id }
                    lastError = nil
                } catch {
                    lastError = error.localizedDescription
                    break
                }
            }

            // Sync legacy plate captures
            for item in capturesToSync {
                do {
                    let response = try await ApiClient.shared.presign(capture: item.capture)
                    try await ApiClient.shared.uploadImage(item.plateImage, to: response.plateUploadUrl)
                    try await ApiClient.shared.uploadImage(item.vehicleImage, to: response.vehicleUploadUrl)

                    pendingCaptures.removeAll { $0.capture.id == item.capture.id }
                    lastError = nil
                } catch {
                    lastError = error.localizedDescription
                    break
                }
            }
            isSyncing = false
        }
    }
}
