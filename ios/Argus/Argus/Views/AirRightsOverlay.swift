import SwiftUI

struct AirRightsOverlay: View {
    let profile: BuildingProfile

    @State private var pulseScale: CGFloat = 1.0
    @State private var pulseOpacity: Double = 0.3

    // Derived values
    private var airRightsSqft: Int { profile.airRightsSqft ?? 0 }

    private var unusedFar: Double { profile.unusedFar ?? 0 }

    private var builtFar: Double {
        guard let farStr = profile.far, let val = Double(farStr) else { return 1.0 }
        return max(val, 0.1) // avoid division by zero
    }

    private var builtStories: Int {
        guard let storiesStr = profile.stories, let val = Int(storiesStr) else { return 1 }
        return max(val, 1)
    }

    // How many additional floors the unused FAR would support
    private var additionalFloors: Int {
        let ratio = unusedFar / builtFar
        return max(Int(ratio * Double(builtStories)), 1)
    }

    // Ghost block height: proportional to unused/built FAR ratio, capped for usability
    private var ghostHeightRatio: CGFloat {
        let ratio = CGFloat(unusedFar / builtFar)
        return min(max(ratio, 0.15), 2.0) // at least 15% of reticle zone, max 2x
    }

    var body: some View {
        GeometryReader { geo in
            let screenH = geo.size.height
            let screenW = geo.size.width

            // Block dimensions: width ~55% of screen, height scaled by ratio
            let blockW: CGFloat = screenW * 0.55
            let baseBlockH: CGFloat = screenH * 0.18
            let blockH: CGFloat = baseBlockH * ghostHeightRatio

            // Position: above screen center (where the reticle lives)
            let centerX = screenW / 2
            let centerY = screenH / 2

            // Bottom of ghost sits at the reticle center; block grows upward
            ZStack(alignment: .topLeading) {
                // Pulsing glow halo behind the block
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color.green.opacity(0.12 * pulseOpacity / 0.3))
                    .frame(width: blockW + 24, height: blockH + 24)
                    .scaleEffect(pulseScale)
                    .position(x: centerX, y: centerY - blockH / 2)

                // Main ghost block
                ZStack {
                    // Fill
                    RoundedRectangle(cornerRadius: 6)
                        .fill(
                            LinearGradient(
                                colors: [
                                    Color.green.opacity(pulseOpacity),
                                    Color.cyan.opacity(pulseOpacity * 0.6)
                                ],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )

                    // Dashed border
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(
                            style: StrokeStyle(lineWidth: 1.5, dash: [6, 4])
                        )
                        .foregroundColor(.green.opacity(0.85))

                    // Labels
                    VStack(spacing: 4) {
                        // Header
                        Text("UNUSED AIR RIGHTS")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(.green)
                            .tracking(1.2)
                            .padding(.top, 8)

                        Spacer()

                        // Square footage — main number
                        Text(formatSqft(airRightsSqft))
                            .font(.system(size: 22, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)

                        Text("sq ft available")
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(.white.opacity(0.75))

                        Spacer()

                        // Additional floors
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.up.square.fill")
                                .font(.system(size: 11))
                                .foregroundColor(.cyan)
                            Text("+\(additionalFloors) potential floor\(additionalFloors == 1 ? "" : "s")")
                                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                                .foregroundColor(.cyan)
                        }
                        .padding(.bottom, 8)
                    }
                    .frame(maxWidth: .infinity)
                }
                .frame(width: blockW, height: blockH)
                .position(x: centerX, y: centerY - blockH / 2)

                // Vertical dashed line from block bottom down to reticle center
                Path { path in
                    path.move(to: CGPoint(x: centerX, y: centerY))
                    path.addLine(to: CGPoint(x: centerX, y: centerY + 16))
                }
                .stroke(
                    style: StrokeStyle(lineWidth: 1, dash: [3, 3])
                )
                .foregroundColor(.green.opacity(0.6))
            }
            .frame(width: screenW, height: screenH)
        }
        .onAppear { startPulse() }
    }

    // MARK: - Helpers

    private func startPulse() {
        withAnimation(
            .easeInOut(duration: 1.6)
            .repeatForever(autoreverses: true)
        ) {
            pulseScale = 1.04
            pulseOpacity = 0.45
        }
    }

    private func formatSqft(_ sqft: Int) -> String {
        if sqft >= 1_000_000 {
            return String(format: "%.1fM", Double(sqft) / 1_000_000)
        } else if sqft >= 1_000 {
            return String(format: "%.0fK", Double(sqft) / 1_000)
        }
        return "\(sqft)"
    }
}

// MARK: - Preview

#Preview {
    ZStack {
        Color.black.ignoresSafeArea()
        AirRightsOverlay(
            profile: BuildingProfile(
                yearBuilt: "1965",
                stories: "4",
                units: String?.none,
                residentialUnits: String?.none,
                lotArea: String?.none,
                buildingClass: String?.none,
                zoneDist: "R8",
                far: "1.2",
                maxFar: "6.5",
                landmark: String?.none,
                landmarkName: String?.none,
                architect: String?.none,
                architecturalStyle: String?.none,
                assessedLand: String?.none,
                assessedTotal: String?.none,
                taxClass: String?.none,
                latitude: Double?.none,
                longitude: Double?.none,
                ownerName: String?.none,
                airRightsSqft: 42500,
                unusedFar: 5.3,
                isTaxExempt: false,
                diplomaticStatus: DiplomaticStatus?.none
            )
        )
    }
}
