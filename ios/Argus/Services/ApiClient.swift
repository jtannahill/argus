import Foundation

class ApiClient {
    static let shared = ApiClient()
    private let baseUrl: String
    private var token: String = ""

    init() {
        baseUrl = Bundle.main.infoDictionary?["API_URL"] as? String ?? ""
    }

    func setToken(_ token: String) { self.token = token }

    func presign(capture: Capture) async throws -> PresignResponse {
        var request = URLRequest(url: URL(string: "\(baseUrl)/captures/presign")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "plate": capture.plate,
            "confidence": capture.confidence,
            "latitude": capture.latitude,
            "longitude": capture.longitude,
            "timestamp": ISO8601DateFormatter().string(from: capture.timestamp),
            "mode": capture.mode.rawValue,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(PresignResponse.self, from: data)
    }

    func uploadImage(_ imageData: Data, to url: String) async throws {
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "PUT"
        request.addValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        request.httpBody = imageData
        let _ = try await URLSession.shared.data(for: request)
    }
}
