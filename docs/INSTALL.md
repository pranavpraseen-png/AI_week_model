# Install AnaemiaLens, click by click

There are two ways to get AnaemiaLens as an app. Both work with **no internet** after the first time.

| | **A. Install from Chrome** (easiest) | **B. Desktop app from GitHub** |
|---|---|---|
| Best for | Chromebook, any laptop, Android phone | Windows, Mac, Linux, or a Chromebook with Linux turned on |
| Camera | ✅ works | Windows/Mac/Linux ✅; on a Chromebook use **Choose a photo** instead (ChromeOS doesn't share the camera with Linux apps) |
| Size | about 1 MB | about 100 MB |
| Updates | by itself | download the new version |

The model is trained on **simulated** photos, so every number it shows is a demo, not a real medical estimate.

---

## A. Install from Chrome (Chromebook, laptop or Android)

1. Open **Chrome**.
2. Go to **pranavpraseen-png.github.io/AI_week_model**.
3. Wait until the page has fully opened (you see "Read your blood through a fingernail").
4. Install it:
   - **Chromebook / laptop:** in the address bar, on the right, click the **Install** icon (a small screen with a down arrow) → click **Install**.
     *No icon?* Click **⋮** (top right) → **Cast, save and share** → **Install page as app…** → **Install**.
   - **Android phone:** tap **⋮** (top right) → **Add to Home screen** → **Install**.
5. AnaemiaLens opens in its own window. It is now in your **Launcher** (Chromebook: press the **Everything** button / circle key, bottom left) or on your **Home screen** (phone).
6. **Check it works offline:** turn on airplane mode (Chromebook: click the clock, bottom right → **Wi-Fi** off), open AnaemiaLens from the Launcher, and do a check. It works with no signal.

**Pin it (Chromebook):** right-click (two-finger tap) the AnaemiaLens icon in the shelf → **Pin**.

---

## B. Desktop app on a Chromebook (Linux)

### Step 1 · Turn on Linux (one time, about 5–10 minutes)
1. Click the **clock** (bottom right) → the **gear** ⚙️ (**Settings**).
2. In the left menu click **About ChromeOS** → **Developers**.
   *(On older ChromeOS: **Advanced** → **Developers**.)*
3. Next to **Linux development environment**, click **Set up** (or **Turn on**).
4. Click **Next**. Leave the username and the **Recommended** disk size as they are.
5. Click **Install**. Wait until a black **Terminal** window opens. Linux is ready.

### Step 2 · Find out which file you need
1. In the **Terminal** window, type this and press **Enter**:
   ```
   dpkg --print-architecture
   ```
2. It prints one word:
   - `amd64` → you need **AnaemiaLens-1.0.1-amd64.deb**
   - `arm64` → you need **AnaemiaLens-1.0.1-arm64.deb**

### Step 3 · Download
1. In Chrome, go to **github.com/pranavpraseen-png/AI_week_model/releases**.
2. Under the newest version, click **Assets** (if it is folded).
3. Click your file from Step 2 (`…amd64.deb` or `…arm64.deb`). It downloads (about 100 MB).

### Step 4 · Install
1. Open the **Files** app → **Downloads**.
2. **Right-click** (two-finger tap) the `.deb` file → **Install with Linux**.
3. Click **Install**. Wait for "Installation complete" → **OK**.

### Step 5 · Open it
1. Press the **Everything** button (Launcher).
2. Open the **Linux apps** folder → click **AnaemiaLens**.
3. To keep it handy: right-click its icon in the shelf → **Pin**.

To take a photo in the desktop app on a Chromebook, save the photo first (Camera app), then in AnaemiaLens tap **Choose a photo**. Or use way **A**, where the camera works.

**Remove it later:** Launcher → **Linux apps** → right-click **AnaemiaLens** → **Uninstall**.

---

## B. Desktop app on Windows, Mac or Linux

1. Go to **github.com/pranavpraseen-png/AI_week_model/releases** → newest version → **Assets**.
2. Download and open your file:
   - **Windows:** `AnaemiaLens-Setup-1.0.1.exe`. If you see "Windows protected your PC", click **More info** → **Run anyway** (the app isn't code-signed yet; that costs money). Follow the installer. Or use `AnaemiaLens-Portable-1.0.1.exe`, which runs without installing.
   - **Mac:** `…arm64.dmg` for Apple chips (M1/M2/M3/M4), `…x64.dmg` for Intel (Apple menu → **About This Mac** shows which). Open it, drag **AnaemiaLens** to **Applications**. The first time, **right-click** the app → **Open** → **Open** (it's from an "unidentified developer" because it isn't signed).
   - **Linux (Debian/Ubuntu):** the `.deb` (open it with your software installer), or the `.AppImage`: right-click → **Properties** → **Permissions** → tick **Allow executing as program**, then double-click it. If it won't start, run `sudo apt install libfuse2` once.

---

## For the demo day
- Install it once **with** internet the day before, then test it in **airplane mode**.
- Keep a few simulated photos on the device (`data/simulated/images/`) for **Choose a photo**, in case the camera or light is bad.
- The optional **Explain in simple words** button is off by default (Settings) and needs a local language model (Ollama, see `CLAUDE.md` §8). Everything else, including the result and what to do next, works without it.
