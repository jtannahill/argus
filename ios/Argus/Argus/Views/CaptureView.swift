import SwiftUI

struct CaptureView: View {
    @StateObject private var camera = CameraManager()
    @StateObject private var detector = PlateDetector()
    @State private var mode: Capture.CaptureMode = .drive
    @State private var showConfirmation = false
    @State private var lastPlate = ""

    var body: some View {
        ZStack {
            CameraPreview(session: camera.session)
                .ignoresSafeArea()

            VStack {
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
                .padding(.top, 60)

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
        }
        .onAppear {
            camera.setup()
            camera.onFrame = { [weak detector] buffer in
                detector?.processFrame(buffer)
            }
        }
        .onDisappear { camera.stop() }
        .onChange(of: detector.lastDetectedPlate) { _, plate in
            guard let plate else { return }
            lastPlate = plate
            showConfirmation = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                showConfirmation = false
            }
        }
    }
}
