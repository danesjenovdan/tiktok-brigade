from django.db import models

# Create your models here.


class Timestampable(models.Model):
    """Abstract base class with timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Group(Timestampable):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Group"
        verbose_name_plural = "Groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TikTokProfile(Timestampable):
    username = models.CharField(max_length=255, unique=True)
    name = models.CharField(
        max_length=255, blank=True, null=True
    )  # Display name from profiles.json
    groups = models.ManyToManyField(Group, related_name="profiles", blank=True)
    profile_url = models.URLField(blank=True, null=True)

    # Optional profile stats (if we scrape profile page in future)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    followers_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)
    likes_count = models.IntegerField(default=0)

    class Meta:
        verbose_name = "TikTok Profile"
        verbose_name_plural = "TikTok Profiles"
        ordering = ["username"]

    def __str__(self):
        return f"@{self.username}" + (f" ({self.name})" if self.name else "")


class TikTokVideo(Timestampable):
    profile = models.ForeignKey(
        TikTokProfile, on_delete=models.CASCADE, related_name="videos"
    )
    video_id = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    video_url = models.URLField()

    # Video stats
    play_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)

    # Timestamps
    posted_at = models.DateTimeField(
        null=True, blank=True
    )  # When video was posted on TikTok
    # created_at and updated_at inherited from Timestampable

    class Meta:
        verbose_name = "TikTok Video"
        verbose_name_plural = "TikTok Videos"
        ordering = ["-posted_at"]

    def __str__(self):
        return f"@{self.profile.username} - {self.video_id}"


class TikTokComment(Timestampable):
    video = models.ForeignKey(
        TikTokVideo, on_delete=models.CASCADE, related_name="comments"
    )
    comment_id = models.CharField(max_length=255, unique=True, db_index=True)
    author_username = models.CharField(max_length=255)
    author_nickname = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    like_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    avatar_url = models.URLField(blank=True)

    # For nested replies
    parent_comment = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True
    )

    # Timestamps
    posted_at = models.DateTimeField(null=True, blank=True)  # When comment was posted
    # created_at and updated_at inherited from Timestampable

    class Meta:
        verbose_name = "TikTok Comment"
        verbose_name_plural = "TikTok Comments"
        ordering = ["-posted_at"]

    def __str__(self):
        return f"@{self.author_username}: {self.content[:50]}"
