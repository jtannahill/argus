import CoreLocation
import CoreMotion
import Observation

@Observable
class LocationManager: NSObject, CLLocationManagerDelegate {
    var latitude: Double = 0
    var longitude: Double = 0
    var heading: CLLocationDirection = 0
    var altitude: Double = 0
    var pitch: Double = 0  // degrees: 0 = horizontal, -90 = pointing straight down
    var hasLocation = false

    private let manager = CLLocationManager()
    private let motionManager = CMMotionManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = 5
    }

    func start() {
        manager.requestWhenInUseAuthorization()
        manager.startUpdatingLocation()
        if CLLocationManager.headingAvailable() {
            manager.startUpdatingHeading()
        }

        if motionManager.isDeviceMotionAvailable {
            motionManager.deviceMotionUpdateInterval = 0.1
            motionManager.startDeviceMotionUpdates(to: .main) { [weak self] motion, _ in
                guard let self, let motion else { return }
                // attitude.pitch: 0 = flat on table, +π/2 = face up vertical, -π/2 = face down
                // Convert so that 0 = horizontal hold (portrait, aimed at horizon),
                // negative = pointing downward toward ground.
                // When held portrait pointing at a building: pitch ≈ 0°
                // When tilted to look down: pitch goes negative.
                let pitchDeg = motion.attitude.pitch * (180.0 / .pi)
                // CMAttitude pitch is measured from horizontal; subtract 90° to get
                // our convention where 0 = camera aimed at horizon.
                self.pitch = pitchDeg - 90.0
            }
        }
    }

    func stop() {
        manager.stopUpdatingLocation()
        manager.stopUpdatingHeading()
        motionManager.stopDeviceMotionUpdates()
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        Task { @MainActor in
            self.latitude = loc.coordinate.latitude
            self.longitude = loc.coordinate.longitude
            self.altitude = loc.altitude
            self.hasLocation = true
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        let h = newHeading.trueHeading >= 0 ? newHeading.trueHeading : newHeading.magneticHeading
        Task { @MainActor in
            self.heading = h
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // GPS errors are non-fatal — just keep trying
    }
}
