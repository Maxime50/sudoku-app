[app]

title = Sudoku
package.name = sudoku
package.domain = org.sudoku.app

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json
source.exclude_exts = spec
source.exclude_dirs = tests, bin, venv, __pycache__, .github

version = 1.0

requirements = python3,kivy==2.3.0,pillow

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #F4F6FB

android.permissions = INTERNET

android.api = 33
android.minapi = 21
android.ndk_api = 21
android.ndk = 25b

android.accept_sdk_license = True
android.release_artifact = apk
android.debug_artifact = apk

android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
