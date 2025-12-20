"""
Django management command for scraping TikTok profiles.
Based on tiktok-scraper-ytdlp.py
"""

import json
import subprocess
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tiktok.models import Group, TikTokProfile, TikTokVideo


class Command(BaseCommand):
    help = "Scrape TikTok profiles for new posts using yt-dlp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--profiles",
            type=str,
            default="profiles.json",
            help="Path to profiles.json file",
        )
        parser.add_argument(
            "--from-date",
            type=str,
            default=None,
            help="Scrape posts from this date onwards (format: YYYY-MM-DD). If not provided, uses --days",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to check for new posts (default: 30). Ignored if --from-date is provided",
        )
        parser.add_argument(
            "--delay",
            type=int,
            default=15,
            help="Delay in seconds between profile scrapes (default: 15)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Debug mode - scrape only first profile per group",
        )
        parser.add_argument(
            "--use-cookies",
            action="store_true",
            default=True,
            help="Use browser cookies to avoid blocking (default: True)",
        )
        parser.add_argument(
            "--username", type=str, help="Scrape only specific username (e.g., delo.si)"
        )

    def handle(self, *args, **options):
        profiles_file = options["profiles"]
        from_date_str = options.get("from_date")
        days_to_check = options["days"]
        delay = options["delay"]
        debug = options["debug"]
        use_cookies = options["use_cookies"]
        specific_username = options.get("username")

        # Parse from_date if provided
        cutoff_date = None
        if from_date_str:
            try:
                cutoff_date = timezone.make_aware(
                    datetime.strptime(from_date_str, "%Y-%m-%d")
                )
                self.stdout.write(f"Scraping posts from {from_date_str} onwards")
            except ValueError:
                raise CommandError(
                    f"Invalid date format: {from_date_str}. Use YYYY-MM-DD"
                )
        else:
            cutoff_date = timezone.now() - timedelta(days=days_to_check)
            self.stdout.write(f"Scraping posts from last {days_to_check} days")

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Starting TikTok Scraper"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        # Load profiles
        profiles = self.load_profiles(profiles_file, debug)
        if not profiles:
            raise CommandError("No profiles to scrape!")

        # Filter by specific username if provided
        if specific_username:
            profiles = [
                p
                for p in profiles
                if self.extract_username(p["url"]) == specific_username
            ]
            if not profiles:
                raise CommandError(f"Profile @{specific_username} not found!")
            self.stdout.write(self.style.WARNING(f"Scraping only @{specific_username}"))

        # Process each profile
        for idx, profile in enumerate(profiles, 1):
            profile_url = profile["url"]
            profile_name = profile["name"]
            profile_group = profile["group"]

            self.stdout.write(f"\n[{idx}/{len(profiles)}] Processing: {profile_name}")

            username = self.extract_username(profile_url)
            if not username:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not extract username from: {profile_url}"
                    )
                )
                continue

            # Scrape profile
            videos = self.scrape_profile_ytdlp(
                username, profile_url, cutoff_date, use_cookies
            )

            # Save to database
            self.save_to_database(
                username, profile_name, profile_group, profile_url, videos
            )

            # Add delay between profiles
            if idx < len(profiles):
                self.stdout.write(f"Waiting {delay} seconds before next profile...")
                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Scraping completed successfully"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

    def load_profiles(self, profiles_file, debug=False):
        """Load TikTok profiles from JSON file."""
        try:
            with open(profiles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Profiles file '{profiles_file}' not found!")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in profiles file: {e}")

        profiles = []
        for group_name, accounts in data.items():
            for account in accounts[:1] if debug else accounts:
                profiles.append(
                    {
                        "url": account["url"],
                        "name": account["name"],
                        "group": group_name,
                    }
                )

        self.stdout.write(f"Loaded {len(profiles)} profiles from {len(data)} groups")
        return profiles

    def extract_username(self, profile_url):
        """Extract username from TikTok profile URL."""
        if "@" in profile_url:
            username = profile_url.split("@")[-1]
            username = username.split("?")[0].strip("/")
            return username
        return None

    def clean_profile_url(self, profile_url):
        """Clean profile URL by removing query parameters."""
        if "?" in profile_url:
            return profile_url.split("?")[0]
        return profile_url

    def scrape_profile_ytdlp(self, username, url, cutoff_date, use_cookies=True):
        """Scrape posts from a TikTok profile using yt-dlp."""
        self.stdout.write(f"Scraping profile: @{username}")

        clean_url = self.clean_profile_url(url)
        videos = []

        try:
            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--print",
                "%(id)s|%(title)s|%(upload_date)s|%(like_count)s|%(view_count)s|%(comment_count)s|%(repost_count)s",
                "--playlist-end",
                "50",
                "--sleep-requests",
                "3",
                "--extractor-retries",
                "3",
            ]

            # Add cookies if requested
            if use_cookies:
                try:
                    import secretstorage

                    cmd.extend(["--cookies-from-browser", "chrome"])
                    self.stdout.write("  Using cookies from Chrome")
                except ImportError:
                    self.stdout.write(
                        self.style.WARNING(
                            "  secretstorage not installed, continuing without cookies"
                        )
                    )

            cmd.append(clean_url)

            self.stdout.write("  Running yt-dlp command...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                stderr = result.stderr.lower()
                if "error:" in stderr and "warning:" not in stderr:
                    self.stdout.write(
                        self.style.ERROR(f"  yt-dlp failed: {result.stderr}")
                    )
                    return []
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  yt-dlp warnings: {result.stderr[:200]}")
                    )
                    if not result.stdout.strip():
                        return []

            # Parse output
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                try:
                    parts = line.split("|")
                    if len(parts) < 6:
                        continue

                    video_id = parts[0]
                    title = parts[1]
                    upload_date_str = parts[2]
                    likes = parts[3]
                    views = parts[4]
                    comments = parts[5]
                    shares = parts[6] if len(parts) > 6 else "NA"

                    # Parse upload date
                    if upload_date_str and upload_date_str != "NA":
                        year = int(upload_date_str[:4])
                        month = int(upload_date_str[4:6])
                        day = int(upload_date_str[6:8])
                        post_date = timezone.make_aware(datetime(year, month, day))

                        # Check if video is recent enough (on or after cutoff_date)
                        if post_date < cutoff_date:
                            continue

                        video_info = {
                            "id": video_id,
                            "description": title,
                            "post_date": post_date,
                            "stats": {
                                "play_count": (
                                    int(views) if views and views != "NA" else 0
                                ),
                                "like_count": (
                                    int(likes) if likes and likes != "NA" else 0
                                ),
                                "comment_count": (
                                    int(comments)
                                    if comments and comments != "NA"
                                    else 0
                                ),
                                "share_count": (
                                    int(shares) if shares and shares != "NA" else 0
                                ),
                            },
                            "video_url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                        }

                        videos.append(video_info)
                        self.stdout.write(f"  Found video: {video_id}")

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Error parsing line: {e}"))
                    continue

            self.stdout.write(f"  Total videos found: {len(videos)}")
            return videos

        except subprocess.TimeoutExpired:
            self.stdout.write(self.style.ERROR(f"  yt-dlp timeout for @{username}"))
            return []
        except FileNotFoundError:
            raise CommandError("yt-dlp not found! Install with: pip install yt-dlp")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Error scraping @{username}: {e}"))
            return []

    @transaction.atomic
    def save_to_database(
        self, username, profile_name, profile_group, profile_url, videos
    ):
        """Save scraped data to database."""
        # Get or create group
        group, _ = Group.objects.get_or_create(name=profile_group)

        # Get or create profile
        profile, created = TikTokProfile.objects.get_or_create(
            username=username,
            defaults={
                "profile_url": profile_url,
                "name": profile_name,
            },
        )

        # Update profile info and add group
        profile.name = profile_name
        profile.profile_url = profile_url
        profile.save()
        profile.groups.add(group)

        new_count = 0
        updated_count = 0

        # Process videos
        for video_data in videos:
            video, created = TikTokVideo.objects.update_or_create(
                video_id=video_data["id"],
                defaults={
                    "profile": profile,
                    "description": video_data["description"],
                    "video_url": video_data["video_url"],
                    "play_count": video_data["stats"]["play_count"],
                    "like_count": video_data["stats"]["like_count"],
                    "comment_count": video_data["stats"]["comment_count"],
                    "share_count": video_data["stats"]["share_count"],
                    "posted_at": video_data["post_date"],
                },
            )

            if created:
                new_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  Added {new_count} new videos, updated {updated_count} existing videos for @{username} ({profile_name})"
            )
        )
