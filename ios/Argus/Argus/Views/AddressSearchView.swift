import SwiftUI

@Observable
final class AddressSearchViewModel {
    var query: String = ""
    var results: [AddressResult] = []
    var isLoading: Bool = false
    var error: String? = nil

    private var debounceTask: Task<Void, Never>? = nil

    func onQueryChanged(_ newValue: String) {
        debounceTask?.cancel()
        results = []
        error = nil

        let trimmed = newValue.trimmingCharacters(in: .whitespaces)
        guard trimmed.count >= 3 else { return }

        debounceTask = Task {
            try? await Task.sleep(for: .milliseconds(500))
            guard !Task.isCancelled else { return }
            await search(query: trimmed)
        }
    }

    @MainActor
    private func search(query: String) async {
        isLoading = true
        error = nil
        do {
            results = try await ApiClient.shared.searchAddress(query: query)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
}

struct AddressSearchView: View {
    @State private var viewModel = AddressSearchViewModel()
    @State private var selectedBuilding: BuildingCandidate? = nil
    @State private var showBuildingSheet = false
    @State private var identifyError: String? = nil
    @State private var isIdentifying = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search field
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("Search address...", text: $viewModel.query)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.words)
                        .submitLabel(.search)
                }
                .padding(12)
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

                Divider()

                // Results / states
                if viewModel.isLoading || isIdentifying {
                    Spacer()
                    ProgressView(isIdentifying ? "Identifying building..." : "Searching...")
                        .padding()
                    Spacer()
                } else if let err = viewModel.error ?? identifyError {
                    Spacer()
                    VStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.title2)
                            .foregroundColor(.red)
                        Text(err)
                            .font(.callout)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    Spacer()
                } else if viewModel.results.isEmpty && viewModel.query.count >= 3 {
                    Spacer()
                    Text("No results found")
                        .foregroundColor(.secondary)
                    Spacer()
                } else {
                    List(viewModel.results) { result in
                        Button {
                            Task { await identify(result: result) }
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(result.address)
                                    .font(.body)
                                    .foregroundColor(.primary)
                                if let borough = result.borough {
                                    Text(borough)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Address Search")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .onChange(of: viewModel.query) { _, newValue in
            viewModel.onQueryChanged(newValue)
        }
        .sheet(isPresented: $showBuildingSheet) {
            if let building = selectedBuilding {
                BuildingSheet(building: building)
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
            }
        }
    }

    private func identify(result: AddressResult) async {
        guard let lat = result.latitude, let lon = result.longitude else {
            identifyError = "No coordinates available for this address"
            return
        }
        isIdentifying = true
        identifyError = nil
        do {
            let response = try await ApiClient.shared.identify(
                latitude: lat,
                longitude: lon,
                heading: 0
            )
            if let first = response.candidates.first {
                selectedBuilding = first
                showBuildingSheet = true
            } else {
                identifyError = "No building found at this address"
            }
        } catch {
            identifyError = error.localizedDescription
        }
        isIdentifying = false
    }
}
