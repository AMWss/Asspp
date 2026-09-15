//
//  AppDelegate+iOS.swift
//  Asspp
//

#if canImport(UIKit)
    import Combine
    import UIKit

    class AppDelegate: NSObject, UIApplicationDelegate {
        private var downloadCountSubscription: AnyCancellable?

        var backgroundTaskIdentifier: UIBackgroundTaskIdentifier = .invalid

        func application(
            _: UIApplication,
            didFinishLaunchingWithOptions _: [UIApplication.LaunchOptionsKey: Any]? = nil,
        ) -> Bool {
            Task { @MainActor in
                self.observeDownloadCount()
            }
            return true
        }

        @MainActor
        private func observeDownloadCount() {
            downloadCountSubscription = Downloads.this.$runningTaskCount
                .removeDuplicates()
                .receive(on: DispatchQueue.main)
                .sink { count in
                    UIApplication.shared.isIdleTimerDisabled = count > 0
                    BackgroundAudioPlayer.shared.setActive(count > 0)
                }
        }

        func applicationWillResignActive(_: UIApplication) {
            guard Downloads.this.runningTaskCount > 0 else { return }
            let task = UIApplication.shared.beginBackgroundTask(withName: "Downloads") {
                UIApplication.shared.endBackgroundTask(self.backgroundTaskIdentifier)
                self.backgroundTaskIdentifier = .invalid
            }
            backgroundTaskIdentifier = task
        }

        func applicationWillEnterForeground(_: UIApplication) {
            guard backgroundTaskIdentifier != .invalid else { return }
            UIApplication.shared.endBackgroundTask(backgroundTaskIdentifier)
            backgroundTaskIdentifier = .invalid
        }
    }
#endif
