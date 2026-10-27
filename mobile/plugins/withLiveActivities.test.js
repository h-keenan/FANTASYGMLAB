const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');
const xcode = require('xcode');

const withLiveActivities = require('./withLiveActivities.js');

const PBX = path.join(__dirname, '..', 'ios', 'FantasyGMLab.xcodeproj', 'project.pbxproj');

test('plugin is a no-op unless FANTASYDESK_LIVE_ACTIVITIES=1', () => {
  delete process.env.FANTASYDESK_LIVE_ACTIVITIES;
  const cfg = { name: 'x' };
  assert.equal(withLiveActivities(cfg), cfg);
});

test('addTargets adds a widget extension target to the real pbxproj and stays parseable', () => {
  const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'pbx-')), 'project.pbxproj');
  fs.copyFileSync(PBX, tmp);
  const proj = xcode.project(tmp);
  proj.parseSync();
  const before = Object.keys(proj.pbxNativeTargetSection()).length;
  withLiveActivities.addTargets(proj, { projectName: 'FantasyGMLab', bundleId: 'com.fantasygmlab.app' });
  assert.ok(withLiveActivities.hasTarget(proj));
  assert.equal(Object.keys(proj.pbxNativeTargetSection()).length, before + 2); // target + its comment
  const out = proj.writeSync();
  assert.match(out, /com\.fantasygmlab\.app\.widgets/);
  assert.match(out, /WidgetKit\.framework/);
  assert.match(out, /Embed Foundation Extensions/);
  assert.match(out, /Begin PBXTargetDependency section/);
  const main = proj.getFirstTarget().firstTarget;
  assert.equal(main.dependencies.length, 1, 'app depends on the extension target');
  const embed = Object.values(proj.hash.project.objects.PBXCopyFilesBuildPhase).find(
    (p) => p && p.name === '"Embed Foundation Extensions"',
  );
  assert.equal(embed.dstSubfolderSpec, 13);
  assert.equal(embed.files.length, 1);
  assert.match(out, /FantasyDeskLiveActivityModule\.swift in Sources/);
  fs.writeFileSync(tmp, out);
  const again = xcode.project(tmp);
  again.parseSync(); // round-trips
  // idempotent
  const n = Object.keys(again.pbxNativeTargetSection()).length;
  withLiveActivities.addTargets(again, { projectName: 'FantasyGMLab', bundleId: 'com.fantasygmlab.app' });
  assert.equal(Object.keys(again.pbxNativeTargetSection()).length, n);
});
