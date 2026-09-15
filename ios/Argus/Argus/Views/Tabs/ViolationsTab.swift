import SwiftUI

struct ViolationsTab: View {
    let violations: [Violation]

    var body: some View {
        if violations.isEmpty {
            VStack(spacing: 8) {
                Image(systemName: "checkmark.shield")
                    .font(.system(size: 32))
                    .foregroundColor(.green)
                Text("No violations on record")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 40)
        } else {
            VStack(spacing: 12) {
                ForEach(violations) { violation in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            SourceBadge(source: violation.source)

                            if let severity = violation.severity {
                                Text(severity)
                                    .font(.caption2)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(severityColor(severity).opacity(0.15))
                                    .foregroundColor(severityColor(severity))
                                    .cornerRadius(4)
                            }

                            Spacer()

                            if let date = violation.date {
                                Text(date)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }

                        Text(violation.description)
                            .font(.system(size: 14))
                            .lineLimit(3)

                        if let status = violation.status {
                            Text(status)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color(.systemGray6))
                    .cornerRadius(10)
                }
            }
        }
    }

    private func severityColor(_ severity: String) -> Color {
        switch severity.lowercased() {
        case "critical", "immediately hazardous": return .red
        case "major", "hazardous": return .orange
        case "minor", "non-hazardous": return .yellow
        default: return .secondary
        }
    }
}

struct SourceBadge: View {
    let source: String

    var body: some View {
        Text(source.uppercased())
            .font(.system(size: 10, weight: .bold, design: .monospaced))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(badgeColor.opacity(0.15))
            .foregroundColor(badgeColor)
            .cornerRadius(4)
    }

    private var badgeColor: Color {
        switch source.lowercased() {
        case "dob": return .blue
        case "hpd": return .orange
        case "ecb": return .red
        case "fdny": return .red
        default: return .secondary
        }
    }
}
