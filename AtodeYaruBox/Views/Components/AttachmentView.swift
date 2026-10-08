import SwiftUI
import QuickLook

struct AttachmentView: View {
    let path: String
    let thumbnailPath: String?
    @State private var previewURL: URL?
    var body: some View {
        if let url = AssetStore.url(for: path), FileManager.default.fileExists(atPath: url.path) {
            Button { previewURL = url } label: {
                HStack(spacing: 12) {
                    if let thumbnail = AssetStore.url(for: thumbnailPath), let image = UIImage(contentsOfFile: thumbnail.path) {
                        Image(uiImage: image).resizable().scaledToFit().frame(width: 56, height: 56).accessibilityHidden(true)
                    }
                    Label("保存した写真・ファイルを開く", systemImage: "doc")
                }.frame(minHeight: 44)
            }.quickLookPreview($previewURL)
        } else {
            Label("元のファイルを開けません", systemImage: "doc.badge.ellipsis").foregroundStyle(.secondary)
        }
    }
}
