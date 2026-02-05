from pathlib import Path
from django.http import FileResponse, Http404
from django.conf import settings


def export(request):
    """Download the latest export file."""
    exports_dir = Path(settings.BASE_DIR) / "exports"
    
    if not exports_dir.exists():
        raise Http404("No exports directory found")
    
    # Get latest export file
    export_files = sorted(exports_dir.glob("tiktok_data_*.json"), reverse=True)
    
    if not export_files:
        raise Http404("No export files found")
    
    latest_file = export_files[0]
    
    return FileResponse(
        open(latest_file, 'rb'),
        as_attachment=True,
        filename=latest_file.name,
        content_type='application/json'
    )
