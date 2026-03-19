import Foundation

@MainActor
class ApiClient {
    static let shared = ApiClient()
    private let baseUrl: String
    private var token: String = ""

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    init() {
        baseUrl = Bundle.main.infoDictionary?["API_URL"] as? String ?? ""
    }

    func setToken(_ token: String) { self.token = token }

    // MARK: - Building Identification

    func identify(latitude: Double, longitude: Double, heading: Double, radius: Double = 100) async throws -> IdentifyResponse {
        guard !baseUrl.isEmpty else {
            throw ApiError.message("API_URL not set in Info.plist")
        }
        guard !token.isEmpty else {
            throw ApiError.message("No auth token — Cognito login failed")
        }

        var request = URLRequest(url: URL(string: "\(baseUrl)/identify")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "latitude": latitude,
            "longitude": longitude,
            "heading": heading,
            "radius": radius,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("Identify \(http.statusCode): \(body.prefix(200))")
        }

        return try decoder.decode(IdentifyResponse.self, from: data)
    }

    func getBuilding(bbl: String) async throws -> BuildingDetail {
        guard !baseUrl.isEmpty else {
            throw ApiError.message("API_URL not set in Info.plist")
        }
        guard !token.isEmpty else {
            throw ApiError.message("No auth token — Cognito login failed")
        }

        var request = URLRequest(url: URL(string: "\(baseUrl)/buildings/\(bbl)")!)
        request.httpMethod = "GET"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)

        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("GetBuilding \(http.statusCode): \(body.prefix(200))")
        }

        return try decoder.decode(BuildingDetail.self, from: data)
    }

    // MARK: - Pinned Buildings

    func pinBuilding(bbl: String, building: BuildingCandidate) async throws {
        guard !baseUrl.isEmpty else { throw ApiError.message("API_URL not set in Info.plist") }
        guard !token.isEmpty else { throw ApiError.message("No auth token — Cognito login failed") }

        var request = URLRequest(url: URL(string: "\(baseUrl)/pins")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        var body: [String: Any] = ["bbl": bbl, "address": building.address]
        if let profile = building.profile {
            var profileDict: [String: Any] = [:]
            if let lat = profile.latitude { profileDict["latitude"] = lat }
            if let lon = profile.longitude { profileDict["longitude"] = lon }
            if let y = profile.yearBuilt { profileDict["yearBuilt"] = y }
            if let s = profile.stories { profileDict["stories"] = s }
            if let u = profile.residentialUnits { profileDict["residentialUnits"] = u }
            if let lm = profile.landmark { profileDict["landmark"] = lm }
            if let ln = profile.landmarkName { profileDict["landmarkName"] = ln }
            if let bc = profile.buildingClass { profileDict["buildingClass"] = bc }
            body["profile"] = profileDict
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("PinBuilding \(http.statusCode): \(body.prefix(200))")
        }
    }

    func unpinBuilding(bbl: String) async throws {
        guard !baseUrl.isEmpty else { throw ApiError.message("API_URL not set in Info.plist") }
        guard !token.isEmpty else { throw ApiError.message("No auth token — Cognito login failed") }

        var request = URLRequest(url: URL(string: "\(baseUrl)/pins/\(bbl)")!)
        request.httpMethod = "DELETE"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("UnpinBuilding \(http.statusCode): \(body.prefix(200))")
        }
    }

    func getPinnedBuildings() async throws -> [BuildingCandidate] {
        guard !baseUrl.isEmpty else { throw ApiError.message("API_URL not set in Info.plist") }
        guard !token.isEmpty else { throw ApiError.message("No auth token — Cognito login failed") }

        var request = URLRequest(url: URL(string: "\(baseUrl)/pins")!)
        request.httpMethod = "GET"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("GetPinnedBuildings \(http.statusCode): \(body.prefix(200))")
        }

        struct PinsResponse: Decodable {
            let buildings: [BuildingCandidate]
        }
        return try decoder.decode(PinsResponse.self, from: data).buildings
    }

    // MARK: - Legacy (plate capture upload)

    func presign(capture: Capture) async throws -> PresignResponse {
        guard !baseUrl.isEmpty else {
            throw ApiError.message("API_URL not set in Info.plist")
        }
        guard !token.isEmpty else {
            throw ApiError.message("No auth token — Cognito login failed")
        }

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

        let (data, response) = try await URLSession.shared.data(for: request)

        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("Presign \(http.statusCode): \(body.prefix(200))")
        }

        return try JSONDecoder().decode(PresignResponse.self, from: data)
    }

    func uploadImage(_ imageData: Data, to url: String) async throws {
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "PUT"
        request.addValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        request.httpBody = imageData

        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            let body = String(data: data, encoding: .utf8) ?? "no body"
            throw ApiError.message("Upload \(http.statusCode): \(body.prefix(200))")
        }
    }
}

enum ApiError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let msg): return msg
        }
    }
}

// Legacy model kept for OfflineQueue compatibility
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
        case scan, point, sweep
    }
}
