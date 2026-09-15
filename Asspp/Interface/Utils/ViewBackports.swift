//
//  ViewBackports.swift
//  Asspp
//
//  Created by luca on 19.09.2025.
//

import SwiftUI

/// Empty states use the same content on iPadOS 16 and newer systems.
struct CompatibleUnavailableView<Label: View, Description: View, Actions: View>: View {
    private let label: Label
    private let description: Description
    private let actions: Actions

    init(
        @ViewBuilder label: () -> Label,
        @ViewBuilder description: () -> Description,
        @ViewBuilder actions: () -> Actions
    ) {
        self.label = label()
        self.description = description()
        self.actions = actions()
    }

    var body: some View {
        if #available(iOS 17.0, macOS 14.0, *) {
            ContentUnavailableView {
                label
            } description: {
                description
            } actions: {
                actions
            }
        } else {
            VStack(spacing: 16) {
                label.font(.title2.bold())
                description.foregroundStyle(.secondary)
                actions
            }
            .multilineTextAlignment(.center)
            .padding(24)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

extension View {
    @ViewBuilder
    func mediumAndLargeDetents() -> some View {
        #if os(iOS)
            presentationDetents([.medium, .large])
        #else
            self
        #endif
    }

    @ViewBuilder
    func neverMinimizeTab() -> some View {
        #if os(iOS)
            if #available(iOS 26.0, *) {
                tabBarMinimizeBehavior(.never)
            } else {
                self
            }
        #else
            self
        #endif
    }

    @ViewBuilder
    func activateSearchWhenSearchTabSelected() -> some View {
        #if os(iOS)
            if #available(iOS 26.0, *) {
                tabViewSearchActivation(.searchTabSelection)
            } else {
                self
            }
        #else
            self
        #endif
    }

    @ViewBuilder
    func sidebarAdaptableTabView() -> some View {
        #if os(iOS)
            if #available(iOS 26.0, *) {
                tabViewStyle(.sidebarAdaptable)
            } else {
                self
            }
        #else
            self
        #endif
    }

    @ViewBuilder
    func smallControlSizeOnMac() -> some View {
        #if os(macOS)
            controlSize(.small)
        #else
            self
        #endif
    }

    @ViewBuilder
    func hide() -> some View {}
}

public extension ToolbarContent {
    @ToolbarContentBuilder
    nonisolated func hideSharedBackground() -> some ToolbarContent {
        if #available(iOS 26.0, macOS 26.0, *) {
            sharedBackgroundVisibility(.hidden)
        } else {
            self
        }
    }
}
