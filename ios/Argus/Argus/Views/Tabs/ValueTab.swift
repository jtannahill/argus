import SwiftUI

struct ValueTab: View {
    let profile: BuildingProfile?

    var body: some View {
        if let profile {
            VStack(alignment: .leading, spacing: 16) {
                // Assessed Values
                VStack(alignment: .leading, spacing: 8) {
                    Text("Assessed Value")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.green)

                    if let total = profile.assessedTotal {
                        HStack {
                            Text("Total")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(formatCurrency(total))
                                .font(.system(size: 16, weight: .bold, design: .monospaced))
                        }
                    }

                    if let land = profile.assessedLand {
                        HStack {
                            Text("Land")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(formatCurrency(land))
                                .font(.system(size: 16, weight: .bold, design: .monospaced))
                        }
                    }

                    if let taxClass = profile.taxClass {
                        HStack {
                            Text("Tax Class")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(taxClass)
                                .font(.system(size: 14, weight: .medium))
                        }
                    }
                }
                .padding(12)
                .background(Color(.systemGray6))
                .cornerRadius(10)

                // Zoning
                VStack(alignment: .leading, spacing: 8) {
                    Text("Zoning")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.green)

                    if let zone = profile.zoneDist {
                        HStack {
                            Text("District")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(zone)
                                .font(.system(size: 14, weight: .medium))
                        }
                    }

                    if let far = profile.far {
                        HStack {
                            Text("FAR (Used)")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(String(format: "%.2f", far))
                                .font(.system(size: 14, design: .monospaced))
                        }
                    }

                    if let maxFar = profile.maxFar {
                        HStack {
                            Text("FAR (Max)")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(String(format: "%.2f", maxFar))
                                .font(.system(size: 14, design: .monospaced))
                        }
                    }

                    if let lot = profile.lotArea {
                        HStack {
                            Text("Lot Area")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("\(lot.formatted()) sq ft")
                                .font(.system(size: 14, design: .monospaced))
                        }
                    }
                }
                .padding(12)
                .background(Color(.systemGray6))
                .cornerRadius(10)

                // Building Details
                VStack(alignment: .leading, spacing: 8) {
                    Text("Building")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.green)

                    if let cls = profile.buildingClass {
                        HStack {
                            Text("Class")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(cls)
                                .font(.system(size: 14, weight: .medium))
                        }
                    }

                    if let style = profile.architecturalStyle {
                        HStack {
                            Text("Style")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(style)
                                .font(.system(size: 14, weight: .medium))
                        }
                    }

                    if let architect = profile.architect {
                        HStack {
                            Text("Architect")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(architect)
                                .font(.system(size: 14, weight: .medium))
                        }
                    }
                }
                .padding(12)
                .background(Color(.systemGray6))
                .cornerRadius(10)
            }
        } else {
            VStack(spacing: 8) {
                Image(systemName: "dollarsign.circle")
                    .font(.system(size: 32))
                    .foregroundColor(.secondary)
                Text("No valuation data")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 40)
        }
    }

    private func formatCurrency(_ value: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$\(value)"
    }
}
