# Blixtro IMS — Capacitor Mobile App Setup Guide (Android & iOS)

This guide walks you through setting up the Blixtro Django web app as a fully working native mobile app using Capacitor — from scratch. Every step is explained in plain language. Follow it in order.

---

## What This Guide Covers

- Why the current app has issues and what the root causes are
- Complete Android setup from scratch
- Complete iOS setup from scratch
- Fixing Google Authentication in the app
- Fixing downloads in the app
- Fixing navigation (home button, cards on landing page)
- Making all web features work inside the app
- Publishing to Google Play Store and Apple App Store

---

## Who Does What — Quick Reference

This table tells you exactly which steps require your action and which are already done in the codebase.

| Step | What to do | Done by |
|------|-----------|---------|
| `capacitor.config.ts` — replace server URL | Already set to `https://blixtro.sfscollege.app/` | Done |
| `capacitor.config.ts` — everything else | Already written correctly | Done |
| `www/index.html` | Create the redirect file | **You** |
| `npx cap add android` / `npx cap add ios` | Run once to generate native folders | **You** |
| `AndroidManifest.xml` — deep link intent filter | Add the XML block shown in Part 4 | **You** |
| `network_security_config.xml` | Create the file shown in Part 4 | **You** |
| `Info.plist` — URL scheme (iOS) | Add the XML block shown in Part 5 | **You** |
| `firebase_login_callback` view — Capacitor branch | **Already added** — no action needed | Done |
| `signInWithRedirect` in JS | Already handled — popup with redirect fallback is in place | Done |
| `mobile-utils.js` deep link handler | Already set up correctly | Done |
| Download fix (`DownloadManager.download`) | Already updated in all templates | Done |
| Keystore for release signing | Generate once, keep safe | **You** |
| Google Play / App Store accounts | Register developer accounts | **You** |

---

## Understanding the Root Causes of Current Issues

Before fixing anything, understand why things break:

1. **Google Auth opens the browser and never returns** — Capacitor's WebView blocks Firebase `signInWithPopup` because it is not a trusted browser context. The fix is to use Firebase's `signInWithRedirect` with a custom URL scheme deep link so the app catches the OAuth callback.

2. **Downloads show "downloading" but nothing saves** — The standard `<a download>` HTML approach does not work in a WebView. You must use the Capacitor Filesystem plugin to write the file to device storage, then open it.

3. **Home button and cards don't render** — These rely on CSS that uses `env(safe-area-inset-*)` and viewport units that behave differently inside a WebView. The fix is proper `capacitor.config.ts` settings and ensuring the Django server URL is set correctly.

4. **Web features don't respond** — The app is pointing at `localhost` instead of your live server, so API calls fail silently.

---

## Prerequisites — Install These First

You need the following tools installed on your computer before starting.

### On Windows

1. **Node.js (v18 or later)** — Download from https://nodejs.org and install. After installing, open a new terminal and run `node -v` to confirm it works.

2. **Java Development Kit (JDK 17)** — Download from https://adoptium.net and install. After installing, run `java -version` in a terminal to confirm.

3. **Android Studio** — Download from https://developer.android.com/studio and install. During setup, make sure "Android SDK", "Android SDK Platform", and "Android Virtual Device" are all checked.

4. **Xcode (iOS only — Mac required)** — iOS builds can only be done on a Mac. Install Xcode from the Mac App Store. After installing, run `xcode-select --install` in Terminal.

5. **CocoaPods (iOS only)** — On Mac, open Terminal and run:
   ```
   sudo gem install cocoapods
   ```

---

## Part 1 — Project Setup

### Step 1: Open the project root

Open a terminal (Command Prompt or PowerShell on Windows, Terminal on Mac) and navigate to the root of the Blixtro project — the folder that contains `package.json`.

### Step 2: Install all Node dependencies

Run this command:

```bash
npm install
```

This installs Capacitor and all its plugins listed in `package.json`.

### Step 3: Install the Capacitor CLI globally

```bash
npm install -g @capacitor/cli
```

### Step 4: Install the core Capacitor package

```bash
npm install @capacitor/core
```

### Step 5: Install all required Capacitor plugins

Run this single command to install everything needed:

```bash
npm install @capacitor/app @capacitor/browser @capacitor/filesystem @capacitor/share @capacitor/status-bar @capacitor/splash-screen @capacitor/preferences
```

---

## Part 2 — The Capacitor Configuration File

`capacitor.config.ts` **already exists** in the project root (same folder as `package.json`). You do not need to create it.

**The only thing you need to change** is the server URL. Open `capacitor.config.ts` and replace `https://your-live-server.com` with your actual deployed Django server URL. Also update the matching entry in `allowNavigation`.

