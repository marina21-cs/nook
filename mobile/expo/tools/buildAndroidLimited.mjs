// Invoke inside scripts/software_guard.py. This controls only the owned build,
// never host settings, SDK licenses, credentials, devices or model artifacts.
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifiedBundle } from './androidBundleInputs.mjs';

const [mode, gradle, sdk, gradleHome] = process.argv.slice(2);
if (!['help', 'debug', 'release'].includes(mode) || !gradle || !sdk || !gradleHome) {
  throw new Error('Usage: buildAndroidLimited.mjs help|debug|release GRADLE SDK GRADLE_HOME');
}
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'android');
for (const path of [gradle, `${sdk}/platforms/android-36`, `${sdk}/build-tools/36.0.0`,
  `${sdk}/ndk/27.1.12297006`, `${sdk}/cmake/3.22.1`, `${project}/app/debug.keystore`]) {
  if (!existsSync(path)) throw new Error(`Required existing build input is missing: ${path}`);
}
// Java/native helper threads can exceed ActiveProcessorCount. Restrict only
// this owned process tree to two already-allowed CPUs; never change host policy.
const taskset = '/usr/bin/taskset';
if (!existsSync(taskset)) throw new Error('This bounded Linux build requires taskset.');
const allowed = readFileSync('/proc/self/status', 'utf8').match(/^Cpus_allowed_list:\s*(.+)$/m)?.[1];
if (!allowed) throw new Error('Could not determine this process’s allowed CPUs.');
const cpus = [];
for (const part of allowed.split(',')) {
  const [start, end = start] = part.split('-').map(Number);
  if (!Number.isInteger(start) || !Number.isInteger(end) || end < start) throw new Error('Invalid allowed CPU list.');
  for (let cpu = start; cpu <= end && cpus.length < 2; cpu += 1) cpus.push(cpu);
  if (cpus.length === 2) break;
}
if (!cpus.length) throw new Error('No CPUs available for this build.');
const task = mode === 'help' ? 'help' : mode === 'debug' ? ':app:assembleDebug' : ':app:assembleRelease';
// The first 384 MiB heap exhausted during Expo Kotlin compilation. Keep the
// process-tree guard unchanged; allow 128 MiB more heap with cached native work.
const jvm = '-Xmx512m -XX:MaxMetaspaceSize=384m -XX:ReservedCodeCacheSize=64m -XX:ActiveProcessorCount=1 -XX:+UseSerialGC';
const args = ['-p', project, task, '--no-daemon', '--max-workers=1', '--no-watch-fs', '--console=plain',
  '--stacktrace', `-Dorg.gradle.jvmargs=${jvm}`, '-Dorg.gradle.parallel=false',
  '-Dorg.gradle.workers.max=1', '-Pkotlin.compiler.execution.strategy=in-process',
  '-Dkotlin.compiler.execution.strategy=in-process', '-Pandroid.builder.sdkDownload=false',
  '-Dorg.gradle.java.installations.auto-download=false', '-Porg.gradle.java.installations.auto-download=false',
  '-PreactNativeArchitectures=arm64-v8a'];
// Bundle first in its own guarded stage. The maintained producer-task gate
// verifies these bytes, then skips only generation while remaining in the DAG.
const bundle = mode === 'release' ? verifiedBundle() : null;
if (bundle) args.push('-Pnook.prebundledRelease=true');
console.log(JSON.stringify({ task, project, gradle, sdk, gradleHome, args, processAffinity: cpus,
  prebundle: bundle && { sha256: bundle.bundleSha256, bytes: bundle.bundleBytes, utc: bundle.utc },
  abi: 'arm64-v8a diagnostic only; not a supported-device decision',
  signing: 'existing public template debug key; no production credential',
  guardRequired: true }));
const child = spawn(taskset, ['-c', cpus.join(','), gradle, ...args], { cwd: project, stdio: 'inherit', env: {
  ...process.env, ANDROID_HOME: sdk, ANDROID_SDK_ROOT: sdk, GRADLE_USER_HOME: gradleHome,
  JAVA_HOME: process.env.JAVA_HOME || '/usr/lib/jvm/java-17-openjdk',
  PATH: `${dirname(process.execPath)}:${process.env.PATH || ''}`,
  JAVA_OPTS: '-Xmx64m -XX:ActiveProcessorCount=1 -XX:+UseSerialGC',
  CMAKE_BUILD_PARALLEL_LEVEL: '1', CI: '1', EXPO_NO_TELEMETRY: '1', EXPO_OFFLINE: '1',
  NODE_ENV: mode === 'release' ? 'production' : 'development',
} });
child.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
