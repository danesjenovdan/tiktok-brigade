from django.contrib import admin

from .models import Group, TikTokComment, TikTokProfile, TikTokVideo


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
        "posted_at",
        "updated_at",
    ]
    list_filter = ["profile__groups", "posted_at", "created_at"]
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
    ]
    list_filter = ["posted_at", "created_at"]
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
