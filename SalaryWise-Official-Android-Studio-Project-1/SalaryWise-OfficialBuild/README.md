# SalaryWise — officially buildable Android project

A Java Android WebView shell that bundles the full offline SalaryWise budgeting UI.
Uses Android platform WebView, no external runtime libraries or server, and stores
financial data in local WebView storage. Export/import uses the Android document picker.

## Generate a genuine Gradle-compiled APK

Open in Android Studio (AGP 8.7.3, SDK 35, JDK 17); choose **Build > Build APK(s)**.
Result: `app/build/outputs/apk/debug/app-debug.apk`.

Alternatively, upload to a GitHub repository. The included **Actions → Build and launch-test SalaryWise APK** workflow compiles and tests
launching on an API 35 emulator before releasing the Android debug APK artifact.
It does not test Android 17 Pixel devices.

## Important

This project has not been built/tested in the ChatGPT container because Android SDK
and external downloads are unavailable. The previously shared hand-assembled APKs
are NOT proof of an Android 17 runtime launch test. Use the Android Studio/CI build.

## Budgeting functions

Set monthly salary, monthly savings and planned SIP. Record expenses and SIP by date,
manage category limits, see safe-to-spend and daily caps, view past months, and
calculate savings, SIP return scenarios, and lifestyle funds. Investment returns
are illustrative estimates, not guaranteed returns.
