import SwiftUI
import WidgetKit

@main
struct FantasyDeskWidgetBundle: WidgetBundle {
  var body: some Widget {
    FantasyDeskAlertsWidget()
    if #available(iOS 16.2, *) {
      FantasyDeskLiveActivityWidget()
    }
  }
}
