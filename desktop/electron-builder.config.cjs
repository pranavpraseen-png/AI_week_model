// How `npm run dist` packages the app (electron-builder).
// It builds for the computer you run it on: Windows -> installer + portable .exe,
// macOS -> .dmg, Linux -> .AppImage + .deb (x64 and arm64). GitHub Actions builds all three
// (.github/workflows/desktop.yml). Builds are NOT code-signed, so Windows and
// macOS show an "unknown publisher / unidentified developer" warning.
const ICON = "../web/icons/icon-512.png";

module.exports = {
  appId: "org.anaemialens.desktop",
  productName: "AnaemiaLens",
  directories: { output: "dist" },

  // The app's own code is tiny: just main.js. It goes inside app.asar.
  files: ["main.js", "package.json"],
  // The website is copied, unchanged, from the ONE copy in ../web (never edited here).
  // main.js finds it at process.resourcesPath/web.
  extraResources: [{ from: "../web", to: "web" }],

  // Electron "fuses": switches burnt into the app file that turn off features we
  // never use, so nobody can use them to make the installed app run other code.
  electronFuses: {
    runAsNode: false, // ELECTRON_RUN_AS_NODE=1 cannot turn the app into a plain Node.js
    enableNodeOptionsEnvironmentVariable: false, // NODE_OPTIONS cannot inject code
    enableNodeCliInspectArguments: false, // --inspect cannot attach a debugger
    onlyLoadAppFromAsar: true, // only our packaged code is ever loaded
    grantFileProtocolExtraPrivileges: false, // we never use file:// pages
    resetAdHocDarwinSignature: true, // macOS (Apple chips) needs a fresh ad-hoc signature after the change
  },

  win: {
    icon: ICON,
    target: [
      { target: "nsis", arch: ["x64"] }, // a normal installer
      { target: "portable", arch: ["x64"] }, // one .exe that runs without installing (e.g. from a USB stick)
    ],
  },
  nsis: { artifactName: "${productName}-Setup-${version}.${ext}" },
  portable: { artifactName: "${productName}-Portable-${version}.${ext}" },

  mac: {
    icon: ICON,
    category: "public.app-category.medical",
    target: [{ target: "dmg", arch: ["arm64", "x64"] }], // Apple-chip and Intel Macs
    // macOS asks the user before any app may use the camera, and shows this sentence.
    extendInfo: {
      NSCameraUsageDescription: "AnaemiaLens uses the camera to photograph a fingernail. The photo never leaves this computer.",
    },
  },
  dmg: { artifactName: "${productName}-${version}-${arch}.${ext}" },

  linux: {
    icon: ICON,
    category: "Science",
    executableName: "anaemialens",
    syncDesktopName: true, // lets the desktop link the open window to its menu entry
    // AppImage: one file that runs without installing. deb: double-click to install on
    // Debian/Ubuntu and on a Chromebook's Linux (Files app -> "Install with Linux").
    // arm64 too, because many Chromebooks (and Raspberry Pis) have ARM chips.
    target: [
      { target: "AppImage", arch: ["x64", "arm64"] },
      { target: "deb", arch: ["x64", "arm64"] },
    ],
    maintainer: "AnaemiaLens student project <https://github.com/pranavpraseen-png/AI_week_model>",
  },
  appImage: { artifactName: "${productName}-${version}-${arch}.${ext}" },
  deb: { artifactName: "${productName}-${version}-${arch}.${ext}" },

  publish: null, // never upload anywhere; CI keeps the files as workflow artifacts
};
