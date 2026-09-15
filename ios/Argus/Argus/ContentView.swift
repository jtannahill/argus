//
//  ContentView.swift
//  Argus
//
//  Created by James T on 3/19/26.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            ScanView()
                .tabItem {
                    Label("Scan", systemImage: "camera.viewfinder")
                }

            ExploreMapView()
                .tabItem {
                    Label("Explore", systemImage: "map")
                }
        }
        .tint(.green)
    }
}

#Preview {
    ContentView()
}
