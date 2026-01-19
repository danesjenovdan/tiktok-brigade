from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Group, TikTokComment, TikTokProfile, TikTokVideo


class WeekFilter(admin.SimpleListFilter):
    title = "teden"
    parameter_name = "week"

    def lookups(self, request, model_admin):
        return (
            ("last_week", "Zadnji teden (0-7 dni)"),
            ("prev_week", "Prejšnji teden (7-14 dni)"),
            ("2_weeks_ago", "2 tedna nazaj (14-21 dni)"),
            ("3_weeks_ago", "3 tedne nazaj (21-28 dni)"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "last_week":
            start = now - timedelta(days=7)
            return queryset.filter(posted_at__gte=start, posted_at__lte=now)
        elif self.value() == "prev_week":
            start = now - timedelta(days=14)
            end = now - timedelta(days=7)
            return queryset.filter(posted_at__gte=start, posted_at__lt=end)
        elif self.value() == "2_weeks_ago":
            start = now - timedelta(days=21)
            end = now - timedelta(days=14)
            return queryset.filter(posted_at__gte=start, posted_at__lt=end)
        elif self.value() == "3_weeks_ago":
            start = now - timedelta(days=28)
            end = now - timedelta(days=21)
            return queryset.filter(posted_at__gte=start, posted_at__lt=end)
        return queryset


class TikTokCommentInline(admin.TabularInline):
    model = TikTokComment
    extra = 0
    fields = [
        "comment_id",
        "author_username",
        "content_preview",
        "like_count",
        "reply_count",
        "posted_at",
    ]
    readonly_fields = [
        "comment_id",
        "author_username",
        "content_preview",
        "like_count",
        "reply_count",
        "posted_at",
    ]
    can_delete = False
    show_change_link = True

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "profile_count", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    def profile_count(self, obj):
        return obj.profiles.count()

    profile_count.short_description = "Profiles"


@admin.register(TikTokProfile)
class TikTokProfileAdmin(admin.ModelAdmin):
    list_display = ["username", "name", "groups_list", "video_count", "updated_at"]
    list_filter = ["groups", "created_at", "updated_at"]
    search_fields = ["username", "name", "groups__name"]
    filter_horizontal = ["groups"]
    readonly_fields = ["created_at", "updated_at"]

    def groups_list(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])

    groups_list.short_description = "Groups"

    def video_count(self, obj):
        return obj.videos.count()

    video_count.short_description = "Videos"


@admin.register(TikTokVideo)
class TikTokVideoAdmin(admin.ModelAdmin):
    list_display = [
        "video_id",
        "profile_username",
        "description_short",
        "play_count",
        "like_count",
        "comment_count",
        "video_url",
        "posted_at",
        "updated_at",
    ]
    list_filter = ["profile__groups", WeekFilter, "posted_at", "created_at"]
    search_fields = ["video_id", "description", "profile__username", "profile__name"]
    autocomplete_fields = ["profile"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "posted_at"
    inlines = [TikTokCommentInline]

    def profile_username(self, obj):
        return f"@{obj.profile.username}"

    profile_username.short_description = "Profile"

    def description_short(self, obj):
        if obj.description:
            return (
                obj.description[:50] + "..."
                if len(obj.description) > 50
                else obj.description
            )
        return "-"

    description_short.short_description = "Description"


@admin.register(TikTokComment)
class TikTokCommentAdmin(admin.ModelAdmin):
    list_display = [
        "comment_id",
        "author_username",
        "video_link",
        "content_short",
        "like_count",
        "reply_count",
        "is_reply",
        "posted_at",
        "video_url_link"
    ]
    list_filter = [WeekFilter, "posted_at", "created_at"]
    search_fields = [
        "comment_id",
        "author_username",
        "author_nickname",
        "content",
        "video__video_id",
    ]
    autocomplete_fields = ["video", "parent_comment"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "posted_at"

    def video_link(self, obj):
        return f"{obj.video.video_id}"

    video_link.short_description = "Video"

    def content_short(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content

    content_short.short_description = "Content"

    def is_reply(self, obj):
        return obj.parent_comment is not None

    is_reply.boolean = True
    is_reply.short_description = "Reply"

    def video_url_link(self, obj):
        if obj.video and obj.video.video_url:
            return format_html('<a href="{}" target="_blank">Link</a>', obj.video.video_url)
        return "-"

    video_url_link.short_description = "Video URL"
