package com.salarywise.android;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public final class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 7001;
    private static final int JSON_EXPORT_REQUEST = 7002;
    private static final String BASE_URL = "https://appassets.androidplatform.net/";
    private WebView webView;
    private ValueCallback<Uri[]> fileChooserCallback;
    private String pendingBackup;

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            webView = new WebView(this);
            WebSettings settings = webView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(false);
            settings.setAllowContentAccess(true);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            webView.setWebViewClient(new WebViewClient() {
                @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    // Keep navigation inside the local finance app only.
                    return !BASE_URL.equals(request.getUrl().toString());
                }
            });
            webView.setWebChromeClient(new WebChromeClient() {
                @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback,
                        FileChooserParams params) {
                    if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
                    fileChooserCallback = callback;
                    try {
                        startActivityForResult(params.createIntent(), FILE_CHOOSER_REQUEST);
                        return true;
                    } catch (ActivityNotFoundException e) {
                        fileChooserCallback = null;
                        callback.onReceiveValue(null);
                        Toast.makeText(MainActivity.this, "File picker unavailable", Toast.LENGTH_LONG).show();
                        return false;
                    }
                }
            });
            webView.addJavascriptInterface(new BackupBridge(), "SalaryWiseAndroid");
            setContentView(webView);
            try (InputStream input = getAssets().open("index.html");
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
                webView.loadDataWithBaseURL(BASE_URL,
                        output.toString(StandardCharsets.UTF_8.name()), "text/html", "UTF-8", null);
            }
        } catch (Exception e) {
            // Surface startup errors instead of silently exiting on a blank screen.
            android.widget.TextView error = new android.widget.TextView(this);
            error.setPadding(24, 32, 24, 24);
            error.setText("SalaryWise couldn't start. Please send this message to support:\n" +
                    e.getClass().getSimpleName() + ": " + e.getMessage());
            setContentView(error);
        }
    }

    private final class BackupBridge {
        @JavascriptInterface public void saveJson(String json) {
            if (json == null || json.length() > 5_000_000) return;
            runOnUiThread(() -> {
                pendingBackup = json;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/json");
                intent.putExtra(Intent.EXTRA_TITLE, "SalaryWise-backup.json");
                try { startActivityForResult(intent, JSON_EXPORT_REQUEST); }
                catch (ActivityNotFoundException e) {
                    Toast.makeText(MainActivity.this, "Save dialog unavailable", Toast.LENGTH_LONG).show();
                    pendingBackup = null;
                }
            });
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (fileChooserCallback != null) {
                fileChooserCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
                fileChooserCallback = null;
            }
        } else if (requestCode == JSON_EXPORT_REQUEST) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingBackup != null) {
                try (OutputStream output = getContentResolver().openOutputStream(data.getData())) {
                    if (output == null) throw new java.io.IOException("Cannot open output");
                    output.write(pendingBackup.getBytes(StandardCharsets.UTF_8));
                    Toast.makeText(this, "Backup saved", Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    Toast.makeText(this, "Backup couldn't be saved", Toast.LENGTH_LONG).show();
                }
            }
            pendingBackup = null;
        }
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (fileChooserCallback != null) {
            fileChooserCallback.onReceiveValue(null);
            fileChooserCallback = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("SalaryWiseAndroid");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
