# Android On-Device Verification Checklist

Use this checklist before release and after any auth/download/navigation changes.

## Preconditions
- Install latest APK built from current branch.
- Ensure backend URL in `capacitor.config.ts` points to production/app server.
- Device has internet and Google account available.

## 1) App Landing Route
- Launch app from Android home screen.
- Verify first screen opens app home flow (not generic website landing).
- Expected: app starts from `core/app` path and remains inside app WebView.

## 2) Google Login (In-App and Browser-Fallback)
- Open student portal login screen in app.
- Tap Google login and complete authentication.
- Verify successful login returns to app and opens student issue reporting page.
- Force browser/fallback login path (if popup closes/redirect path used).
- Verify completion still deep-links back into app and lands on issue reporting page.

## 3) Student URL Compatibility
- Open old path in browser/app context: `/student/portal/`.
- Verify redirect to `/students/portal/` succeeds without 404.
- Verify `/students/report_issue/`, `/students/track_ticket/`, and `/students/portal/` all load.

## 4) Download Behavior
- Trigger a report/document download from app.
- Verify one of these outcomes:
  - File is saved successfully and success toast is shown, or
  - Browser fallback opens and download starts without app crash.
- Verify app remains usable after download action.

## 5) Rooms Mobile Actions UI
- Open rooms list on mobile viewport/device.
- Check action buttons in list view and card view.
- Expected: Edit/Delete actions stack vertically and stay inside card/row width.

## 6) Regression Sanity (Web Browser)
- Verify web browser login still works.
- Verify student portal/login/report pages load normally.
- Verify no redirect loops for non-app browser users.

## Pass Criteria
- No 404s for student routes.
- No login dead-ends.
- No app exit/crash during auth or download.
- Room action buttons are fully visible and tappable on mobile.
