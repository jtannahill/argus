import Foundation

/// Auto-refreshing Cognito auth. Fetches token on launch and refreshes before expiry.
@MainActor
class AuthManager {
    static let shared = AuthManager()

    private let clientId = "7fbvjg0d8rcgi550j7pdvaljfp"
    private let username = "argus@plocamium.ventures"
    private let password = "ArgusField2026!"
    private let poolRegion = "us-east-1"

    private(set) var token: String = ""
    private var expiresAt: Date = .distantPast

    func ensureToken() async {
        if !token.isEmpty && Date() < expiresAt {
            return // Token still valid
        }
        await refreshToken()
    }

    func refreshToken() async {
        let url = URL(string: "https://cognito-idp.\(poolRegion).amazonaws.com")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/x-amz-json-1.1", forHTTPHeaderField: "Content-Type")
        request.addValue("AWSCognitoIdentityProviderService.InitiateAuth", forHTTPHeaderField: "X-Amz-Target")

        let body: [String: Any] = [
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": clientId,
            "AuthParameters": [
                "USERNAME": username,
                "PASSWORD": password,
            ]
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let result = json["AuthenticationResult"] as? [String: Any],
               let idToken = result["IdToken"] as? String,
               let expiresIn = result["ExpiresIn"] as? Int {
                token = idToken
                expiresAt = Date().addingTimeInterval(TimeInterval(expiresIn - 60)) // Refresh 1 min early
                ApiClient.shared.setToken(idToken)
            }
        } catch {
            // Auth failed — will retry on next ensureToken call
        }
    }
}
