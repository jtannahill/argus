import SwiftUI
import MapKit

struct ExploreMapView: View {
    @State private var position: MapCameraPosition = .userLocation(fallback: .automatic)
    @State private var selectedBuilding: BuildingCandidate?
    @State private var showSheet = false

    // TODO: Populate from local storage / API
    @State private var scannedBuildings: [BuildingCandidate] = []

    var body: some View {
        Map(position: $position) {
            UserAnnotation()

            ForEach(scannedBuildings) { building in
                if let profile = building.profile,
                   let lat = profile.latitude,
                   let lon = profile.longitude {
                    Annotation(building.address, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon)) {
                        Button {
                            selectedBuilding = building
                            showSheet = true
                        } label: {
                            Image(systemName: "building.2.fill")
                                .font(.system(size: 16))
                                .foregroundColor(.white)
                                .padding(8)
                                .background(pinColor(for: building))
                                .clipShape(Circle())
                                .shadow(radius: 3)
                        }
                    }
                }
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .mapControls {
            MapUserLocationButton()
            MapCompass()
            MapScaleView()
        }
        .sheet(isPresented: $showSheet) {
            if let building = selectedBuilding {
                BuildingSheet(building: building)
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
            }
        }
    }

    private func pinColor(for building: BuildingCandidate) -> Color {
        if let lm = building.profile?.landmark, !lm.isEmpty, lm != "N" {
            return .yellow
        }
        return .green
    }
}