```typescript
server: {
  url: 'https://blixtro.sfscollege.app/',      // ← change this
  cleartext: false,
  allowNavigation: ['blixtro.sfscollege.app'],  // ← and this (domain only, no https://)
},
```

Everything else in the file is already configured correctly — app ID, app name, plugins, Android and iOS settings.

**Why `server.url` matters:** Without this, the app loads a blank `localhost` page and nothing works. Setting it to your live server URL makes the WebView load your actual Django app — all pages, APIs, sessions, and cookies work exactly as in the browser.

---

## Part 3 — Create the `www` Folder

Capacitor needs a `www` folder as the web root. Since your app is server-side rendered (Django), this folder just needs a redirect file.

Create a folder called `www` in the project root, then create `www/index.html` with this content:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=/">
  <title>Blixtro IMS</title>
</head>
<body>
  <p>Loading...</p>
</body>
</html>
```

This file is never actually shown to users because `server.url` in `capacitor.config.ts` redirects the WebView to your live server immediately.

---

## Part 4 — Android Setup

### Step 1: Add the Android platform

In the project root terminal, run:

```bash
npx cap add android
```

This creates an `android/` folder in your project.

### Step 2: Sync the project

Every time you change `capacitor.config.ts` or install new plugins, run:

```bash
npx cap sync android
```

### Step 3: Configure Android deep links for Google Auth

Open `android/app/src/main/AndroidManifest.xml` in a text editor.

Find the `<activity>` tag for `MainActivity` and add the following `<intent-filter>` inside it, right after the existing intent filters:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="in.sfscollege.blixtro" android:host="auth" />
</intent-filter>
```

This registers the custom URL scheme `in.sfscollege.blixtro://auth` so the app can catch the Google Auth callback.

### Step 4: Configure network security (allow HTTPS to your server)

Create the file `android/app/src/main/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">blixtro.sfscollege.app</domain>
    </domain-config>
</network-security-config>
```

Then in `AndroidManifest.xml`, inside the `<application>` tag, add:

```xml
android:networkSecurityConfig="@xml/network_security_config"
```

### Step 5: Set minimum SDK version

Open `android/variables.gradle` and make sure these values are set:

```gradle
minSdkVersion = 23
targetSdkVersion = 34
compileSdkVersion = 34
```

### Step 6: Open in Android Studio

Run:

```bash
npx cap open android
```

Android Studio opens. Wait for it to finish syncing Gradle (the progress bar at the bottom).

### Step 7: Build and run

In Android Studio:
- Connect your Android phone via USB with USB Debugging enabled, OR use the emulator.
- Click the green **Run** button (triangle) at the top.
- Select your device and click OK.

The app installs and opens. It loads your live Django server inside the WebView.

---

## Part 5 — iOS Setup (Mac Only)

### Step 1: Add the iOS platform

```bash
npx cap add ios
```

### Step 2: Sync the project

```bash
npx cap sync ios
```

### Step 3: Configure iOS deep links for Google Auth

Open `ios/App/App/Info.plist` in a text editor and add the following inside the root `<dict>`:

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLName</key>
        <string>in.sfscollege.blixtro</string>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>in.sfscollege.blixtro</string>
        </array>
    </dict>
</array>
```

Also add this to allow the app to open external URLs (needed for some auth flows):

```xml
<key>LSApplicationQueriesSchemes</key>
<array>
    <string>https</string>
    <string>http</string>
</array>
```

### Step 4: Open in Xcode

```bash
npx cap open ios
```

Xcode opens. Wait for it to index the project.

### Step 5: Set your Team and Bundle ID

In Xcode:
- Click on the `App` project in the left sidebar.
- Click on the `App` target.
- Go to the **Signing & Capabilities** tab.
- Set your **Team** (your Apple Developer account).
- Set **Bundle Identifier** to `in.sfscollege.blixtro`.

### Step 6: Build and run

- Connect your iPhone via USB.
- Select your device from the device dropdown at the top.
- Click the **Run** button (triangle).

---

## Part 6 — Fixing Google Authentication

The current code tries `signInWithPopup` which does not work in a WebView. Here is the fix.

### How it works after the fix

1. User taps "Sign in with Google".
2. The app opens Google's sign-in page in the **system browser** (not inside the app).
3. After the user signs in, Google redirects to your Django server's `/firebase-login/` callback URL.
4. Your Django server verifies the Firebase token and logs the user in.
5. Because the request came from the Capacitor app (detected via `User-Agent: Capacitor` or `?app=1`), the server redirects to the deep link `in.sfscollege.blixtro://auth?status=success`.
6. The app catches this deep link and the user is now logged in.

### Step 1: Django view — already done

The `firebase_login_callback` view in `src/core/views.py` **already has the Capacitor branch**. No changes needed on the Django side. For reference, the added block looks like this:

