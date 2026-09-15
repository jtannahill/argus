import SwiftUI

struct ReticleView: View {
    let isIdentifying: Bool
    let hasResult: Bool
    let coneWidth: String
    var distance: Double? = nil  // meters to identified building

    private var ringColor: Color {
        if hasResult { return .green }
        if isIdentifying { return .yellow }
        return .white.opacity(0.5)
    }

    // Reticle size shrinks as cone narrows (visual feedback for precision)
    private var ringSize: CGFloat {
        switch coneWidth {
        case "Nearby": return 120
        case "Street": return 90
        case "Block": return 60
        case "Far": return 40
        case "Skyline": return 24
        default: return 90
        }
    }

    var body: some View {
        ZStack {
            // Outer ring
            Circle()
                .stroke(ringColor, lineWidth: hasResult ? 2.5 : 1.5)
                .frame(width: ringSize, height: ringSize)
                .animation(.easeInOut(duration: 0.3), value: ringSize)
                .animation(.easeInOut(duration: 0.2), value: hasResult)

            // Crosshair lines
            Group {
                Rectangle()
                    .fill(ringColor)
                    .frame(width: 1, height: ringSize * 0.3)
                    .offset(y: -(ringSize * 0.5 + ringSize * 0.15))

                Rectangle()
                    .fill(ringColor)
                    .frame(width: 1, height: ringSize * 0.3)
                    .offset(y: ringSize * 0.5 + ringSize * 0.15)

                Rectangle()
                    .fill(ringColor)
                    .frame(width: ringSize * 0.3, height: 1)
                    .offset(x: -(ringSize * 0.5 + ringSize * 0.15))

                Rectangle()
                    .fill(ringColor)
                    .frame(width: ringSize * 0.3, height: 1)
                    .offset(x: ringSize * 0.5 + ringSize * 0.15)
            }

            // Center dot
            Circle()
                .fill(ringColor)
                .frame(width: 4, height: 4)

            // Pulse animation when identifying
            if isIdentifying {
                Circle()
                    .stroke(Color.yellow.opacity(0.4), lineWidth: 1)
                    .frame(width: ringSize + 20, height: ringSize + 20)
                    .scaleEffect(isIdentifying ? 1.3 : 1.0)
                    .opacity(isIdentifying ? 0.0 : 0.6)
                    .animation(
                        .easeOut(duration: 1.2).repeatForever(autoreverses: false),
                        value: isIdentifying
                    )
            }

            // Mode + distance labels below reticle
            VStack(spacing: 2) {
                Text(coneWidth.uppercased())
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundColor(ringColor)

                if let dist = distance, dist > 0 {
                    Text(formatDistance(dist))
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundColor(.white)
                }
            }
            .offset(y: ringSize * 0.5 + ringSize * 0.15 + 20)
        }
    }

    private func formatDistance(_ meters: Double) -> String {
        if meters < 1000 {
            return "\(Int(meters))m"
        } else {
            let miles = meters / 1609.34
            return String(format: "%.1f mi", miles)
        }
    }
}
