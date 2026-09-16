const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

// expo-build-properties' ios.deploymentTarget only sets the Podfile's own
// `platform :ios, 'X'` line — several pods (RevenueCat, PurchasesHybridCommon,
// RNCAsyncStorage's resource target) hardcode their own lower target (13.0/
// 13.4) on their Xcode targets, which newer Xcode toolchains (Xcode Cloud's,
// specifically — this doesn't fail on this repo's older local Xcode) reject
// outright: "range of supported deployment target versions is 15.0 to 27.0.x".
// This appends a per-target floor to the generated Podfile's post_install
// block so every pod target matches the app's real minimum, not just the
// top-level Podfile platform declaration.
const ANCHOR = ':ccache_enabled => ccache_enabled?(podfile_properties),\n    )\n  end';
const FIX = `:ccache_enabled => ccache_enabled?(podfile_properties),
    )
    installer.pods_project.targets.each do |target|
      target.build_configurations.each do |build_configuration|
        if build_configuration.build_settings['IPHONEOS_DEPLOYMENT_TARGET'].to_f < 15.1
          build_configuration.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '15.1'
        end
      end
    end
  end`;

module.exports = function withIosMinDeploymentTarget(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(config.modRequest.platformProjectRoot, 'Podfile');
      const contents = fs.readFileSync(podfilePath, 'utf8');
      if (!contents.includes(ANCHOR)) {
        throw new Error(
          'withIosMinDeploymentTarget: expected Podfile post_install anchor not found — ' +
            'Expo template changed, update plugins/withIosMinDeploymentTarget.js.',
        );
      }
      fs.writeFileSync(podfilePath, contents.replace(ANCHOR, FIX));
      return config;
    },
  ]);
};
