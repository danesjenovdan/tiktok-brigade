import json
import os
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from tiktok.models import TikTokProfile, TikTokVideo, TikTokComment, Group


class Command(BaseCommand):
    help = "Export TikTok data (profiles, videos, comments) to JSON file for analysis"

    def handle(self, *args, **options):
        self.stdout.write("Starting data export...")

        # Prepare export directory
        exports_dir = Path(settings.BASE_DIR) / "exports"
        exports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = exports_dir / f"tiktok_data_{timestamp}.json"

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

        # Write to file
        self.stdout.write(f"Writing to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        
        # Delete old exports after successful new export
        for old_file in exports_dir.glob("tiktok_data_*.json"):
            if old_file != output_path:
                old_file.unlink()
                self.stdout.write(f"Deleted old export: {old_file.name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Export complete: {output_path} ({file_size_mb:.2f} MB)"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export_data['statistics']['total_profiles']} profiles"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export_data['statistics']['total_videos']} videos"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {export_data['statistics']['total_comments']} comments"
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
