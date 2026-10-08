import SwiftUI

struct OnboardingView: View {
    let finish: () -> Void
    @State private var page = 0
    private let titles = ["あとでやる箱", "何でも保存できます", "必要な時に知らせます"]
    private let messages = ["「あとでやろう」を\n忘れない場所へ。", "スクリーンショット\nWebページ\nメモ\nファイル", "完了するまで\nあとでやる箱に残ります。"]
    private let symbols = ["tray", "square.and.arrow.down", "bell"]
    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                Image(systemName: symbols[page]).font(.system(size: 64)).foregroundStyle(Color.boxAccent).accessibilityHidden(true)
                Text(titles[page]).font(.largeTitle.bold()).multilineTextAlignment(.center)
                Text(messages[page]).font(.title3).multilineTextAlignment(.center)
                Text("\(page + 1) / 3").font(.subheadline).foregroundStyle(.secondary)
                Button {
                    if page < 2 { page += 1 } else { finish() }
                } label: {
                    Text(page < 2 ? "次へ" : "はじめる").frame(maxWidth: .infinity, minHeight: 44)
                }.buttonStyle(.borderedProminent).tint(.boxButton).accessibilityIdentifier("onboardingNext")
                if page < 2 { Button("はじめる", action: finish).frame(minHeight: 44).accessibilityIdentifier("onboardingSkip") }
            }
            .padding(28).padding(.top, 48)
        }
        .tint(.boxAccent).background(Color(.systemGroupedBackground))
    }
}
