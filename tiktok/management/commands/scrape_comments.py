"""
Django management command for scraping TikTok video comments.
Based on tiktok-comment-scrapper library by RomySaputraSihananda
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import jmespath
import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tiktok.models import TikTokComment, TikTokVideo


class TikTokCommentScraper:
    """Wrapper for TikTok comment scraping API."""

    BASE_URL = "https://www.tiktok.com"
    API_URL = f"{BASE_URL}/api"

    def __init__(self):
        self.session = requests.Session()
        self.aweme_id = None

    def _parse_comment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse comment data using jmespath."""
        parsed = jmespath.search(
            """
            {
                comment_id: cid,
                username: user.unique_id,
                nickname: user.nickname,
                comment: text,
                create_time: create_time,
                avatar: user.avatar_thumb.url_list[0],
                total_reply: reply_comment_total,
                like_count: digg_count
            }
            """,
            data,
        )
        return parsed

    def get_replies(
        self, comment_id: str, size: int = 50, page: int = 1
    ) -> List[Dict[str, Any]]:
        """Get replies for a specific comment."""
        try:
            response = self.session.get(
                f"{self.API_URL}/comment/list/reply/",
                params={
                    "aid": 1988,
                    "comment_id": comment_id,
                    "item_id": self.aweme_id,
                    "count": size,
                    "cursor": (page - 1) * size,
                },
                timeout=30,
            )
            response.raise_for_status()

            comments = response.json().get("comments", [])
            return [self._parse_comment(comment) for comment in comments]
        except Exception as e:
            print(f"  Error getting replies for comment {comment_id}: {e}")
            return []

    def get_all_replies(self, comment_id: str) -> List[Dict[str, Any]]:
        """Get all replies for a comment (paginated)."""
        all_replies = []
        page = 1

        while True:
            replies = self.get_replies(comment_id=comment_id, page=page)
            if not replies:
                break

            all_replies.extend(replies)
            page += 1
            time.sleep(0.5)  # Small delay between pages

        return all_replies

    def get_comments(
        self, aweme_id: str, size: int = 50, page: int = 1
    ) -> Dict[str, Any]:
        """Get comments for a video."""
        self.aweme_id = aweme_id

        try:
            response = self.session.get(
                f"{self.API_URL}/comment/list/",
                params={
                    "aid": 1988,
                    "aweme_id": aweme_id,
                    "count": size,
                    "cursor": (page - 1) * size,
                },
                timeout=30,
            )
            response.raise_for_status()

            data = jmespath.search(
                """
                {
                    caption: comments[0].share_info.title,
                    video_url: comments[0].share_info.url,
                    comments: comments,
                    has_more: has_more
                }
                """,
                response.json(),
            )

            if not data or "comments" not in data:
                return {"comments": [], "has_more": 0}

            parsed_comments = []
            for comment in data["comments"]:
                parsed = self._parse_comment(comment)
                if parsed:
                    # Get replies if there are any
                    if parsed.get("total_reply", 0) > 0:
                        parsed["replies"] = self.get_all_replies(parsed["comment_id"])
                    else:
                        parsed["replies"] = []
                    parsed_comments.append(parsed)

            return {
                "caption": data.get("caption", ""),
                "video_url": data.get("video_url", ""),
                "comments": parsed_comments,
                "has_more": data.get("has_more", 0),
            }

        except Exception as e:
            print(f"  Error getting comments for video {aweme_id}: {e}")
            return {"comments": [], "has_more": 0}

    def get_all_comments(self, aweme_id: str) -> Dict[str, Any]:
        """Get all comments for a video (paginated)."""
        page = 1
        data = self.get_comments(aweme_id=aweme_id, page=page)
        all_comments = data["comments"]

        while data.get("has_more", 0) == 1:
            page += 1
            time.sleep(1)  # Delay between requests

            next_data = self.get_comments(aweme_id=aweme_id, page=page)
            if not next_data["comments"]:
                break

            all_comments.extend(next_data["comments"])
            data["has_more"] = next_data.get("has_more", 0)

        data["comments"] = all_comments
        return data


