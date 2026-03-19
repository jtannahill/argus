import SwiftUI

struct OwnerTab: View {
    let records: [OwnershipRecord]

    var body: some View {
        if records.isEmpty {
            VStack(spacing: 8) {
                Image(systemName: "person.2")
                    .font(.system(size: 32))
                    .foregroundColor(.secondary)
                Text("No ownership records")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 40)
        } else {
            VStack(spacing: 12) {
                ForEach(records) { record in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(record.name)
                            .font(.system(size: 15, weight: .semibold))

                        HStack(spacing: 12) {
                            Text(record.type)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color.blue.opacity(0.15))
                                .foregroundColor(.blue)
                                .cornerRadius(4)

                            if let pct = record.percentage {
                                Text(String(format: "%.0f%%", pct))
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }

                            if let since = record.since {
                                Text("Since \(since)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
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
