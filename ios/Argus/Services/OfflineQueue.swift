import Foundation
import Network

class OfflineQueue: ObservableObject {
    static let shared = OfflineQueue()
    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "offline.queue.monitor")
    @Published var isOnline = true

    // In-memory queue (swap for Core Data in production)
    private var pendingCaptures: [(capture: Capture, plateImage: Data, vehicleImage: Data)] = []
    private let lock = NSLock()

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isOnline = path.status == .satisfied
            }
            if path.status == .satisfied {
                self?.syncPending()
            }
        }
        monitor.start(queue: monitorQueue)
    }

    func enqueue(capture: Capture, plateImage: Data, vehicleImage: Data) {
        lock.lock()
        pendingCaptures.append((capture, plateImage, vehicleImage))
        pendingCaptures.sort { $0.capture.timestamp < $1.capture.timestamp }
        lock.unlock()

        if isOnline {
            syncPending()
        }
    }

    private func syncPending() {
        lock.lock()
        let toSync = pendingCaptures
        lock.unlock()

        Task {
            for item in toSync {
                do {
                    let response = try await ApiClient.shared.presign(capture: item.capture)
                    try await ApiClient.shared.uploadImage(item.plateImage, to: response.plateUploadUrl)
                    try await ApiClient.shared.uploadImage(item.vehicleImage, to: response.vehicleUploadUrl)

                    lock.lock()
                    pendingCaptures.removeAll { $0.capture.id == item.capture.id }
                    lock.unlock()
                } catch {
                    break
                }
            }
        }
    }

    var pendingCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return pendingCaptures.count
    }
}
