import SwiftUI
import UIKit
import CoreLocation

struct ShareableSnapshot: View {
    let building: BuildingCandidate
    let userLocation: CLLocationCoordinate2D?
    let heading: Double?
    let distance: Double?
    let mode: String

    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            HStack {
                Image(systemName: "viewfinder")
                    .foregroundColor(.green)
                Text("ARGUS")
                    .font(.system(size: 14, weight: .black, design: .monospaced))
                    .foregroundColor(.green)
                Spacer()
                Text(Date().formatted(date: .abbreviated, time: .shortened))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.gray)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color.black)

            // Building info
            VStack(alignment: .leading, spacing: 12) {
                // Address + BBL
                VStack(alignment: .leading, spacing: 4) {
                    Text(building.address)
                        .font(.system(size: 22, weight: .bold))
                        .foregroundColor(.white)
                    Text("BBL \(building.bbl)")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.gray)
                }

                // Profile grid
                if let profile = building.profile {
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible()),
                        GridItem(.flexible()),
                    ], spacing: 8) {
                        if let year = profile.yearBuilt, !year.isEmpty {
                            metricCell(label: "BUILT", value: year)
                        }
                        if let stories = profile.stories, !stories.isEmpty {
                            metricCell(label: "FLOORS", value: stories.components(separatedBy: ".").first ?? stories)
                        }
                        if let units = profile.units, !units.isEmpty {
                            metricCell(label: "UNITS", value: units)
                        }
                        if let zone = profile.zoneDist, !zone.isEmpty {
                            metricCell(label: "ZONE", value: zone)
                        }
                        if let cls = profile.buildingClass, !cls.isEmpty {
                            metricCell(label: "CLASS", value: cls)
                        }
                        if let d = distance {
                            metricCell(label: "DIST", value: d < 1000 ? "\(Int(d))m" : String(format: "%.1fmi", d / 1609.34))
                        }
                    }

                    // Owner
                    if let owner = profile.ownerName, !owner.isEmpty {
                        HStack(spacing: 6) {
                            Image(systemName: "person.fill")
                                .font(.caption2)
                                .foregroundColor(.green)
                            Text(owner)
                                .font(.system(size: 13))
                                .foregroundColor(.white)
                        }
                    }

                    // Landmark
                    if let lm = profile.landmark, !lm.isEmpty, lm != "N" {
                        HStack(spacing: 6) {
                            Image(systemName: "star.fill")
                                .font(.caption2)
                                .foregroundColor(.yellow)
                            Text(lm)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(.yellow)
                        }
                    }

                    // Diplomatic
                    if let diplo = profile.diplomaticStatus, diplo.isDiplomatic == true {
                        HStack(spacing: 6) {
                            Image(systemName: "flag.fill")
                                .font(.caption2)
                                .foregroundColor(.red)
                            Text("DIPLOMATIC PROPERTY")
                                .font(.system(size: 12, weight: .bold))
                                .foregroundColor(.red)
                        }
                    }

                    // Air rights
                    if let air = profile.airRightsSqft, air > 0 {
                        HStack(spacing: 6) {
                            Image(systemName: "arrow.up.square")
                                .font(.caption2)
                                .foregroundColor(.cyan)
                            Text("\(air.formatted()) sq ft unused air rights")
                                .font(.system(size: 12))
                                .foregroundColor(.cyan)
                        }
                    }

                    // Value
                    if let total = profile.assessedTotal, let num = Double(total), num > 0 {
                        HStack(spacing: 6) {
                            Image(systemName: "dollarsign.circle")
                                .font(.caption2)
                                .foregroundColor(.green)
                            Text("Assessed: $\(Int(num).formatted())")
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundColor(.green)
                        }
                    }
                }

                // Story headline
                if let story = building.story, let headline = story.headline, !headline.isEmpty {
                    Text(headline)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.white.opacity(0.8))
                        .italic()
                        .padding(.top, 4)
                }
            }
            .padding(16)
            .background(Color(white: 0.1))

            // Footer with coordinates
            HStack(spacing: 16) {
                if let loc = userLocation {
                    Text(String(format: "%.5f, %.5f", loc.latitude, loc.longitude))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.gray)
                }
                if let h = heading {
                    Text(String(format: "%.0f°", h))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.gray)
                }
                Spacer()
                Text(mode.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(.green)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.black)
        }
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.green.opacity(0.3)))
    }

    private func metricCell(label: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundColor(.gray)
            Text(value)
                .font(.system(size: 15, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color(white: 0.15))
        .cornerRadius(6)
    }
}


// MARK: - Renderer

@MainActor
func renderSnapshot(building: BuildingCandidate, userLocation: CLLocationCoordinate2D?, heading: Double?, distance: Double?, mode: String) -> UIImage? {
    let view = ShareableSnapshot(
        building: building,
        userLocation: userLocation,
        heading: heading,
        distance: distance,
        mode: mode
    )
    let controller = UIHostingController(rootView: view.frame(width: 380))
    controller.view.backgroundColor = .clear

    let size = controller.sizeThatFits(in: CGSize(width: 380, height: UIView.layoutFittingExpandedSize.height))
    controller.view.frame = CGRect(origin: .zero, size: size)
    controller.view.layoutIfNeeded()

    let renderer = UIGraphicsImageRenderer(size: size)
    return renderer.image { _ in
        controller.view.drawHierarchy(in: controller.view.bounds, afterScreenUpdates: true)
    }
}
