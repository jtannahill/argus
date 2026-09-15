import SwiftUI

struct PermitsTab: View {
    let permits: [Permit]

    var body: some View {
        if permits.isEmpty {
            VStack(spacing: 8) {
                Image(systemName: "doc.text")
                    .font(.system(size: 32))
                    .foregroundColor(.secondary)
                Text("No permits on record")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 40)
        } else {
            VStack(spacing: 12) {
                ForEach(permits) { permit in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(permit.type)
                                .font(.system(size: 12, weight: .bold))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color.blue.opacity(0.15))
                                .foregroundColor(.blue)
                                .cornerRadius(4)

                            Spacer()

                            if let date = permit.date {
                                Text(date)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }

                        Text(permit.description)
                            .font(.system(size: 14))
                            .lineLimit(3)

                        HStack {
                            Text("Job #\(permit.jobNumber)")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundColor(.secondary)

                            if let status = permit.status {
                                Spacer()
                                Text(status)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }

                        if let applicant = permit.applicant {
                            Text("Filed by: \(applicant)")
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
}
