import SwiftUI
import CoreLocation

struct ScanView: View {
    @State private var camera = CameraManager()
    @State private var location = LocationManager()
    @State private var identifier = BuildingIdentifier()
    @State private var showSheet = false
    @State private var showAddressSearch = false
    @State private var radiusIndex = 1  // 0=nearby, 1=street, 2=block, 3=far
    @State private var showAirRights = false

    private let radiusOptions: [(label: String, meters: Double, icon: String)] = [
        ("Nearby", 30, "figure.walk"),
        ("Street", 100, "road.lanes"),
        ("Block", 300, "map"),
        ("Far", 800, "binoculars"),
    ]

    var body: some View {
        ZStack {
            CameraPreview(session: camera.session)
                .ignoresSafeArea()

            // Reticle — targeting crosshair at center
            ReticleView(
                isIdentifying: identifier.isIdentifying,
                hasResult: identifier.currentBuilding != nil,
                coneWidth: radiusOptions[radiusIndex].label
            )

            // Air rights ghost building overlay
            if showAirRights,
               let profile = identifier.currentBuilding?.profile,
               let airRights = profile.airRightsSqft, airRights > 0 {
                AirRightsOverlay(profile: profile)
                    .ignoresSafeArea()
                    .transition(.opacity)
                    .animation(.easeInOut(duration: 0.3), value: showAirRights)
            }

            VStack {
                // Top status
                HStack(spacing: 8) {
                    if identifier.isIdentifying {
                        HStack(spacing: 6) {
                            ProgressView()
                                .scaleEffect(0.7)
                                .tint(.white)
                            Text("IDENTIFYING...")
                                .font(.system(size: 13, weight: .bold, design: .monospaced))
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.green.opacity(0.85))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }

                    Spacer()

                    if location.hasLocation {
                        HStack(spacing: 4) {
                            Image(systemName: "location.fill")
                                .font(.caption2)
                            Text(String(format: "%.4f, %.4f", location.latitude, location.longitude))
                                .font(.system(size: 11, design: .monospaced))
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.black.opacity(0.6))
                        .foregroundColor(.green)
                        .cornerRadius(6)
                    }

                    // Address search button
                    Button {
                        showAddressSearch = true
                    } label: {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(width: 36, height: 36)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 60)

                Spacer()

                // Radius toggle + Refresh
                HStack(spacing: 12) {
                    // Radius picker
                    HStack(spacing: 0) {
                        ForEach(0..<radiusOptions.count, id: \.self) { i in
                            Button {
                                radiusIndex = i
                                // Re-identify with new radius
                                guard location.hasLocation else { return }
                                let loc = CLLocation(latitude: location.latitude, longitude: location.longitude)
                                Task {
                                    await identifier.identify(
                                        location: loc,
                                        heading: location.heading,
                                        radius: radiusOptions[i].meters,
                                        altitude: location.altitude,
                                        pitch: location.pitch,
                                        force: true
                                    )
                                }
                            } label: {
                                VStack(spacing: 2) {
                                    Image(systemName: radiusOptions[i].icon)
                                        .font(.system(size: 12))
                                    Text(radiusOptions[i].label)
                                        .font(.system(size: 9, weight: .medium))
                                }
                                .frame(width: 52, height: 40)
                                .foregroundColor(i == radiusIndex ? .white : .gray)
                                .background(i == radiusIndex ? Color.green.opacity(0.85) : Color.black.opacity(0.4))
                            }
                        }
                    }
                    .cornerRadius(8)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.white.opacity(0.2)))

                    Spacer()

                    // Air rights toggle button — only active when a building is identified
                    let hasAirRights = (identifier.currentBuilding?.profile?.airRightsSqft ?? 0) > 0
                    Button {
                        if hasAirRights {
                            withAnimation(.easeInOut(duration: 0.25)) {
                                showAirRights.toggle()
                            }
                        }
                    } label: {
                        VStack(spacing: 2) {
                            Image(systemName: showAirRights ? "building.fill" : "building")
                                .font(.system(size: 14, weight: .semibold))
                            Text("AIR")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                        }
                        .frame(width: 44, height: 44)
                        .foregroundColor(showAirRights ? .black : (hasAirRights ? .white : .gray))
                        .background(showAirRights ? Color.green : (hasAirRights ? Color.black.opacity(0.6) : Color.black.opacity(0.3)))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(showAirRights ? Color.green : Color.white.opacity(hasAirRights ? 0.3 : 0.1), lineWidth: 1)
                        )
                    }
                    .disabled(!hasAirRights)

                    // Refresh button
                    Button {
                        guard location.hasLocation else { return }
                        let loc = CLLocation(latitude: location.latitude, longitude: location.longitude)
                        Task {
                            await identifier.identify(
                                location: loc,
                                heading: location.heading,
                                radius: radiusOptions[radiusIndex].meters,
                                altitude: location.altitude,
                                pitch: location.pitch,
                                force: true
                            )
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(.white)
                            .frame(width: 44, height: 44)
                            .background(Color.green.opacity(0.85))
                            .clipShape(Circle())
                    }
                }
                .padding(.horizontal, 16)

                // Error display
                if let err = identifier.error {
                    Text(err)
                        .font(.caption2)
                        .padding(6)
                        .background(Color.red.opacity(0.9))
                        .foregroundColor(.white)
                        .cornerRadius(6)
                        .padding(.horizontal)
                }

                // Bottom status bar
                if let building = identifier.currentBuilding {
                    Button {
                        showSheet = true
                    } label: {
                        HStack {
                            Image(systemName: "building.2.fill")
                                .foregroundColor(.green)
                            Text(building.address)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(.white)
                                .lineLimit(1)
                            Spacer()
                            Image(systemName: "chevron.up")
                                .foregroundColor(.gray)
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(Color.black.opacity(0.8))
                        .cornerRadius(12)
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
                }
            }
        }
        .onAppear {
            Task { await AuthManager.shared.ensureToken() }
            camera.setup()
            location.start()
        }
        .onDisappear {
            camera.stop()
            location.stop()
        }
        .onChange(of: location.latitude) { _, _ in
            guard location.hasLocation else { return }
            let loc = CLLocation(latitude: location.latitude, longitude: location.longitude)
            Task {
                await identifier.identify(
                    location: loc,
                    heading: location.heading,
                    radius: radiusOptions[radiusIndex].meters,
                    altitude: location.altitude,
                    pitch: location.pitch
                )
            }
        }
        .onChange(of: identifier.currentBuilding?.bbl) { _, newValue in
            if newValue != nil {
                showSheet = true
            }
            // Auto-dismiss air rights overlay if new building has no air rights data
            if showAirRights {
                let hasAirRights = (identifier.currentBuilding?.profile?.airRightsSqft ?? 0) > 0
                if !hasAirRights {
                    withAnimation(.easeInOut(duration: 0.25)) { showAirRights = false }
                }
            }
        }
        .sheet(isPresented: $showSheet) {
            if let building = identifier.currentBuilding {
                BuildingSheet(building: building)
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
            }
        }
        .sheet(isPresented: $showAddressSearch) {
            AddressSearchView()
        }
        .onChange(of: showSheet) { _, isShowing in
            if isShowing {
                camera.stop()
            } else {
                camera.setup()
            }
        }
    }
}
