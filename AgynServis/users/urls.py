from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', views.register, name='register'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('client/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/change-password/', views.change_password, name='change_password'),
    
    # Документы
    path('documents/', views.document_list, name='document_list'),
    path('document/create/', views.document_create, name='document_create'),
    path('document/<int:pk>/', views.document_detail, name='document_detail'),
    path('document/<int:pk>/edit/', views.document_edit, name='document_edit'),
    path('document/<int:pk>/edit/realtime/', views.document_edit_realtime, name='document_edit_realtime'),
    path('document/<int:pk>/save/', views.document_save_api, name='document_save_api'),
    path('document/<int:pk>/unlock/', views.document_unlock, name='document_unlock'),
    path('document/<int:pk>/approve/', views.document_approve, name='document_approve'),
    path('document/<int:pk>/sign/', views.document_sign, name='document_sign'),
    path('document/<int:pk>/reject/', views.document_reject, name='document_reject'),
    
    # Комментарии
    path('document/<int:pk>/comment/reply/<int:comment_id>/', views.comment_reply, name='comment_reply'),
    
    # Версии документов
    path('document/<int:pk>/version/<int:version_id>/', views.document_version_detail, name='document_version_detail'),
    path('document/<int:pk>/version/compare/<int:version1_id>/<int:version2_id>/', views.document_version_compare, name='document_version_compare'),
    path('document/<int:pk>/version/revert/<int:version_id>/', views.document_revert_to_version, name='document_revert_to_version'),
    
    # Соавторы
    path('document/<int:pk>/collaborator/add/', views.document_add_collaborator, name='document_add_collaborator'),
    path('document/<int:pk>/collaborator/remove/<int:user_id>/', views.document_remove_collaborator, name='document_remove_collaborator'),
    
    # Фильтры документов
    path('documents/drafts/', views.document_drafts, name='document_drafts'),
    path('documents/pending/', views.document_pending, name='document_pending'),
    path('documents/approved/', views.document_approved, name='document_approved'),
    path('documents/signed/', views.document_signed, name='document_signed'),
    
    # Задания
    path('tasks/', views.task_list, name='task_list'),
    path('task/create/', views.task_create, name='task_create'),
    path('task/<int:pk>/', views.task_detail, name='task_detail'),
    path('task/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('task/<int:pk>/complete/', views.task_complete, name='task_complete'),
    path('task/<int:pk>/cancel/', views.task_cancel, name='task_cancel'),
    path('task/<int:pk>/start/', views.task_start, name='task_start'),
    
    # Дашборды
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),
    path('dashboard/client/', views.client_dashboard, name='client_dashboard'),
    
    # Статистика
    path('login-statistics/', views.login_statistics, name='login_statistics'),
] 