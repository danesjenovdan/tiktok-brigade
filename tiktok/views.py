from django.http import FileResponse, Http404, JsonResponse
from django.conf import settings
from tiktok.models import Export


def export(request):
    """Download or return info about the latest export file."""

    try:
        latest_export = Export.objects.latest("exported_at")
    except Export.DoesNotExist:
        raise Http404("No export files found")

    if not latest_export.file:
        raise Http404("Export file not found")

    # For S3, redirect to URL. For local, serve file
    if settings.AWS_STORAGE_BUCKET_NAME:
        # S3 - redirect to signed URL
        from django.shortcuts import redirect

        return redirect(latest_export.file.url)
    else:
        # Local file - serve directly
        return FileResponse(
            latest_export.file.open("rb"),
            as_attachment=True,
            filename=latest_export.file.name.split("/")[-1],
            content_type="application/json",
        )
