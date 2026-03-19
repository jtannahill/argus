import SwiftUI

struct CaptureView: View {
    @State private var camera = CameraManager()
    @State private var detector = PlateDetector()
    @State private var mode: Capture.CaptureMode = .drive
    @State private var showConfirmation = false
    @State private var lastPlate = ""

    var body: some View {
        ZStack {
            CameraPreview(session: camera.session)
                .ignoresSafeArea()

            VStack {
                // Debug info
                if let error = camera.errorMessage {
                    Text(error)
                        .font(.caption)
                        .padding(8)
                        .background(Color.red.opacity(0.9))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                } else if !camera.isRunning {
                    Text("Starting camera...")
                        .font(.caption)
                        .padding(8)
                        .background(Color.orange.opacity(0.9))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }

                HStack(spacing: 12) {
                    ForEach(["drive", "point", "watch"], id: \.self) { m in
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

                if showConfirmation {
                    Text(lastPlate)
                        .font(.system(size: 24, weight: .bold, design: .monospaced))
                        .padding()
                        .background(Color.green.opacity(0.9))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                        .transition(.move(edge: .bottom))
                }
            }
            .padding(.top, 60)
        }
        .onAppear {
            camera.setup()
            let det = detector
            camera.onFrame = { buffer in
                det.processFrame(buffer)
            }
        }
        .onDisappear { camera.stop() }
        .onChange(of: detector.lastDetectedPlate) { oldValue, newValue in
            guard let plate = newValue else { return }
            lastPlate = plate
            showConfirmation = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                showConfirmation = false
            }
        }
    }
}
