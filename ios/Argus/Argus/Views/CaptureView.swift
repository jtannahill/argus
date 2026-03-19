import SwiftUI

struct CaptureView: View {
    @State private var camera = CameraManager()
    @State private var detector = PlateDetector()
    @State private var location = LocationManager()
    @State private var mode: Capture.CaptureMode = .scan
    @State private var showConfirmation = false
    @State private var lastPlate = ""
    @State private var captureCount = 0
    @State private var recentPlates: Set<String> = []

    var body: some View {
        ZStack {
            CameraPreview(session: camera.session)
                .ignoresSafeArea()

            // Yellow bounding box
            GeometryReader { geo in
                if let box = detector.smoothedBox {
                    let rect = convertBoundingBox(box, in: geo.size)
                    Rectangle()
                        .stroke(Color.yellow, lineWidth: 3)
                        .frame(width: rect.width, height: rect.height)
                        .position(x: rect.midX, y: rect.midY)

                    if let plate = detector.lastDetectedPlate {
                        Text(plate)
                            .font(.system(size: 14, weight: .bold, design: .monospaced))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.yellow)
                            .foregroundColor(.black)
                            .cornerRadius(4)
                            .position(x: rect.midX, y: rect.minY - 16)
                    }
                }
            }
            .animation(.easeOut(duration: 0.15), value: detector.smoothedBox?.origin.x)
            .ignoresSafeArea()

            VStack {
                if let error = camera.errorMessage {
                    Text(error)
                        .font(.caption)
                        .padding(8)
                        .background(Color.red.opacity(0.9))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }

                HStack(spacing: 12) {
                    ForEach(["scan", "point", "sweep"], id: \.self) { m in
                        Button(m.capitalized) {
                            mode = Capture.CaptureMode(rawValue: m)!
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(mode.rawValue == m ? Color.green : Color.gray.opacity(0.7))
                        .foregroundColor(.white)
                        .cornerRadius(20)
                    }
                }
                .padding(.top, 20)

                Spacer()

                // Status bar
                HStack {
                    if location.hasLocation {
                        Image(systemName: "location.fill")
                            .foregroundColor(.green)
                            .font(.caption)
                    }
                    Text("\(captureCount) captured")
                        .font(.caption)
                        .foregroundColor(.gray)
                    if OfflineQueue.shared.pendingCount > 0 {
                        Text("• \(OfflineQueue.shared.pendingCount) pending")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
                .padding(.bottom, 8)

                if showConfirmation {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.white)
                        Text(lastPlate)
                            .font(.system(size: 20, weight: .bold, design: .monospaced))
                    }
                    .padding()
                    .background(Color.green.opacity(0.9))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                    .transition(.move(edge: .bottom))
                    .padding(.bottom, 40)
                }
            }
            .padding(.top, 60)
        }
        .onAppear {
            // Auth + camera + GPS
            Task { await AuthManager.shared.ensureToken() }
            camera.setup()
            location.start()

            let det = detector
            camera.onFrame = { buffer in
                det.processFrame(buffer)
            }
        }
        .onDisappear {
            camera.stop()
            location.stop()
        }
        .onChange(of: detector.lastDetectedPlate) { oldValue, newValue in
            guard let plate = newValue else { return }

            // In Scan mode: auto-capture unique plates
            // In Point mode: just show detection, user taps to capture (TODO)
            // In Sweep mode: capture everything including repeats
            let shouldCapture: Bool
            switch mode {
            case .scan:
                shouldCapture = !recentPlates.contains(plate)
            case .point:
                shouldCapture = false // TODO: tap to capture
            case .sweep:
                shouldCapture = true
            }

            if shouldCapture {
                captureAndUpload(plate: plate)
                recentPlates.insert(plate)
                // Clear recent plates after 5 minutes to allow re-capture
                DispatchQueue.main.asyncAfter(deadline: .now() + 300) {
                    recentPlates.remove(plate)
                }
            }

            lastPlate = plate
            showConfirmation = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                showConfirmation = false
            }
        }
    }

    private func captureAndUpload(plate: String) {
        guard let vehicleData = detector.lastVehicleFrame,
              let plateData = detector.lastPlateFrame else { return }

        let capture = Capture(
            id: UUID(),
            plate: plate,
            confidence: detector.lastConfidence,
            latitude: location.latitude,
            longitude: location.longitude,
            timestamp: Date(),
            mode: mode
        )

        captureCount += 1
        OfflineQueue.shared.enqueue(capture: capture, plateImage: plateData, vehicleImage: vehicleData)
    }

    private func convertBoundingBox(_ box: CGRect, in size: CGSize) -> CGRect {
        let x = box.origin.x * size.width
        let y = (1 - box.origin.y - box.height) * size.height
        let w = box.width * size.width
        let h = box.height * size.height
        return CGRect(x: x, y: y, width: w, height: h)
    }
}
