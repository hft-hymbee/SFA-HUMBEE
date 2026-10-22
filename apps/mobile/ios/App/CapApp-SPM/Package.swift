// swift-tools-version: 5.9
import PackageDescription

// DO NOT MODIFY THIS FILE - managed by Capacitor CLI commands
let package = Package(
    name: "CapApp-SPM",
    platforms: [.iOS(.v15)],
    products: [
        .library(
            name: "CapApp-SPM",
            targets: ["CapApp-SPM"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", exact: "8.5.0"),
        .package(name: "CapacitorApp", path: "..\..\..\..\..\node_modules\.pnpm\@capacitor+app@8.1.1_patch__f1a6f1802d9c14a001e7a231648bc93c\node_modules\@capacitor\app"),
        .package(name: "CapacitorGeolocation", path: "..\..\..\..\..\node_modules\.pnpm\@capacitor+geolocation@8.2.2_@capacitor+core@8.5.0\node_modules\@capacitor\geolocation")
    ],
    targets: [
        .target(
            name: "CapApp-SPM",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm"),
                .product(name: "CapacitorApp", package: "CapacitorApp"),
                .product(name: "CapacitorGeolocation", package: "CapacitorGeolocation")
            ]
        )
    ]
)
