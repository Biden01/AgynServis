from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, LoginHistory, Document, DocumentHistory

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'specialty', 'role', 'is_staff')
    list_filter = ('role', 'specialty', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('specialty', 'role')}),
    )

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'ip_address')
    search_fields = ('user__username', 'ip_address')
    list_filter = ('login_time',)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'author')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('hash', 'signature', 'public_key')

@admin.register(DocumentHistory)
class DocumentHistoryAdmin(admin.ModelAdmin):
    list_display = ('document', 'user', 'action', 'status', 'timestamp', 'ip_address')
    list_filter = ('status', 'timestamp', 'user')
    search_fields = ('document__title', 'user__username', 'action')
    readonly_fields = ('timestamp',)
