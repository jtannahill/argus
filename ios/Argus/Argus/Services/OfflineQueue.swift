import Foundation
import Network
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

    func enqueue(capture: Capture, plateImage: Data, vehicleImage: Data) {
        pendingCaptures.append((capture, plateImage, vehicleImage))
        pendingCaptures.sort { $0.capture.timestamp < $1.capture.timestamp }
        lastError = nil

        if isOnline {
            syncPending()
        }
    }

    private func syncPending() {
        guard !isSyncing else { return }
        let toSync = pendingCaptures
        guard !toSync.isEmpty else { return }
        isSyncing = true

        Task {
            // Ensure we have a valid token
            await AuthManager.shared.ensureToken()

            for item in toSync {
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

    var pendingCount: Int {
        return pendingCaptures.count
    }
}
