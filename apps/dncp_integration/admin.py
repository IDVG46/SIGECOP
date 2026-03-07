from django.contrib import admin

from apps.dncp_integration.models import DNCPOrganization, UserDNCPOrganizationSelection


@admin.register(DNCPOrganization)
class DNCPOrganizationAdmin(admin.ModelAdmin):
	list_display = ("code", "name", "procuring_entity_name", "is_active")
	list_filter = ("is_active",)
	search_fields = ("code", "name", "procuring_entity_name")


@admin.register(UserDNCPOrganizationSelection)
class UserDNCPOrganizationSelectionAdmin(admin.ModelAdmin):
	list_display = ("user", "organization", "updated_at")
	search_fields = ("user__username", "organization__name", "organization__code")
