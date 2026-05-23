#!/usr/bin/env python3
"""Patch p4a AndroidManifest template to include FileProvider.

buildozer's extra_manifest_application_arguments injects content inside the
opening <application> tag (as attributes), but FileProvider needs to be a
child element. This script patches the template directly.
"""
import pathlib
import sys

# p4a's SDL2 bootstrap template path changed over time. Recent master shares
# the manifest between sdl2 and sdl3 via _sdl_common; older checkouts kept it
# under sdl2/. Patch whichever exists.
CANDIDATE_TEMPLATES = (
    '/p4a/pythonforandroid/bootstraps/_sdl_common/build/templates/AndroidManifest.tmpl.xml',
    '/p4a/pythonforandroid/bootstraps/sdl2/build/templates/AndroidManifest.tmpl.xml',
)

PROVIDER_XML = (
    '    <provider android:name="androidx.core.content.FileProvider"'
    ' android:authorities="${applicationId}.fileprovider"'
    ' android:exported="false"'
    ' android:grantUriPermissions="true">'
    '<meta-data android:name="android.support.FILE_PROVIDER_PATHS"'
    ' android:resource="@xml/file_paths" />'
    '</provider>\n'
)

for path in CANDIDATE_TEMPLATES:
    tmpl = pathlib.Path(path)
    if tmpl.exists():
        content = tmpl.read_text()
        content = content.replace('    </application>', PROVIDER_XML + '    </application>')
        tmpl.write_text(content)
        print(f'FileProvider injected into {path}')
        break
else:
    sys.stderr.write(
        'patch_manifest.py: AndroidManifest template not found in any known '
        'p4a bootstrap path. Looked in:\n'
        + '\n'.join(f'  - {p}' for p in CANDIDATE_TEMPLATES)
        + '\n'
    )
    sys.exit(1)
