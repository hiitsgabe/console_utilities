#!/usr/bin/env python3
"""Patch p4a AndroidManifest template to include FileProvider.

buildozer's extra_manifest_application_arguments injects content inside the
opening <application> tag (as attributes), but FileProvider needs to be a
child element. This script patches the template directly.
"""
import pathlib

TEMPLATE = '/p4a/pythonforandroid/bootstraps/sdl2/build/templates/AndroidManifest.tmpl.xml'

PROVIDER_XML = (
    '    <provider android:name="androidx.core.content.FileProvider"'
    ' android:authorities="${applicationId}.fileprovider"'
    ' android:exported="false"'
    ' android:grantUriPermissions="true">'
    '<meta-data android:name="android.support.FILE_PROVIDER_PATHS"'
    ' android:resource="@xml/file_paths" />'
    '</provider>\n'
)

tmpl = pathlib.Path(TEMPLATE)
content = tmpl.read_text()
content = content.replace('    </application>', PROVIDER_XML + '    </application>')
tmpl.write_text(content)
print('FileProvider injected into AndroidManifest template')