```python
# Detects Capacitor via User-Agent or ?app=1 query param
ua = request.META.get('HTTP_USER_AGENT', '')
is_capacitor = 'Capacitor' in ua or request.POST.get('app') == '1'
if is_capacitor:
    from django.http import HttpResponseRedirect
    return HttpResponseRedirect('in.sfscollege.blixtro://auth?status=success')
# Web browser flow — unchanged
return redirect('student:report_issue')
```

The existing web redirect (`student:report_issue`) is completely untouched.

### Step 2: The deep link handler in mobile-utils.js is already set up

The existing `setupDeepLinkHandler()` and `handleDeepLink()` functions in `mobile-utils.js` already listen for `appUrlOpen` events and call `submitAuthToken()`. This part is correct and does not need changes.

### Step 3: signInWithPopup vs signInWithRedirect — already handled

The `capacitorGoogleLogin` function in `mobile-utils.js` already tries `signInWithPopup` first (which works in modern Capacitor WebViews) and automatically falls back to `signInWithRedirect` if the popup is blocked or closed. The redirect fallback opens the system browser and the deep link handler catches the result. No manual change needed here.

---

## Part 7 — Fixing Downloads

All `<a download>` tags in templates have been replaced with `DownloadManager.download()` calls. `DownloadManager` is already defined and globally exposed in `mobile-utils.js`.

How it works:
- **On web:** uses a standard browser download (Blob + anchor click).
- **On Android:** fetches the file, writes it to the Downloads folder via the Filesystem plugin, then opens it.
- **On iOS:** fetches the file, writes to the Documents folder, then uses the Share sheet.

The affected templates were:
- `central_admin/aura_dashboard.html` — image download, PDF download in booking doc panel, PDF download in the inline doc viewer
- `central_admin/edit_request_list.html` — image download, PDF download in the requirements doc panel

If you add new download buttons in the future, use this pattern instead of `<a download>`:

```javascript
// Instead of:
<a href="/download/file.pdf" download>Download</a>

// Use:
<button onclick="DownloadManager.download('/download/file.pdf', 'file.pdf', {mimeType: 'application/pdf', openAfterDownload: false})">Download</button>
```

---

## Part 8 — Fixing Navigation (Home Button, Landing Page Cards)

The home button and landing page cards not rendering is caused by the app loading `localhost` instead of your server. Once you set `server.url` in `capacitor.config.ts` (Part 2), this is fixed automatically — the WebView loads your actual Django pages with all their CSS and JS.

