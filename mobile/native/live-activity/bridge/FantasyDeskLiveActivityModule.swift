import ActivityKit
import Foundation
import React
import WidgetKit

/// Thin RN bridge (classic RCT module) over ActivityKit + the App Group
/// widget snapshot. Only compiled into builds prebuilt with
/// FANTASYDESK_LIVE_ACTIVITIES=1. Local updates only (pushType: nil);
/// APNs push-to-update is the documented phase 2.
@objc(FantasyDeskLiveActivity)
class FantasyDeskLiveActivity: NSObject {
  @objc static func requiresMainQueueSetup() -> Bool { false }

  @objc(isSupported:rejecter:)
  func isSupported(_ resolve: RCTPromiseResolveBlock, rejecter reject: RCTPromiseRejectBlock) {
    if #available(iOS 16.2, *) {
      resolve(ActivityAuthorizationInfo().areActivitiesEnabled)
    } else {
      resolve(false)
    }
  }

  @objc(startOrUpdate:state:resolver:rejecter:)
  func startOrUpdate(_ leagueName: String, state: NSDictionary,
                     resolver resolve: @escaping RCTPromiseResolveBlock,
                     rejecter reject: @escaping RCTPromiseRejectBlock) {
    guard #available(iOS 16.2, *) else { resolve(false); return }
    guard let content = Self.decode(state) else { reject("bad_state", "Invalid content state", nil); return }
    Task {
      if let existing = Activity<FantasyDeskActivityAttributes>.activities.first {
        await existing.update(ActivityContent(state: content, staleDate: Date().addingTimeInterval(15 * 60)))
        resolve(true)
        return
      }
      do {
        _ = try Activity.request(
          attributes: FantasyDeskActivityAttributes(leagueName: leagueName),
          content: ActivityContent(state: content, staleDate: Date().addingTimeInterval(15 * 60)),
          pushType: nil)
        resolve(true)
      } catch {
        reject("start_failed", error.localizedDescription, error)
      }
    }
  }

  @objc(end:rejecter:)
  func end(_ resolve: @escaping RCTPromiseResolveBlock, rejecter reject: RCTPromiseRejectBlock) {
    guard #available(iOS 16.2, *) else { resolve(false); return }
    Task {
      for activity in Activity<FantasyDeskActivityAttributes>.activities {
        await activity.end(nil, dismissalPolicy: .immediate)
      }
      resolve(true)
    }
  }

  @objc(setWidgetSnapshot:resolver:rejecter:)
  func setWidgetSnapshot(_ json: String, resolver resolve: RCTPromiseResolveBlock, rejecter reject: RCTPromiseRejectBlock) {
    guard let defaults = UserDefaults(suiteName: FantasyDeskShared.appGroup) else {
      reject("no_app_group", "App Group unavailable", nil); return
    }
    defaults.set(json, forKey: FantasyDeskShared.widgetSnapshotKey)
    WidgetCenter.shared.reloadAllTimelines()
    resolve(true)
  }

  @available(iOS 16.2, *)
  private static func decode(_ d: NSDictionary) -> FantasyDeskActivityAttributes.ContentState? {
    guard
      let myTeam = d["myTeam"] as? String, let opp = d["opponentTeam"] as? String,
      let mine = (d["myPoints"] as? NSNumber)?.doubleValue,
      let theirs = (d["opponentPoints"] as? NSNumber)?.doubleValue,
      let week = (d["week"] as? NSNumber)?.intValue
    else { return nil }
    return .init(myTeam: myTeam, opponentTeam: opp, myPoints: mine, opponentPoints: theirs,
                 winProbability: (d["winProbability"] as? NSNumber)?.doubleValue, week: week)
  }
}
