import SwiftUI
import AVFoundation

struct CameraPreview: UIViewControllerRepresentable {
    let session: AVCaptureSession

    func makeUIViewController(context: Context) -> PreviewViewController {
        let vc = PreviewViewController()
        vc.session = session
        return vc
    }

    func updateUIViewController(_ uiViewController: PreviewViewController, context: Context) {}

    class PreviewViewController: UIViewController {
        var session: AVCaptureSession?
        private var previewLayer: AVCaptureVideoPreviewLayer?

        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black

            guard let session else { return }
            let layer = AVCaptureVideoPreviewLayer(session: session)
            layer.videoGravity = .resizeAspectFill
            layer.frame = view.bounds
            view.layer.addSublayer(layer)
            previewLayer = layer
        }

        override func viewDidLayoutSubviews() {
            super.viewDidLayoutSubviews()
            previewLayer?.frame = view.bounds
        }
    }
}
