[app]
title = Console Utilities
package.name = consoleutilities
package.domain = com.consoleutilities
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.10.12,kivy==2.3.0,pyjnius==1.5.0,hostpython3==3.10.12,pygame,requests,zstandard,pycryptodomex
orientation = landscape
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0
ios.codesign.allowed = false
android.accept_sdk_license = True
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE,WAKE_LOCK,MANAGE_EXTERNAL_STORAGE,DOWNLOAD_WITHOUT_NOTIFICATION,POST_NOTIFICATIONS
icon.filename = icon.png
presplash.filename = presplash.png
android.presplash_color = #ffffff

[buildozer]
log_level = 1
warn_on_root = 1
