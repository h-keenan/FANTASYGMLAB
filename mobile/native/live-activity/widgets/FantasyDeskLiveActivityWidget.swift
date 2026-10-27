import ActivityKit
import SwiftUI
import WidgetKit

// Colors mirror mobile/src/theme.ts semantic tokens (success / danger / accent).
private extension Color {
  static let fdAccent = Color(red: 0.404, green: 0.910, blue: 0.976)   // #67E8F9
  static let fdSuccess = Color(red: 0.133, green: 0.773, blue: 0.369)  // #22C55E
  static let fdDanger = Color(red: 1.0, green: 0.302, blue: 0.302)     // #FF4D4D
}

@available(iOS 16.2, *)
private func leadColor(_ s: FantasyDeskActivityAttributes.ContentState) -> Color {
  if s.myPoints > s.opponentPoints { return .fdSuccess }
  if s.myPoints < s.opponentPoints { return .fdDanger }
  return .secondary
}

private func fmt(_ v: Double) -> String { String(format: "%.1f", v) }

@available(iOS 16.2, *)
struct FantasyDeskLiveActivityWidget: Widget {
  var body: some WidgetConfiguration {
    ActivityConfiguration(for: FantasyDeskActivityAttributes.self) { context in
      // Lock screen / banner
      let s = context.state
      VStack(alignment: .leading, spacing: 6) {
        Text("\(context.attributes.leagueName) · Week \(s.week)")
          .font(.caption).foregroundColor(.secondary)
        HStack {
          VStack(alignment: .leading) {
            Text(s.myTeam).font(.subheadline).lineLimit(1)
            Text(fmt(s.myPoints)).font(.title).bold().foregroundColor(leadColor(s))
          }
          Spacer()
          VStack(alignment: .trailing) {
            Text(s.opponentTeam).font(.subheadline).lineLimit(1)
            Text(fmt(s.opponentPoints)).font(.title).bold()
          }
        }
        if let p = s.winProbability {
          Text("Win probability \(Int((p * 100).rounded()))%")
            .font(.caption2).foregroundColor(.fdAccent)
        }
      }
      .padding()
    } dynamicIsland: { context in
      let s = context.state
      return DynamicIsland {
        DynamicIslandExpandedRegion(.leading) {
          VStack(alignment: .leading) {
            Text(s.myTeam).font(.caption).lineLimit(1)
            Text(fmt(s.myPoints)).font(.title2).bold().foregroundColor(leadColor(s))
          }
        }
        DynamicIslandExpandedRegion(.trailing) {
          VStack(alignment: .trailing) {
            Text(s.opponentTeam).font(.caption).lineLimit(1)
            Text(fmt(s.opponentPoints)).font(.title2).bold()
          }
        }
        DynamicIslandExpandedRegion(.bottom) {
          if let p = s.winProbability {
            Text("Win probability \(Int((p * 100).rounded()))%").font(.caption2)
          } else {
            Text("Week \(s.week)").font(.caption2)
          }
        }
      } compactLeading: {
        Text(fmt(s.myPoints)).foregroundColor(leadColor(s))
      } compactTrailing: {
        Text(fmt(s.opponentPoints))
      } minimal: {
        Text(fmt(s.myPoints)).foregroundColor(leadColor(s))
      }
    }
  }
}
