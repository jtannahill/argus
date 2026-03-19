import Foundation
import Network
import Combine

@MainActor
class OfflineQueue: ObservableObject {
    static let shared = OfflineQueue()
    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "offline.queue.monitor")
    @Published var isOnline = true

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

        if isOnline {
            syncPending()
        }
    }

    private func syncPending() {
        let toSync = pendingCaptures

        Task {
            for item in toSync {
                do {
                    let response = try await ApiClient.shared.presign(capture: item.capture)
                    try await ApiClient.shared.uploadImage(item.plateImage, to: response.plateUploadUrl)
                    try await ApiClient.shared.uploadImage(item.vehicleImage, to: response.vehicleUploadUrl)

                    pendingCaptures.removeAll { $0.capture.id == item.capture.id }
                } catch {
                    break
                }
            }
        }
    }

    var pendingCount: Int {
        return pendingCaptures.count
    }
}
