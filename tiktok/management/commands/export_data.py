import json
import os
from datetime import datetime
from pathlib import Path
from io import BytesIO

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings

from tiktok.models import TikTokProfile, TikTokVideo, TikTokComment, Group, Export


class Command(BaseCommand):
    help = "Export TikTok data (profiles, videos, comments) to JSON file for analysis"

    def handle(self, *args, **options):
        self.stdout.write("Starting data export...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tiktok_data_{timestamp}.json"

        # Collect data
        self.stdout.write("Fetching profiles...")
        profiles_data = self._export_profiles()

        self.stdout.write("Fetching videos...")
        videos_data = self._export_videos()

        self.stdout.write("Fetching comments...")
        comments_data = self._export_comments()

        # Build final structure
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "statistics": {
                "total_groups": Group.objects.count(),
                "total_profiles": len(profiles_data),
                "total_videos": len(videos_data),
                "total_comments": len(comments_data),
            },
            "groups": self._export_groups(),
            "profiles": profiles_data,
            "videos": videos_data,
            "comments": comments_data,
        }

        # Convert to JSON string
        self.stdout.write("Preparing export file...")
        json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
        json_bytes = json_data.encode('utf-8')
        file_size_bytes = len(json_bytes)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # Create Export model instance and save to S3
        self.stdout.write("Uploading to S3...")
        export = Export.objects.create(
            file_size_bytes=file_size_bytes,
            total_groups=export_data['statistics']['total_groups'],
            total_profiles=export_data['statistics']['total_profiles'],
            total_videos=export_data['statistics']['total_videos'],
            total_comments=export_data['statistics']['total_comments'],
        )
        
        # Save the file (will use S3 if configured)
        export.file.save(filename, ContentFile(json_bytes), save=True)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Export complete: {export.file.name} ({file_size_mb:.2f} MB)"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export.total_profiles} profiles"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export.total_videos} videos"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export.total_comments} comments"
            )
        )
        if hasattr(export.file, 'url'):
            self.stdout.write(
                self.style.SUCCESS(
                    f"  - URL: {export.file.url}"
                )
            )

    def _export_groups(self):
        """Export all groups."""
        groups = []
        for group in Group.objects.all():
            groups.append(
                {
                    "id": group.id,
                    "name": group.name,
                    "created_at": group.created_at.isoformat(),
                }
            )
        return groups

    def _export_profiles(self):
        """Export all profiles with their group associations."""
        profiles = []
        for profile in TikTokProfile.objects.prefetch_related("groups").all():
            profiles.append(
                {
                    "id": profile.id,
                    "username": profile.username,
                    "name": profile.name,
                    "profile_url": profile.profile_url,
                    "full_name": profile.full_name,
                    "bio": profile.bio,
                    "followers_count": profile.followers_count,
                    "following_count": profile.following_count,
                    "likes_count": profile.likes_count,
                    "groups": [group.name for group in profile.groups.all()],
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat(),
                }
            )
        return profiles

    def _export_videos(self):
        """Export all videos with profile info."""
        videos = []
        for video in TikTokVideo.objects.select_related("profile").all():
            videos.append(
                {
                    "id": video.id,
                    "video_id": video.video_id,
                    "video_url": video.video_url,
                    "description": video.description,
                    "profile_username": video.profile.username,
                    "profile_id": video.profile.id,
                    "play_count": video.play_count,
                    "like_count": video.like_count,
                    "comment_count": video.comment_count,
                    "share_count": video.share_count,
                    "posted_at": (
                        video.posted_at.isoformat() if video.posted_at else None
                    ),
                    "created_at": video.created_at.isoformat(),
                    "updated_at": video.updated_at.isoformat(),
                }
            )
        return videos

    def _export_comments(self):
        """Export all comments with video and parent info."""
        comments = []
        for comment in TikTokComment.objects.select_related(
            "video", "parent_comment"
        ).all():
            comments.append(
                {
                    "id": comment.id,
                    "comment_id": comment.comment_id,
                    "content": comment.content,
                    "author_username": comment.author_username,
                    "author_nickname": comment.author_nickname,
                    "avatar_url": comment.avatar_url,
                    "video_id": comment.video.video_id,
                    "video_internal_id": comment.video.id,
                    "parent_comment_id": (
                        comment.parent_comment.comment_id
                        if comment.parent_comment
                        else None
                    ),
                    "like_count": comment.like_count,
                    "reply_count": comment.reply_count,
                    "posted_at": (
                        comment.posted_at.isoformat() if comment.posted_at else None
                    ),
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat(),
                }
            )
        return comments