If the home button still appears broken after that fix, it is a CSS safe-area issue. The `room_booking.html` already has the correct safe-area CSS variables. Make sure your `base.html` has this in the `<head>`:

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
```

---

## Part 9 — After Every Code Change

Whenever you change your Django templates or JavaScript:

1. Your changes are live on the server immediately (no rebuild needed — the app loads from the server URL).
2. If you change `capacitor.config.ts` or install new plugins, run `npx cap sync android` (and/or `npx cap sync ios`) then rebuild the app in Android Studio / Xcode.

---

## Part 10 — Building a Signed APK / AAB for Distribution

### Debug APK (for testing only)

In Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**

The APK is saved to `android/app/build/outputs/apk/debug/app-debug.apk`.

### Release APK or AAB (for Google Play)

Google Play requires an **AAB (Android App Bundle)** for new apps. APK is still accepted for direct/sideload distribution.

1. In Android Studio: **Build → Generate Signed Bundle / APK**
2. Choose **Android App Bundle** (for Play Store) or **APK** (for direct distribution).
3. Click **Next**.
4. Under **Key store path**, click **Create new…** if you don't have a keystore yet:
   - Choose a safe location to save the `.jks` file — **back this up, you can never recover it**.
   - Fill in Key store password, Key alias, Key password, and your name/org details.
   - Click **OK**.
5. If you already have a keystore, click **Choose existing…** and select it.
6. Enter your passwords, select the key alias, click **Next**.
7. Choose **release** build variant.
8. Click **Finish**.

The signed AAB is saved to `android/app/release/app-release.aab`.

> **Important:** Never commit your keystore file or passwords to git. Store them securely (password manager, encrypted drive). Losing the keystore means you can never update your Play Store listing — you would have to publish a new app with a new package name.

---

## Part 11 — Publishing to Google Play Store

### Prerequisites

- A **Google Play Developer account** — register at https://play.google.com/console. One-time $25 USD fee.
- A signed AAB built in Part 10.
- App icon (512×512 PNG), feature graphic (1024×500 PNG), and at least 2 screenshots per device type.

### Steps

1. Go to https://play.google.com/console and sign in.
2. Click **Create app**.
3. Fill in app name ("Blixtro IMS"), default language, app/game type, free/paid.
4. Click **Create app**.
5. In the left sidebar, go to **Release → Production → Create new release**.
6. Upload your `.aab` file.
7. Fill in the release notes (what's new).
8. Click **Save**, then **Review release**, then **Start rollout to Production**.
9. Google reviews the app — this typically takes 1–3 days for a new app.

### Store listing checklist

Before submitting, complete these sections in the Play Console:

- **Main store listing** — short description (80 chars), full description (4000 chars), screenshots, icon, feature graphic.
- **Content rating** — complete the questionnaire (takes ~5 minutes).
- **Target audience** — set age group.
- **App content** — data safety form (declare what data the app collects — in this case: email address via Google Sign-In, no data sold to third parties).
- **Pricing & distribution** — set to Free, select countries.

---

## Part 12 — Building for iOS Distribution

### Prerequisites

- An **Apple Developer account** — register at https://developer.apple.com. Annual $99 USD fee.
- A Mac with Xcode installed.
- Your Bundle ID (`in.sfscollege.blixtro`) registered in the Apple Developer portal.

### Steps

1. In Xcode, make sure your **Team** and **Bundle Identifier** are set correctly (Part 5, Step 5).
2. Select **Any iOS Device (arm64)** as the build target (not a simulator).
3. Go to **Product → Archive**.
4. Xcode builds and archives the app. The **Organizer** window opens automatically.
5. Select your archive and click **Distribute App**.
6. Choose **App Store Connect** and click **Next**.
7. Choose **Upload** (sends directly to App Store Connect) or **Export** (saves an IPA file locally).
8. Follow the prompts — Xcode handles signing automatically if you have the right certificates.

### App Store Connect

1. Go to https://appstoreconnect.apple.com and sign in.
2. Click **My Apps → +** to create a new app.
3. Fill in name, primary language, Bundle ID, SKU.
4. Under **App Store → App Information**, fill in subtitle, category, privacy policy URL.
5. Under **Pricing and Availability**, set price to Free.
6. Under **App Store → 1.0 Prepare for Submission**:
   - Upload screenshots (required sizes: 6.7" and 5.5" for iPhone, 12.9" for iPad if supporting iPad).
   - Fill in description, keywords, support URL.
   - Under **Build**, select the build you uploaded from Xcode.
7. Click **Submit for Review**.
8. Apple reviews the app — typically 1–2 days, sometimes up to a week for a new app.

### App Store review tips

- Make sure your privacy policy URL is live and accessible.
- The app must work without requiring a physical device or special network — reviewers test on their own devices. Since your app loads from a live server, ensure the server is up during review.
- If your app requires login, provide a demo account in the **Notes for Reviewer** field.

---

## Part 13 — Quick Reference Commands

| Task | Command |
|------|---------|
| Install dependencies | `npm install` |
| Add Android | `npx cap add android` |
| Add iOS | `npx cap add ios` |
| Sync after changes | `npx cap sync` |
| Open Android Studio | `npx cap open android` |
| Open Xcode | `npx cap open ios` |
| Run on Android device | `npx cap run android` |
| Run on iOS device | `npx cap run ios` |

---

## Troubleshooting

**"App shows blank white screen"**
→ `server.url` in `capacitor.config.ts` is wrong or the server is not reachable. Double-check the URL and make sure your Django server is running and accessible from the phone's network.

**"Google sign-in opens browser but never returns to app"**
→ The deep link URL scheme is not registered. Re-check Part 6 Step 1 (Android) or Part 5 Step 3 (iOS).

**"Downloads say complete but file is not found"**
→ On Android 10+, the app needs `WRITE_EXTERNAL_STORAGE` permission OR must use the MediaStore API. The `mobile-utils.js` `handleDownload` function handles this by falling back to the Cache directory. Make sure you are calling `MobileUtils.handleDownload()` and not a plain anchor tag.

**"Gradle sync failed in Android Studio"**
→ Make sure JDK 17 is set in Android Studio: **File → Project Structure → SDK Location → JDK Location**.

**"CocoaPods install fails on Mac"**
→ Run `sudo gem install cocoapods --pre` or use Homebrew: `brew install cocoapods`.

**"Session/cookies not working in app"**
→ Make sure `server.url` uses `https://` (not `http://`). Django's session cookies require HTTPS in production. Also ensure `SESSION_COOKIE_SAMESITE = 'None'` and `SESSION_COOKIE_SECURE = True` are set in `settings.py` when using a cross-origin WebView.

**"Play Store says 'You need to use a release build'"**
→ Make sure you followed Part 10 and generated a signed AAB/APK, not a debug build.

**"App Store rejects with 'Missing privacy policy'"**
→ Add a publicly accessible privacy policy URL to your App Store Connect listing and in the app itself.
