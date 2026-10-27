import ActivityKit
import Foundation

/// Shared by the app target (bridge/) and the widget extension target.
/// ContentState field names MUST match LiveActivityContentState in
/// mobile/src/lib/liveActivityCore.ts (enforced by liveActivityCore.test.ts).
@available(iOS 16.2, *)
struct FantasyDeskActivityAttributes: ActivityAttributes {
  let leagueName: String

  public struct ContentState: Codable, Hashable {
    var myTeam: String
    var opponentTeam: String
    var myPoints: Double
    var opponentPoints: Double
    var winProbability: Double?
    var week: Int
  }
}

enum FantasyDeskShared {
  /// Must equal the App Group created in the Apple developer portal.
  static let appGroup = "group.com.fantasygmlab.app"
  static let widgetSnapshotKey = "widgetSnapshot"
}
