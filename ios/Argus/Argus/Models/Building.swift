import Foundation

// MARK: - Identify API

struct IdentifyResponse: Codable {
    let candidates: [BuildingCandidate]
}

struct BuildingCandidate: Codable, Identifiable {
    var id: String { bbl }
    let bbl: String
    let address: String
    let distance: Double
    let score: Double
    var profile: BuildingProfile?
    var story: BuildingStory?
}

struct BuildingProfile: Codable {
    let yearBuilt: Int?
    let stories: Int?
    let units: Int?
    let lotArea: Int?
    let buildingClass: String?
    let zoneDist: String?
    let far: Double?
    let maxFar: Double?
    let landmark: Bool?
    let landmarkName: String?
    let architect: String?
    let architecturalStyle: String?
    let assessedLand: Int?
    let assessedTotal: Int?
    let taxClass: String?
    let latitude: Double?
    let longitude: Double?
}

struct BuildingStory: Codable {
    let headline: String
    let narrative: String
    let funFacts: [String]
    let generatedAt: String
}

// MARK: - Detail API

struct BuildingDetail: Codable {
    let profile: BuildingProfile?
    let story: BuildingStory?
    let ownership: [OwnershipRecord]?
    let violations: [Violation]?
    let permits: [Permit]?
}

struct OwnershipRecord: Codable, Identifiable {
    var id: String { "\(name)-\(type)" }
    let name: String
    let type: String
    let percentage: Double?
    let since: String?
}

struct Violation: Codable, Identifiable {
    var id: String { "\(source)-\(violationId)" }
    let violationId: String
    let source: String
    let date: String?
    let description: String
    let status: String?
    let severity: String?
}

struct Permit: Codable, Identifiable {
    var id: String { "\(jobNumber)-\(type)" }
    let jobNumber: String
    let type: String
    let date: String?
    let description: String
    let status: String?
    let applicant: String?
}

// MARK: - Legacy (kept for OfflineQueue compatibility)

struct PresignResponse: Codable {
    let sightingId: String
    let plateUploadUrl: String
    let vehicleUploadUrl: String
}
