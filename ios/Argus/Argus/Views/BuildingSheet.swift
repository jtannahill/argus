import SwiftUI

enum BuildingTab: String, CaseIterable {
    case story = "Story"
    case owner = "Owner"
    case value = "Value"
    case violations = "Violations"
    case permits = "Permits"

    var icon: String {
        switch self {
        case .story: return "book.fill"
        case .owner: return "person.2.fill"
        case .value: return "dollarsign.circle.fill"
        case .violations: return "exclamationmark.triangle.fill"
        case .permits: return "doc.text.fill"
        }
    }
}

struct BuildingSheet: View {
    let building: BuildingCandidate
    @State private var selectedTab: BuildingTab = .story
    @State private var detail: BuildingDetail?
    @State private var isLoading = false
    @State private var isPinned = false
    @State private var isPinning = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top) {
                    Text(building.address)
                        .font(.system(size: 20, weight: .bold))
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Button {
                        Task { await togglePin() }
                    } label: {
                        Image(systemName: isPinned ? "mappin.circle.fill" : "mappin.circle")
                            .font(.system(size: 26))
                            .foregroundColor(isPinned ? .green : .secondary)
                            .opacity(isPinning ? 0.5 : 1.0)
                    }
                    .disabled(isPinning)
                    .accessibilityLabel(isPinned ? "Unpin building" : "Pin building")
                }

                HStack(spacing: 10) {
                    if let profile = building.profile ?? detail?.profile {
                        if let lm = profile.landmark, !lm.isEmpty, lm != "N" {
                            Label(profile.landmarkName ?? "Landmark", systemImage: "star.fill")
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color.yellow.opacity(0.2))
                                .foregroundColor(.yellow)
                                .cornerRadius(4)
                        }
                        if let year = profile.yearBuilt, !year.isEmpty {
                            Text("Built \(year)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        if let stories = profile.stories, !stories.isEmpty {
                            Text("\(stories) floors")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                Text("BBL: \(building.bbl)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 12)

            // Tab bar
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 4) {
                    ForEach(BuildingTab.allCases, id: \.self) { tab in
                        TabButton(
                            title: tab.rawValue,
                            icon: tab.icon,
                            isSelected: selectedTab == tab
                        ) {
                            selectedTab = tab
                        }
                    }
                }
                .padding(.horizontal, 12)
            }
            .padding(.vertical, 8)
            .background(Color(.systemGray6))

            // Tab content
            ScrollView {
                Group {
                    switch selectedTab {
                    case .story:
                        StoryTab(story: detail?.story ?? building.story)
                    case .owner:
                        OwnerTab(records: detail?.ownership ?? [])
                    case .value:
                        ValueTab(profile: detail?.profile ?? building.profile)
                    case .violations:
                        ViolationsTab(violations: detail?.violations ?? [])
                    case .permits:
                        PermitsTab(permits: detail?.permits ?? [])
                    }
                }
                .padding(16)
            }
        }
        .task {
            await loadDetail()
        }
    }

    private func loadDetail() async {
        guard detail == nil else { return }
        isLoading = true
        do {
            await AuthManager.shared.ensureToken()
            detail = try await ApiClient.shared.getBuilding(bbl: building.bbl)
        } catch {
            // Detail load failed — show what we have from candidates
        }
        isLoading = false
    }
}

struct TabButton: View {
    let title: String
    let icon: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                Text(title)
                    .font(.system(size: 13, weight: isSelected ? .semibold : .regular))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(isSelected ? Color.green.opacity(0.15) : Color.clear)
            .foregroundColor(isSelected ? .green : .secondary)
            .cornerRadius(8)
        }
    }
}
