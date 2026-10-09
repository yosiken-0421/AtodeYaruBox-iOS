import SwiftUI

struct OnboardingView: View {
    let finish: () -> Void
    @State private var page = 0
    @Environment(\.dynamicTypeSize) private var typeSize
    private let titles = ["あとでやる箱", "何でも保存できます", "必要な時に知らせます"]
    private let messages = ["「あとでやろう」を\n忘れない場所へ。", "スクリーンショット\nWebページ\nメモ\nファイル", "完了するまで\nあとでやる箱に残ります。"]
    private let symbols = ["tray", "square.and.arrow.down", "bell"]

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(spacing: 28) {
                    Image(systemName: symbols[page]).font(.system(size: 64))
                        .foregroundStyle(Color.boxAccent).accessibilityHidden(true)
                    BoxStatusText(text: titles[page], headline: true, identifier: "onboardingTitle",
                        textStyle: .largeTitle, centered: true, background: .systemGroupedBackground)
                    BoxStatusText(text: messages[page], identifier: "onboardingMessage",
                        textStyle: .title3, centered: true, background: .systemGroupedBackground)
                    BoxStatusText(text: "\(page + 1) / 3", identifier: "onboardingProgress",
                        textStyle: .subheadline, centered: true, background: .systemGroupedBackground)
                    BoxActionButton(title: page < 2 ? "次へ" : "はじめる", symbol: "arrow.right", prominent: true,
                        identifier: "onboardingNext") {
                        if page < 2 { page += 1 } else { finish() }
                    }
                    if page < 2 {
                        BoxActionButton(title: "はじめる", symbol: "checkmark", identifier: "onboardingSkip", action: finish)
                    }
                }
                .id("introTop")
                .padding(28).padding(.top, typeSize.isAccessibilitySize ? 12 : 48)
            }
            .onChange(of: page) { _, _ in
                // Start each page at its heading without motion or hidden gestures.
                proxy.scrollTo("introTop", anchor: .top)
            }
        }
        .tint(.boxAccent).background(Color(.systemGroupedBackground))
    }
}
