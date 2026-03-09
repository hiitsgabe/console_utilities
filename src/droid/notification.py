"""
Android notification helpers for the extraction foreground service.

All pyjnius/android imports are deferred to function scope — this module
is never imported on desktop/macOS/Windows/console.

IMPORTANT: notification functions accept a `context` parameter because
the service runs in a separate process where PythonActivity.mActivity
is None. The service must pass PythonService.mService as context.
"""

CHANNEL_ID = "consoleutilities_extraction"
CHANNEL_NAME = "Extraction Progress"
NOTIFICATION_ID = 9001

DOWNLOAD_CHANNEL_ID = "consoleutilities_download"
DOWNLOAD_CHANNEL_NAME = "Download Progress"
DOWNLOAD_NOTIFICATION_ID = 9002


def create_notification_channel(context):
    """
    Create the notification channel required for Android 8+ (API 26+).

    Must be called before showing any foreground service notification.

    Args:
        context: Android Context (PythonService.mService or PythonActivity.mActivity)
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationChannel = autoclass("android.app.NotificationChannel")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    channel = NotificationChannel(
        CHANNEL_ID,
        CHANNEL_NAME,
        NotificationManager.IMPORTANCE_LOW,
    )
    channel.setDescription("Shows extraction progress for downloaded games")
    manager.createNotificationChannel(channel)


def build_extraction_notification(context, title, progress=-1, max_progress=100):
    """
    Build a Notification for the foreground extraction service.

    Args:
        context: Android Context (PythonService.mService or PythonActivity.mActivity)
        title: Notification title text (e.g., "Extracting game.zip...")
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value

    Returns:
        Android Notification object
    """
    from jnius import autoclass

    NotificationBuilder = autoclass("android.app.Notification$Builder")

    builder = NotificationBuilder(context, CHANNEL_ID)
    builder.setContentTitle(title)
    builder.setSmallIcon(context.getApplicationInfo().icon)
    builder.setOngoing(True)

    if progress >= 0:
        builder.setProgress(max_progress, progress, False)
        pct = int(progress * 100 / max_progress) if max_progress > 0 else 0
        builder.setContentText(f"{pct}%")
    else:
        builder.setProgress(0, 0, True)
        builder.setContentText("Preparing...")

    return builder.build()


def update_notification(context, title, progress=-1, max_progress=100):
    """
    Update the existing foreground service notification.

    Args:
        context: Android Context (PythonService.mService or PythonActivity.mActivity)
        title: Updated title text
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    notification = build_extraction_notification(context, title, progress, max_progress)
    manager.notify(NOTIFICATION_ID, notification)


def create_download_notification_channel(context):
    """
    Create the notification channel for download progress.

    Args:
        context: Android Context (PythonService.mService)
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationChannel = autoclass("android.app.NotificationChannel")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    channel = NotificationChannel(
        DOWNLOAD_CHANNEL_ID,
        DOWNLOAD_CHANNEL_NAME,
        NotificationManager.IMPORTANCE_LOW,
    )
    channel.setDescription("Shows download progress for games")
    manager.createNotificationChannel(channel)


def build_download_notification(context, title, progress=-1, max_progress=100):
    """
    Build a Notification for the download foreground service.

    Args:
        context: Android Context (PythonService.mService)
        title: Notification title text
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value

    Returns:
        Android Notification object
    """
    from jnius import autoclass

    NotificationBuilder = autoclass("android.app.Notification$Builder")

    builder = NotificationBuilder(context, DOWNLOAD_CHANNEL_ID)
    builder.setContentTitle(title)
    builder.setSmallIcon(context.getApplicationInfo().icon)
    builder.setOngoing(True)

    if progress >= 0:
        builder.setProgress(max_progress, progress, False)
        pct = int(progress * 100 / max_progress) if max_progress > 0 else 0
        builder.setContentText(f"{pct}%")
    else:
        builder.setProgress(0, 0, True)
        builder.setContentText("Starting download...")

    return builder.build()


def update_download_notification(context, title, progress=-1, max_progress=100):
    """
    Update the existing download foreground service notification.

    Args:
        context: Android Context (PythonService.mService)
        title: Updated title text
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    notification = build_download_notification(context, title, progress, max_progress)
    manager.notify(DOWNLOAD_NOTIFICATION_ID, notification)
