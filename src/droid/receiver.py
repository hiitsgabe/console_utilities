"""
BroadcastReceiver for Android DownloadManager ACTION_DOWNLOAD_COMPLETE.

Registered dynamically by AndroidDownloadManager. When a download finishes,
this receiver triggers the extraction foreground service.

Uses p4a's android.broadcast.BroadcastReceiver wrapper (not PythonJavaClass,
since BroadcastReceiver is an abstract class, not an interface).
"""


def create_download_complete_receiver(on_download_complete):
    """
    Create and start a BroadcastReceiver for download completions.

    Uses p4a's android.broadcast.BroadcastReceiver which handles the
    Java-side subclassing internally.

    Args:
        on_download_complete: Callback function(download_id: int) called when
            a download finishes.

    Returns:
        The BroadcastReceiver instance. Call stop_receiver() to unregister.
    """
    from android.broadcast import BroadcastReceiver as P4ABroadcastReceiver
    from jnius import autoclass

    DownloadManager = autoclass("android.app.DownloadManager")

    def _on_receive(context, intent):
        download_id = intent.getLongExtra(
            DownloadManager.EXTRA_DOWNLOAD_ID, -1
        )
        if download_id >= 0:
            on_download_complete(download_id)

    receiver = P4ABroadcastReceiver(
        _on_receive,
        actions=[DownloadManager.ACTION_DOWNLOAD_COMPLETE],
    )
    receiver.start()
    return receiver


def stop_receiver(receiver):
    """
    Stop and unregister a previously started BroadcastReceiver.

    Args:
        receiver: The BroadcastReceiver instance to stop
    """
    try:
        receiver.stop()
    except Exception:
        pass
