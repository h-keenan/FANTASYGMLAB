import SwiftUI
import WidgetKit

/// Mirrors WidgetSnapshot in mobile/src/lib/liveActivityCore.ts. Written by the
/// app into the shared App Group; this widget never fetches or invents data.
struct WidgetSnapshot: Codable {
  struct Alert: Codable { let title: String; let player: String? }
  let leagueName: String
  let alerts: [Alert]
  let unreadCount: Int
  let updatedAt: Double
}

struct AlertsEntry: TimelineEntry {
  let date: Date
  let snapshot: WidgetSnapshot?
}

struct AlertsProvider: TimelineProvider {
  private func load() -> WidgetSnapshot? {
    guard
      let defaults = UserDefaults(suiteName: FantasyDeskShared.appGroup),
      let json = defaults.string(forKey: FantasyDeskShared.widgetSnapshotKey),
      let data = json.data(using: .utf8)
    else { return nil }
    return try? JSONDecoder().decode(WidgetSnapshot.self, from: data)
  }

  func placeholder(in context: Context) -> AlertsEntry { AlertsEntry(date: Date(), snapshot: nil) }
  func getSnapshot(in context: Context, completion: @escaping (AlertsEntry) -> Void) {
    completion(AlertsEntry(date: Date(), snapshot: load()))
  }
  func getTimeline(in context: Context, completion: @escaping (Timeline<AlertsEntry>) -> Void) {
    let entry = AlertsEntry(date: Date(), snapshot: load())
    completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(30 * 60))))
  }
}

struct AlertsView: View {
  let entry: AlertsEntry
  var body: some View {
    VStack(alignment: .leading, spacing: 4) {
      if let s = entry.snapshot, !s.alerts.isEmpty {
        Text("\(s.leagueName) · \(s.unreadCount) new")
          .font(.caption).foregroundColor(.secondary).lineLimit(1)
        ForEach(Array(s.alerts.enumerated()), id: \.offset) { _, a in
          Text(a.title).font(.footnote).lineLimit(2)
        }
      } else {
        Text("FantasyDesk").font(.headline)
        Text("Open the app to load your alerts.").font(.caption).foregroundColor(.secondary)
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding()
  }
}

struct FantasyDeskAlertsWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "FantasyDeskAlerts", provider: AlertsProvider()) { entry in
      if #available(iOS 17.0, *) {
        AlertsView(entry: entry).containerBackground(.fill.tertiary, for: .widget)
      } else {
        AlertsView(entry: entry)
      }
    }
    .configurationDisplayName("League alerts")
    .description("Latest waiver and trade alerts for your active league.")
    .supportedFamilies([.systemSmall, .systemMedium])
  }
}