class Command(BaseCommand):
    help = "Scrape comments for TikTok videos in database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--video-id", type=str, help="Scrape comments for specific video ID"
        )
        parser.add_argument(
            "--profile",
            type=str,
            help="Scrape comments for all videos from specific profile username",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Limit number of videos to process"
        )
        parser.add_argument(
            "--delay",
            type=int,
            default=2,
            help="Delay in seconds between video scrapes (default: 2)",
        )

    def handle(self, *args, **options):
        video_id = options.get("video_id")
        profile_username = options.get("profile")
        limit = options.get("limit")
        delay = options.get("delay")

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Starting TikTok Comment Scraper"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        # Get videos to process
        videos = TikTokVideo.objects.all()

        if video_id:
            videos = videos.filter(video_id=video_id)
            if not videos.exists():
                raise CommandError(f"Video {video_id} not found in database!")

        if profile_username:
            videos = videos.filter(profile__username=profile_username)
            if not videos.exists():
                raise CommandError(f"No videos found for profile @{profile_username}!")

        videos = videos.order_by("-posted_at")

        if limit:
            videos = videos[:limit]

        total = videos.count()
        self.stdout.write(f"Found {total} videos to process")

        # Initialize scraper
        scraper = TikTokCommentScraper()

        # Process each video
        for idx, video in enumerate(videos, 1):
            self.stdout.write(f"\n[{idx}/{total}] Processing video: {video.video_id}")
            self.stdout.write(f"  Profile: @{video.profile.username}")
            self.stdout.write(f"  URL: {video.video_url}")

            # Scrape comments
            result = scraper.get_all_comments(video.video_id)

            if not result["comments"]:
                self.stdout.write(self.style.WARNING("  No comments found"))
                continue

            # Save to database
            saved_count = self.save_comments(video, result["comments"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Saved {saved_count} comments (including replies)"
                )
            )

            # Delay between videos
            if idx < total:
                self.stdout.write(f"  Waiting {delay} seconds before next video...")
                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Comment scraping completed"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

    @transaction.atomic
    def save_comments(self, video: TikTokVideo, comments: List[Dict[str, Any]]) -> int:
        """Save comments and replies to database."""
        saved_count = 0

        for comment_data in comments:
            # Save main comment
            comment, created = TikTokComment.objects.update_or_create(
                comment_id=comment_data["comment_id"],
                defaults={
                    "video": video,
                    "author_username": comment_data.get("username", ""),
                    "author_nickname": comment_data.get("nickname", ""),
                    "content": comment_data.get("comment", ""),
                    "like_count": comment_data.get("like_count", 0),
                    "reply_count": comment_data.get("total_reply", 0),
                    "avatar_url": comment_data.get("avatar", ""),
                    "posted_at": (
                        timezone.make_aware(
                            datetime.fromtimestamp(comment_data["create_time"])
                        )
                        if comment_data.get("create_time")
                        else None
                    ),
                    "parent_comment": None,
                },
            )
            saved_count += 1

            # Save replies
            for reply_data in comment_data.get("replies", []):
                reply, _ = TikTokComment.objects.update_or_create(
                    comment_id=reply_data["comment_id"],
                    defaults={
                        "video": video,
                        "author_username": reply_data.get("username", ""),
                        "author_nickname": reply_data.get("nickname", ""),
                        "content": reply_data.get("comment", ""),
                        "like_count": reply_data.get("like_count", 0),
                        "reply_count": 0,
                        "avatar_url": reply_data.get("avatar", ""),
                        "posted_at": (
                            timezone.make_aware(
                                datetime.fromtimestamp(reply_data["create_time"])
                            )
                            if reply_data.get("create_time")
                            else None
                        ),
                        "parent_comment": comment,
                    },
                )
                saved_count += 1

        return saved_count
