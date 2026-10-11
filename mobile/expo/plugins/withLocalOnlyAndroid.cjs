// Maintained outside CNG output. No OS settings or firewall changes.
const { withAndroidManifest, withDangerousMod, withProjectBuildGradle, withAppBuildGradle } = require('@expo/config-plugins');
const fs = require('node:fs/promises');
const path = require('node:path');

// Remove only our exact older generated block. Never discard unknown manual
// native edits when applying a new configuration version.
const legacyBudget = `// NOOK_NATIVE_BUILD_BUDGET_V1
// Keep all application/library Ninja compilation and linking serial. Gradle's
// worker cap alone does not constrain the processes spawned by CMake/Ninja.
subprojects { nativeProject ->
  ['com.android.application', 'com.android.library'].each { pluginId ->
    nativeProject.plugins.withId(pluginId) {
      def nativeAndroid = nativeProject.extensions.getByName('android')
      nativeAndroid.defaultConfig.externalNativeBuild.cmake.arguments.addAll([
        '-DCMAKE_JOB_POOLS=nook_native_work=1',
        '-DCMAKE_JOB_POOL_COMPILE=nook_native_work',
        '-DCMAKE_JOB_POOL_LINK=nook_native_work'
      ])
    }
  }
}
`;

const budgetCallbacks = `subprojects { nativeProject ->
  ['com.android.application', 'com.android.library'].each { pluginId ->
    nativeProject.plugins.withId(pluginId) {
      nativeProject.extensions.getByName('androidComponents').finalizeDsl { nativeAndroid ->
        def nativeArguments = nativeAndroid.defaultConfig.externalNativeBuild.cmake.arguments
        [
          '-DCMAKE_JOB_POOLS=nook_native_work=1',
          '-DCMAKE_JOB_POOL_COMPILE=nook_native_work',
          '-DCMAKE_JOB_POOL_LINK=nook_native_work'
        ].each { nativeArgument ->
          if (!nativeArguments.contains(nativeArgument)) nativeArguments.add(nativeArgument)
        }
      }
    }
  }
}
`;
const budgetComments = `// Keep all application/library Ninja compilation and linking serial. Gradle's
// worker cap alone does not constrain the processes spawned by CMake/Ninja.
`;
const budgetV2 = '// NOOK_NATIVE_BUILD_BUDGET_V2\n' + budgetComments
  + '// Apply at DSL finalization: the application plugin replaces early defaults.\n' + budgetCallbacks;
const budgetV3 = '// NOOK_NATIVE_BUILD_BUDGET_V3\n' + budgetComments
  + '// Register before root plugins eagerly evaluate :app; apply at DSL finalization.\n' + budgetCallbacks;

const prebundleBlock = `// NOOK_VERIFIED_PREBUNDLE_V1
// Keep the producer task in Gradle's graph: -x prevents Gradle 9 providers
// from reading generated resource paths. Skip generation only after verifying
// the actual staged Hermes asset against its current maintained source.
tasks.withType(com.facebook.react.tasks.BundleHermesCTask).configureEach { bundleTask ->
  if (bundleTask.name == 'createBundleReleaseJsAndAssets') {
    bundleTask.onlyIf('Generate with Metro unless a real prebundle is verified') {
      if (providers.gradleProperty('nook.prebundledRelease').orNull != 'true') return true
      def inputFile = rootProject.file('.nook-prebundled-release.json')
      if (!inputFile.isFile()) throw new GradleException('Generate the guarded Nook prebundle first.')
      def receipt = new groovy.json.JsonSlurper().parse(inputFile)
      def bundleFile = new File(bundleTask.jsBundleDir.get().asFile, 'index.android.bundle')
      def sha256File = { sourceFile ->
        java.security.MessageDigest.getInstance('SHA-256').digest(sourceFile.bytes).encodeHex().toString()
      }
      if (!bundleFile.isFile() || sha256File(bundleFile) != receipt.bundleSha256) {
        throw new GradleException('The actual staged Hermes asset changed; regenerate it.')
      }
      receipt.sourceHashes.each { relativePath, expectedHash ->
        if (relativePath.startsWith('/') || relativePath.split('/').contains('..')) {
          throw new GradleException('Invalid prebundle source path.')
        }
        def sourceFile = new File(rootProject.projectDir.parentFile, relativePath)
        if (!sourceFile.isFile() || sha256File(sourceFile) != expectedHash) {
          throw new GradleException('Prebundle source changed; regenerate before native assembly.')
        }
      }
      if (!bundleTask.resourcesDir.get().asFile.isDirectory()) throw new GradleException('Prebundle resources directory is missing.')
      logger.lifecycle('Nook verified real prebuilt Hermes asset: ' + receipt.bundleSha256)
      return false
    }
  }
}
`;

module.exports = (config) => {
  config = withProjectBuildGradle(config, (result) => {
    if (result.modResults.language !== 'groovy') throw new Error('Review the native build budget for a non-Groovy project.');
    for (const [marker, body] of [
      ['// NOOK_NATIVE_BUILD_BUDGET_V1', legacyBudget],
      ['// NOOK_NATIVE_BUILD_BUDGET_V2', budgetV2],
      ['// NOOK_NATIVE_BUILD_BUDGET_V3', budgetV3],
    ]) {
      if (result.modResults.contents.includes(marker)) {
        if (!result.modResults.contents.includes(body)) throw new Error('Review a modified managed native budget before regeneration.');
        result.modResults.contents = result.modResults.contents.replace(body, '');
      }
    }
    const anchor = 'apply plugin: "expo-root-project"';
    if (!result.modResults.contents.includes(anchor)) throw new Error('Review root plugin ordering before installing the native build budget.');
    result.modResults.contents = result.modResults.contents.replace(anchor, budgetV3 + '\n' + anchor);
    return result;
  });
  config = withAppBuildGradle(config, (result) => {
    if (result.modResults.language !== 'groovy') throw new Error('Review prebundle handling for a non-Groovy project.');
    if (!result.modResults.contents.includes('// NOOK_VERIFIED_PREBUNDLE_V1')) {
      result.modResults.contents += '\n' + prebundleBlock;
    }
    return result;
  });
  config = withAndroidManifest(config, (result) => {
    const application = result.modResults.manifest.application?.[0];
    if (!application) throw new Error('Android application manifest is missing');
    application.$['android:allowBackup'] = 'false';
    application.$['android:fullBackupContent'] = 'false';
    // Android 12+ OEM device-transfer rules are separate from allowBackup.
    // Exclude this private, unencrypted feasibility vault from both routes.
    application.$['android:dataExtractionRules'] = '@xml/nook_data_extraction_rules';
    return result;
  });
  return withDangerousMod(config, ['android', async (result) => {
    const directory = path.join(result.modRequest.platformProjectRoot, 'app/src/main/res/xml');
    await fs.mkdir(directory, { recursive: true });
    const domains = ['root', 'file', 'database', 'sharedpref', 'external',
      'device_root', 'device_file', 'device_database', 'device_sharedpref'];
    const exclusions = domains.map((domain) => `    <exclude domain="${domain}" path="." />`).join('\n');
    await fs.writeFile(path.join(directory, 'nook_data_extraction_rules.xml'),
      '<?xml version="1.0" encoding="utf-8"?>\n' +
      `<data-extraction-rules>\n  <cloud-backup>\n${exclusions}\n  </cloud-backup>\n` +
      `  <device-transfer>\n${exclusions}\n  </device-transfer>\n` +
      `  <cross-platform-transfer platform="ios">\n${exclusions}\n  </cross-platform-transfer>\n` +
      '</data-extraction-rules>\n');
    return result;
  }]);
};
