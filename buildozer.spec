[app]
title = Console Utilities
package.name = consoleutilities
package.domain = com.consoleutilities
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf
source.include_patterns = src/**/*.py,assets/**/*,recipes/**/*
version = 0.1
requirements = python3==3.10.12,kivy==2.3.0,pyjnius==1.5.0,hostpython3==3.10.12,pygame,requests,rarfile,zstandard==0.21.0,pycryptodome,jnius,android
orientation = landscape, portrait
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
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE,WAKE_LOCK,MANAGE_EXTERNAL_STORAGE,DOWNLOAD_WITHOUT_NOTIFICATION,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,REQUEST_INSTALL_PACKAGES
services = ExtractionService:./src/droid/service.py:foreground:sticky
icon.filename = icon.png
presplash.filename = presplash.png
android.presplash_color = #ffffff
p4a.local_recipes = ./recipes
p4a.source_dir = /p4a
android.add_resources = res/xml/file_paths.xml:xml/file_paths.xml
android.gradle_dependencies = androidx.core:core:1.6.0
android.release_artifact = apk
android.keystore = keystore/release.keystore
android.keyalias = consoleutilities

[buildozer]
log_level = 2
warn_on_root = 1
