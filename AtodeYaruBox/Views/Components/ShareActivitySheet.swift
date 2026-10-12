import SwiftUI
import UIKit

struct ShareActivityPayload: Identifiable {
    enum Content { case text(String), file(URL) }
    let id = UUID()
    let content: Content
}

struct ShareActivitySheet: UIViewControllerRepresentable {
    let payload: ShareActivityPayload
    @Environment(\.dismiss) private var dismiss
    func makeUIViewController(context: Context) -> UIActivityViewController {
        let items: [Any]
        switch payload.content {
        case .text(let text): items = [text]
        case .file(let url): items = [url]
        }
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        controller.completionWithItemsHandler = { _, _, _, _ in
            if case .file(let url) = payload.content { try? FileManager.default.removeItem(at: url) }
            dismiss()
        }
        return controller
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
