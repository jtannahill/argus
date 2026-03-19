import SwiftUI

struct CorrectionSheet: View {
    let wrongBuilding: BuildingCandidate
    let onCorrected: (BuildingCandidate?) -> Void

    @State private var searchText = ""
    @State private var results: [AddressResult] = []
    @State private var isSearching = false
    @State private var searchTask: Task<Void, Never>?
    @State private var flagReason = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Wrong building indicator
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Wrong building?")
                            .font(.system(size: 15, weight: .bold))
                        Text("Showing: \(wrongBuilding.address)")
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding()
                .background(Color.orange.opacity(0.1))

                // Search for correct building
                VStack(alignment: .leading, spacing: 8) {
                    Text("What building are you looking at?")
                        .font(.system(size: 14, weight: .semibold))
                        .padding(.horizontal)
                        .padding(.top, 12)

                    TextField("Type address...", text: $searchText)
                        .textFieldStyle(.roundedBorder)
                        .padding(.horizontal)
                        .onChange(of: searchText) { _, newValue in
                            searchTask?.cancel()
                            guard newValue.count >= 3 else {
                                results = []
                                return
                            }
                            searchTask = Task {
                                try? await Task.sleep(for: .milliseconds(400))
                                guard !Task.isCancelled else { return }
                                await search(query: newValue)
                            }
                        }
                }

                if isSearching {
                    ProgressView()
                        .padding()
                }

                // Results
                List(results) { result in
                    Button {
                        submitCorrection(correctAddress: result)
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(result.address)
                                .font(.system(size: 15, weight: .medium))
                                .foregroundColor(.primary)
                            HStack {
                                Text(result.borough ?? "")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                if let zip = result.zipCode {
                                    Text(zip)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                Text("BBL \(result.bbl)")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundColor(.green)
                            }
                        }
                    }
                }
                .listStyle(.plain)

                // Or just flag it without correction
                Button {
                    submitFlag()
                } label: {
                    HStack {
                        Image(systemName: "flag.fill")
                        Text("Just flag as wrong (no correction)")
                    }
                    .font(.system(size: 14))
                    .foregroundColor(.orange)
                    .padding()
                }
            }
            .navigationTitle("Report Error")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func search(query: String) async {
        isSearching = true
        do {
            await AuthManager.shared.ensureToken()
            results = try await ApiClient.shared.searchAddress(query: query)
        } catch {
            results = []
        }
        isSearching = false
    }

    private func submitCorrection(correctAddress: AddressResult) {
        // TODO: POST correction to API for training data
        // For now, just report back
        onCorrected(nil)
    }

    private func submitFlag() {
        // TODO: POST flag to API
        onCorrected(nil)
    }
}
