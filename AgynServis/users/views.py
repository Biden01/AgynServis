from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from .models import Document, DocumentHistory, LoginHistory, User, Comment, DocumentVersion, Task, DocumentApproval
from .forms import DocumentForm, UserRegistrationForm, CustomPasswordChangeForm, CommentForm, DocumentVersionForm, AddCollaboratorForm, KeyPasswordForm, TaskForm, LoginForm, ProfileEditForm
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from .utils import generate_hash, sign_document, verify_signature, generate_key_pair, serialize_public_key
from .utils import encrypt_private_key, decrypt_private_key, create_document_version, compare_versions, validate_document_integrity, create_backup
from django.contrib.auth import login, authenticate, update_session_auth_hash
from datetime import datetime, timedelta
from django.db.models.functions import ExtractWeekDay, ExtractHour
import json
import user_agents
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Регистрация успешна! Теперь вы можете войти.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        form = ProfileEditForm(instance=request.user)
    
    # Получаем статистику документов
    total_documents = Document.objects.filter(author=request.user).count()
    draft_documents = Document.objects.filter(author=request.user, status='draft').count()
    pending_documents = Document.objects.filter(author=request.user, status='pending').count()
    signed_documents = Document.objects.filter(author=request.user, status='signed').count()
    
    # Получаем историю входов
    login_history = LoginHistory.objects.filter(user=request.user).order_by('-login_time')[:10]
    
    # Получаем задания пользователя
    tasks = Task.objects.filter(assigned_to=request.user).order_by('-created_at')[:5]
    
    context = {
        'form': form,
        'total_documents': total_documents,
        'draft_documents': draft_documents,
        'pending_documents': pending_documents,
        'signed_documents': signed_documents,
        'login_history': login_history,
        'tasks': tasks,
    }
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        form = ProfileEditForm(instance=request.user)
    
    return render(request, 'users/profile_edit.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успешно изменен!')
            return redirect('profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    return render(request, 'users/change_password.html', {'form': form})

@login_required
def document_list(request):
    documents = Document.objects.all()
    
    # Фильтрация по статусу
    status = request.GET.get('status')
    if status:
        documents = documents.filter(status=status)
    
    # Фильтрация по типу (входящие/исходящие)
    doc_type = request.GET.get('type')
    if doc_type == 'incoming':
        documents = documents.filter(Q(author__role='director') & ~Q(author=request.user))
    elif doc_type == 'outgoing':
        documents = documents.filter(author=request.user)
    elif doc_type == 'approval':
        # Документы, требующие моего согласования
        documents = documents.filter(current_approver=request.user)
    
    # Поиск по названию
    search_query = request.GET.get('search')
    if search_query:
        documents = documents.filter(title__icontains=search_query)
    
    # Фильтрация по роли пользователя
    if request.user.role == 'director':
        if not doc_type and not status:
            documents = documents.filter(Q(status='pending') | Q(current_approver=request.user))
    elif request.user.role == 'lawyer':
        if not doc_type and not status:
            documents = documents.filter(Q(status='approved') | Q(current_approver=request.user))
    else:
        # Для обычных сотрудников - показываем их документы + те, где они согласующие
        if not doc_type:
            documents = documents.filter(
                Q(author=request.user) | 
                Q(collaborators=request.user) |
                Q(current_approver=request.user)
            ).distinct()
    
    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    documents = documents.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(documents, 10)  # 10 документов на страницу
    page = request.GET.get('page')
    try:
        documents = paginator.page(page)
    except PageNotAnInteger:
        # Если page не является целым числом, показываем первую страницу
        documents = paginator.page(1)
    except EmptyPage:
        # Если page больше максимального, показываем последнюю страницу
        documents = paginator.page(paginator.num_pages)
    
    context = {
        'documents': documents,
        'current_status': status,
        'search_query': search_query,
        'sort_by': sort_by,
        'doc_type': doc_type,
        'pending_approvals': Document.objects.filter(current_approver=request.user).count(),
    }
    return render(request, 'users/document_list.html', context)

@login_required
def document_create(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        key_form = KeyPasswordForm(request.POST)
        
        if form.is_valid() and key_form.is_valid():
            document = form.save(commit=False)
            document.author = request.user
            
            # Генерация хэша
            content = f"{document.title}{document.content}{timezone.now()}"
            document.hash = generate_hash(content)
            
            # Получаем пароль из формы
            password = key_form.cleaned_data['password']
            
            try:
                # Если у пользователя уже есть ключ, пытаемся его расшифровать
                if request.user.private_key:
                    private_key = decrypt_private_key(request.user.private_key, password)
                    if not private_key:
                        messages.error(request, 'Неверный пароль для существующего ключа')
                        return render(request, 'users/document_form.html', {'form': form, 'key_form': key_form})
                else:
                    # Если ключа нет, генерируем новый
                    try:
                        private_key, public_key = generate_key_pair()
                        encrypted_private_key = encrypt_private_key(private_key, password)
                        if encrypted_private_key:
                            request.user.private_key = encrypted_private_key
                            request.user.save()
                            document.public_key = serialize_public_key(public_key)
                        else:
                            messages.error(request, 'Ошибка при шифровании приватного ключа')
                            return render(request, 'users/document_form.html', {'form': form, 'key_form': key_form})
                    except Exception as crypto_error:
                        messages.error(request, f'Ошибка при создании ключей: {str(crypto_error)}')
                        return render(request, 'users/document_form.html', {'form': form, 'key_form': key_form})
                
                # Создание подписи
                document.signature = sign_document(private_key, document.hash)
                document.save()
                
                # Запись в историю
                DocumentHistory.objects.create(
                    document=document,
                    user=request.user,
                    action='Создание документа',
                    status=document.status,
                    ip_address=get_client_ip(request),
                    content_after=document.content
                )
                
                # Создание первой версии документа
                create_document_version(document, request.user, document.content, version_number=1)
                
                # Создание резервной копии
                create_backup(document)
                
                messages.success(request, 'Документ успешно создан!')
                return redirect('document_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании документа: {str(e)}')
                return render(request, 'users/document_form.html', {'form': form, 'key_form': key_form})
    else:
        form = DocumentForm()
        key_form = KeyPasswordForm()
    
    return render(request, 'users/document_form.html', {'form': form, 'key_form': key_form})

@login_required
def document_edit(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем права доступа
    if document.author != request.user and request.user not in document.collaborators.all():
        messages.error(request, 'У вас нет прав для редактирования этого документа!')
        return redirect('document_list')
    
    # Проверяем не заблокирован ли документ другим пользователем
    if document.is_locked and document.locked_by != request.user:
        if (timezone.now() - document.locked_at).seconds < 3600:  # 1 час
            messages.warning(request, f'Документ в данный момент редактируется пользователем {document.locked_by.username}')
            return redirect('document_detail', pk=pk)
    
    # Блокируем документ
    document.lock_document(request.user)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            # Сохраняем старое содержимое для истории
            old_content = document.content
            
            document = form.save(commit=False)
            
            # Обновляем хэш и подпись если изменился текст документа
            if old_content != document.content:
                # Запрос пароля для расшифровки приватного ключа
                key_form = KeyPasswordForm(request.POST)
                if key_form.is_valid():
                    password = key_form.cleaned_data['password']
                    
                    # Расшифровываем приватный ключ
                    private_key = decrypt_private_key(request.user.private_key, password)
                    
                    if private_key:
                        # Обновляем хэш
                        content = f"{document.title}{document.content}{timezone.now()}"
                        document.hash = generate_hash(content)
                        
                        # Обновляем подпись
                        document.signature = sign_document(private_key, document.hash)
                        
                        document.save()
                        
                        # Запись в историю
                        DocumentHistory.objects.create(
                            document=document,
                            user=request.user,
                            action='Редактирование документа',
                            status=document.status,
                            ip_address=get_client_ip(request),
                            content_before=old_content,
                            content_after=document.content
                        )
                        
                        # Создание новой версии документа
                        create_document_version(document, request.user, document.content)
                        
                        # Создание резервной копии
                        create_backup(document)
                        
                        # Разблокируем документ
                        document.unlock_document()
                        
                        messages.success(request, 'Документ успешно обновлен!')
                        return redirect('document_detail', pk=pk)
                    else:
                        messages.error(request, 'Неверный пароль для ключа!')
                else:
                    messages.error(request, 'Пожалуйста, укажите пароль для ключа')
            else:
                document.save()
                document.unlock_document()
                messages.success(request, 'Документ успешно обновлен!')
                return redirect('document_detail', pk=pk)
    else:
        form = DocumentForm(instance=document)
        key_form = KeyPasswordForm()
    
    return render(request, 'users/document_edit.html', {
        'form': form,
        'document': document,
        'key_form': key_form
    })

@login_required
def document_unlock(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    if document.locked_by != request.user and not request.user.is_staff:
        messages.error(request, 'Вы не можете разблокировать этот документ!')
        return redirect('document_detail', pk=pk)
    
    document.unlock_document()
    messages.success(request, 'Документ разблокирован')
    return redirect('document_detail', pk=pk)

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем права доступа
    if (document.author != request.user and 
        request.user not in document.collaborators.all() and 
        request.user.role not in ['director', 'lawyer']):
        messages.error(request, 'У вас нет доступа к этому документу!')
        return redirect('document_list')
    
    # Получаем комментарии
    comments = document.comments.filter(parent=None).order_by('created_at')
    
    # Получаем версии
    versions = document.versions.order_by('-version_number')
    
    # Форма для комментариев
    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.document = document
            comment.user = request.user
            comment.save()
            messages.success(request, 'Комментарий добавлен!')
            return redirect('document_detail', pk=pk)
    else:
        comment_form = CommentForm()
    
    # Проверка целостности документа
    document_integrity = validate_document_integrity(document)
    
    return render(request, 'users/document_detail.html', {
        'document': document,
        'history': document.history.all(),
        'comments': comments,
        'versions': versions,
        'comment_form': comment_form,
        'document_integrity': document_integrity
    })

@login_required
def comment_reply(request, pk, comment_id):
    document = get_object_or_404(Document, pk=pk)
    parent_comment = get_object_or_404(Comment, id=comment_id)
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.document = document
            comment.user = request.user
            comment.parent = parent_comment
            comment.save()
            messages.success(request, 'Ответ на комментарий добавлен!')
            return redirect('document_detail', pk=pk)
    
    return redirect('document_detail', pk=pk)

@login_required
def document_version_detail(request, pk, version_id):
    document = get_object_or_404(Document, pk=pk)
    version = get_object_or_404(DocumentVersion, id=version_id, document=document)
    
    # Проверяем права доступа
    if (document.author != request.user and 
        request.user not in document.collaborators.all() and 
        request.user.role not in ['director', 'lawyer']):
        messages.error(request, 'У вас нет доступа к этому документу!')
        return redirect('document_list')
    
    return render(request, 'users/document_version_detail.html', {
        'document': document,
        'version': version
    })

@login_required
def document_version_compare(request, pk, version1_id, version2_id):
    document = get_object_or_404(Document, pk=pk)
    version1 = get_object_or_404(DocumentVersion, id=version1_id, document=document)
    version2 = get_object_or_404(DocumentVersion, id=version2_id, document=document)
    
    # Проверяем права доступа
    if (document.author != request.user and 
        request.user not in document.collaborators.all() and 
        request.user.role not in ['director', 'lawyer']):
        messages.error(request, 'У вас нет доступа к этому документу!')
        return redirect('document_list')
    
    # Сравниваем версии
    diff = compare_versions(version1, version2)
    
    return render(request, 'users/document_version_compare.html', {
        'document': document,
        'version1': version1,
        'version2': version2,
        'diff': diff
    })

@login_required
def document_add_collaborator(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем права доступа
    if document.author != request.user:
        messages.error(request, 'Только автор документа может добавлять соавторов!')
        return redirect('document_detail', pk=pk)
    
    if request.method == 'POST':
        form = AddCollaboratorForm(request.POST, document=document)
        if form.is_valid():
            user = form.cleaned_data['user']
            document.collaborators.add(user)
            
            # Запись в историю
            DocumentHistory.objects.create(
                document=document,
                user=request.user,
                action=f'Добавлен соавтор: {user.username}',
                status=document.status,
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Пользователь {user.username} добавлен в соавторы!')
            return redirect('document_detail', pk=pk)
    else:
        form = AddCollaboratorForm(document=document)
    
    return render(request, 'users/document_add_collaborator.html', {
        'form': form,
        'document': document
    })

@login_required
def document_remove_collaborator(request, pk, user_id):
    document = get_object_or_404(Document, pk=pk)
    collaborator = get_object_or_404(User, id=user_id)
    
    # Проверяем права доступа
    if document.author != request.user:
        messages.error(request, 'Только автор документа может удалять соавторов!')
        return redirect('document_detail', pk=pk)
    
    document.collaborators.remove(collaborator)
    
    # Запись в историю
    DocumentHistory.objects.create(
        document=document,
        user=request.user,
        action=f'Удален соавтор: {collaborator.username}',
        status=document.status,
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, f'Пользователь {collaborator.username} удален из соавторов!')
    return redirect('document_detail', pk=pk)

@login_required
def document_revert_to_version(request, pk, version_id):
    document = get_object_or_404(Document, pk=pk)
    version = get_object_or_404(DocumentVersion, id=version_id, document=document)
    
    # Проверяем права доступа
    if document.author != request.user and request.user not in document.collaborators.all():
        messages.error(request, 'У вас нет прав для редактирования этого документа!')
        return redirect('document_detail', pk=pk)
    
    # Проверяем не заблокирован ли документ другим пользователем
    if document.is_locked and document.locked_by != request.user:
        if (timezone.now() - document.locked_at).seconds < 3600:  # 1 час
            messages.warning(request, f'Документ в данный момент редактируется пользователем {document.locked_by.username}')
            return redirect('document_detail', pk=pk)
    
    # Блокируем документ
    document.lock_document(request.user)
    
    # Запрос пароля для расшифровки приватного ключа
    if request.method == 'POST':
        key_form = KeyPasswordForm(request.POST)
        if key_form.is_valid():
            password = key_form.cleaned_data['password']
            
            # Расшифровываем приватный ключ
            private_key = decrypt_private_key(request.user.private_key, password)
            
            if private_key:
                # Сохраняем старое содержимое для истории
                old_content = document.content
                
                # Обновляем документ до выбранной версии
                document.content = version.content
                
                # Обновляем хэш
                content = f"{document.title}{document.content}{timezone.now()}"
                document.hash = generate_hash(content)
                
                # Обновляем подпись
                document.signature = sign_document(private_key, document.hash)
                
                document.save()
                
                # Запись в историю
                DocumentHistory.objects.create(
                    document=document,
                    user=request.user,
                    action=f'Откат к версии {version.version_number}',
                    status=document.status,
                    ip_address=get_client_ip(request),
                    content_before=old_content,
                    content_after=document.content
                )
                
                # Создание новой версии документа
                create_document_version(document, request.user, document.content)
                
                # Создание резервной копии
                create_backup(document)
                
                # Разблокируем документ
                document.unlock_document()
                
                messages.success(request, f'Документ успешно откачен к версии {version.version_number}!')
                return redirect('document_detail', pk=pk)
            else:
                messages.error(request, 'Неверный пароль для ключа!')
        else:
            messages.error(request, 'Пожалуйста, укажите пароль для ключа')
    else:
        key_form = KeyPasswordForm()
    
    return render(request, 'users/document_revert_version.html', {
        'document': document,
        'version': version,
        'key_form': key_form
    })

def is_staff(user):
    return user.role in ['director', 'lawyer', 'employee']

def is_client(user):
    return user.role == 'client'

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Record login history
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Redirect based on user role
                if user.role == 'employee':
                    return redirect('document_list')
                elif user.role == 'director':
                    return redirect('document_pending')
                elif user.role == 'lawyer':
                    return redirect('document_approved')
                else:
                    return redirect('document_list')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль')
    else:
        form = LoginForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
@user_passes_test(is_staff)
def staff_dashboard(request):
    # Получаем статистику документов
    total_documents = Document.objects.count()
    signed_documents = Document.objects.filter(status='signed').count()
    
    # Получаем последние действия
    recent_actions = DocumentHistory.objects.select_related('document').order_by('-timestamp')[:5]
    
    # Получаем последние документы
    recent_documents = Document.objects.order_by('-created_at')[:5]
    
    context = {
        'total_documents': total_documents,
        'signed_documents': signed_documents,
        'recent_actions': recent_actions,
        'recent_documents': recent_documents,
    }
    return render(request, 'users/staff/dashboard.html', context)

@login_required
@user_passes_test(is_client)
def client_dashboard(request):
    # Получаем документы клиента
    documents = Document.objects.filter(author=request.user)
    total_documents = documents.count()
    signed_documents = documents.filter(status='signed').count()
    
    # Получаем последние действия с документами клиента
    recent_actions = DocumentHistory.objects.filter(
        document__author=request.user
    ).select_related('document').order_by('-timestamp')[:5]
    
    context = {
        'total_documents': total_documents,
        'signed_documents': signed_documents,
        'recent_actions': recent_actions,
        'documents': documents[:5],  # Последние 5 документов
    }
    return render(request, 'users/client/dashboard.html', context)

# Представления для работы с заданиями

@login_required
def task_list(request):
    # Для директора показываем созданные им задания
    if request.user.role == 'director':
        tasks = Task.objects.filter(assigned_by=request.user)
    # Для остальных пользователей - задания, назначенные им
    else:
        tasks = Task.objects.filter(assigned_to=request.user)
    
    # Фильтрация по статусу
    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)
    
    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    
    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    tasks = tasks.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(tasks, 10)  # 10 задач на страницу
    page = request.GET.get('page')
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        # Если page не является целым числом, показываем первую страницу
        tasks = paginator.page(1)
    except EmptyPage:
        # Если page больше максимального, показываем последнюю страницу
        tasks = paginator.page(paginator.num_pages)
    
    context = {
        'tasks': tasks,
        'current_status': status,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    return render(request, 'users/task_list.html', context)

@login_required
@user_passes_test(lambda u: u.role == 'director')
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.assigned_by = request.user
            task.save()
            
            messages.success(request, 'Задание успешно создано!')
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)
    
    return render(request, 'users/task_form.html', {'form': form})

@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    
    # Проверяем права доступа
    if request.user != task.assigned_by and request.user != task.assigned_to:
        messages.error(request, 'У вас нет доступа к этому заданию!')
        return redirect('task_list')
    
    return render(request, 'users/task_detail.html', {'task': task})

@login_required
@user_passes_test(lambda u: u.role == 'director')
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_by=request.user)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Задание успешно обновлено!')
            return redirect('task_detail', pk=pk)
    else:
        form = TaskForm(instance=task, user=request.user)
    
    return render(request, 'users/task_form.html', {'form': form, 'task': task})

@login_required
def task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    
    task.mark_completed()
    messages.success(request, 'Задание отмечено как выполненное!')
    return redirect('task_list')

@login_required
def task_cancel(request, pk):
    task = get_object_or_404(Task, pk=pk)
    
    # Проверяем права доступа
    if request.user != task.assigned_by:
        messages.error(request, 'Только создатель задания может отменить его!')
        return redirect('task_detail', pk=pk)
    
    task.status = 'cancelled'
    task.save()
    messages.success(request, 'Задание отменено!')
    return redirect('task_list')

@login_required
def task_start(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    
    task.status = 'in_progress'
    task.save()
    messages.success(request, 'Задание взято в работу!')
    return redirect('task_detail', pk=pk)

@login_required
def document_approve(request, pk):
    if request.user.role != 'director':
        messages.error(request, 'У вас нет прав для этого действия!')
        return redirect('document_list')
    
    document = get_object_or_404(Document, pk=pk, status='pending')
    document.status = 'approved'
    document.save()
    
    DocumentHistory.objects.create(
        document=document,
        user=request.user,
        action='Подтверждение директором',
        status=document.status,
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, 'Документ подтвержден!')
    return redirect('document_list')

@login_required
def document_sign(request, pk):
    if request.user.role != 'lawyer':
        messages.error(request, 'У вас нет прав для этого действия!')
        return redirect('document_list')
    
    document = get_object_or_404(Document, pk=pk, status='approved')
    document.status = 'signed'
    document.save()
    
    DocumentHistory.objects.create(
        document=document,
        user=request.user,
        action='Подписание юристом',
        status=document.status,
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, 'Документ подписан!')
    return redirect('document_list')

@login_required
def document_reject(request, pk):
    if request.user.role not in ['director', 'lawyer']:
        messages.error(request, 'У вас нет прав для этого действия!')
        return redirect('document_list')
    
    document = get_object_or_404(Document, pk=pk)
    document.status = 'rejected'
    document.save()
    
    DocumentHistory.objects.create(
        document=document,
        user=request.user,
        action='Отклонение документа',
        status=document.status,
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, 'Документ отклонен!')
    return redirect('document_list')

@login_required
def document_drafts(request):
    documents = Document.objects.filter(author=request.user, status='draft').order_by('-created_at')
    return render(request, 'users/document_list.html', {
        'documents': documents,
        'current_status': 'draft',
        'title': 'Черновики'
    })

@login_required
def document_pending(request):
    if request.user.role == 'director':
        documents = Document.objects.filter(status='pending').order_by('-created_at')
    else:
        documents = Document.objects.filter(author=request.user, status='pending').order_by('-created_at')
    return render(request, 'users/document_list.html', {
        'documents': documents,
        'current_status': 'pending',
        'title': 'На рассмотрении'
    })

@login_required
def document_approved(request):
    if request.user.role == 'lawyer':
        documents = Document.objects.filter(status='approved').order_by('-created_at')
    else:
        documents = Document.objects.filter(author=request.user, status='approved').order_by('-created_at')
    return render(request, 'users/document_list.html', {
        'documents': documents,
        'current_status': 'approved',
        'title': 'Одобренные документы'
    })

@login_required
def document_signed(request):
    documents = Document.objects.filter(Q(author=request.user, status='signed') | 
                                      Q(collaborators=request.user, status='signed')).distinct().order_by('-created_at')
    return render(request, 'users/document_list.html', {
        'documents': documents,
        'current_status': 'signed',
        'title': 'Подписанные документы'
    })

@login_required
def login_statistics(request):
    """View for login statistics"""
    # Check if user has permission (admin or director)
    if not (request.user.is_staff or request.user.role in ['admin', 'director']):
        messages.error(request, 'У вас нет доступа к этой странице')
        return redirect('profile')
    
    now = timezone.now()
    
    # Overall statistics
    total_logins = LoginHistory.objects.count()
    
    # Last month statistics
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)
    
    logins_last_month = LoginHistory.objects.filter(login_time__gte=month_ago).count()
    logins_previous_month = LoginHistory.objects.filter(
        login_time__gte=two_months_ago,
        login_time__lt=month_ago
    ).count()
    
    # Calculate percentage change
    if logins_previous_month > 0:
        logins_last_month_change = int(((logins_last_month - logins_previous_month) / logins_previous_month) * 100)
    else:
        logins_last_month_change = 100 if logins_last_month > 0 else 0
    
    # Last week statistics
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    logins_last_week = LoginHistory.objects.filter(login_time__gte=week_ago).count()
    logins_previous_week = LoginHistory.objects.filter(
        login_time__gte=two_weeks_ago,
        login_time__lt=week_ago
    ).count()
    
    # Calculate percentage change for week
    if logins_previous_week > 0:
        logins_last_week_change = int(((logins_last_week - logins_previous_week) / logins_previous_week) * 100)
    else:
        logins_last_week_change = 100 if logins_last_week > 0 else 0
    
    # Active users (with login in the last 7 days)
    active_users = LoginHistory.objects.filter(
        login_time__gte=week_ago
    ).values('user').distinct().count()
    
    # Activity by weekday (1=Monday, 7=Sunday)
    weekday_data = LoginHistory.objects.filter(
        login_time__gte=month_ago
    ).annotate(
        weekday=ExtractWeekDay('login_time')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')
    
    # Convert to list for chart
    weekday_counts = [0] * 7  # Initialize with zeros for all 7 days
    for entry in weekday_data:
        # Django's ExtractWeekDay uses 1-7 where 1=Sunday, so we need to adjust
        # to make Monday=0, Sunday=6
        day_index = (entry['weekday'] % 7) - 1
        weekday_counts[day_index] = entry['count']
    
    # Activity by hour
    hourly_data = LoginHistory.objects.filter(
        login_time__gte=month_ago
    ).annotate(
        hour=ExtractHour('login_time')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Convert to list for chart
    hourly_counts = [0] * 24  # Initialize with zeros for all 24 hours
    for entry in hourly_data:
        hourly_counts[entry['hour']] = entry['count']
    
    # Get top users by login count
    user_stats = []
    top_users_data = LoginHistory.objects.values('user').annotate(
        login_count=Count('id')
    ).order_by('-login_count')[:20]  # Get top 20 users
    
    for entry in top_users_data:
        user = User.objects.get(pk=entry['user'])
        last_login = LoginHistory.objects.filter(user=user).order_by('-login_time').first()
        
        # Extract device types
        user_devices = set()
        user_login_samples = LoginHistory.objects.filter(user=user).order_by('-login_time')[:10]
        
        for login in user_login_samples:
            if login.user_agent:
                try:
                    agent = user_agents.parse(login.user_agent)
                    if agent.is_mobile:
                        user_devices.add('mobile')
                    elif agent.is_tablet:
                        user_devices.add('tablet')
                    elif agent.is_pc:
                        user_devices.add('desktop')
                    else:
                        user_devices.add('other')
                except:
                    user_devices.add('other')
        
        user_stats.append({
            'user': user,
            'login_count': entry['login_count'],
            'last_login': last_login.login_time if last_login else None,
            'devices': list(user_devices)
        })
    
    # Mock map data (in a real app, would use IP geolocation)
    # This would typically come from a geolocation service using stored IP addresses
    map_data = [
        {'lat': 43.25, 'lng': 76.95, 'city': 'Алматы', 'count': 250},
        {'lat': 51.12, 'lng': 71.43, 'city': 'Астана', 'count': 180},
        {'lat': 52.28, 'lng': 76.96, 'city': 'Павлодар', 'count': 85},
        {'lat': 42.31, 'lng': 69.59, 'city': 'Шымкент', 'count': 105},
        {'lat': 49.80, 'lng': 73.10, 'city': 'Караганда', 'count': 75},
    ]
    
    context = {
        'total_logins': total_logins,
        'logins_last_month': logins_last_month,
        'logins_last_month_change': logins_last_month_change,
        'logins_last_week': logins_last_week,
        'logins_last_week_change': logins_last_week_change,
        'active_users': active_users,
        'weekday_data': json.dumps(weekday_counts),
        'hourly_data': json.dumps(hourly_counts),
        'top_users': user_stats,
        'map_data': json.dumps(map_data)
    }
    
    # На всякий случай, проверим, правильно ли работает URL-resolving
    try:
        from django.urls import reverse
        staff_url = reverse('staff_dashboard')
        # Если URL не существует, это вызовет исключение
        context['staff_dashboard_url'] = staff_url
    except Exception as e:
        # Логируем ошибку, добавляем информацию в контекст для диагностики
        context['url_error'] = str(e)
    
    return render(request, 'users/login_statistics.html', context)

@login_required
def document_edit_realtime(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем права доступа
    if document.author != request.user and request.user not in document.collaborators.all():
        messages.error(request, 'У вас нет прав для редактирования этого документа!')
        return redirect('document_list')
    
    # Проверяем статус документа
    if document.status != 'draft':
        messages.error(request, 'Этот документ нельзя редактировать, т.к. он не является черновиком!')
        return redirect('document_detail', pk=pk)
    
    return render(request, 'users/document_edit_realtime.html', {
        'document': document,
    })

@login_required
def document_save_api(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})
    
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем права доступа
    if document.author != request.user and request.user not in document.collaborators.all():
        return JsonResponse({'success': False, 'error': 'У вас нет прав для редактирования этого документа'})
    
    # Проверяем статус документа
    if document.status != 'draft':
        return JsonResponse({'success': False, 'error': 'Этот документ нельзя редактировать, т.к. он не является черновиком'})
    
    try:
        data = json.loads(request.body)
        title = data.get('title')
        content = data.get('content')
        password = data.get('password')
        
        if not all([title, content, password]):
            return JsonResponse({'success': False, 'error': 'Пожалуйста, заполните все поля'})
        
        # Сохраняем старое содержимое для истории
        old_title = document.title
        old_content = document.content
        
        # Попытка расшифровать приватный ключ
        private_key = decrypt_private_key(request.user.private_key, password)
        
        if not private_key:
            return JsonResponse({'success': False, 'error': 'Неверный пароль для ключа'})
        
        # Обновляем документ
        document.title = title
        document.content = content
        
        # Обновляем хэш и подпись
        content_for_hash = f"{document.title}{document.content}{timezone.now()}"
        document.hash = generate_hash(content_for_hash)
        document.signature = sign_document(private_key, document.hash)
        document.updated_at = timezone.now()
        document.save()
        
        # Записываем в историю если были изменения
        if old_title != title or old_content != content:
            DocumentHistory.objects.create(
                document=document,
                user=request.user,
                action='Редактирование документа (реальное время)',
                status=document.status,
                ip_address=get_client_ip(request),
                content_before=old_content,
                content_after=document.content
            )
            
            # Создание новой версии документа
            create_document_version(document, request.user, document.content)
            
            # Создание резервной копии
            create_backup(document)
        
        return JsonResponse({'success': True, 'message': 'Документ успешно сохранен'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def document_approve_step(request, pk):
    """Функция согласования текущего шага документа"""
    document = get_object_or_404(Document, pk=pk)
    
    # Проверка, что текущий пользователь является текущим согласовывающим
    if document.current_approver != request.user:
        messages.error(request, 'Вы не можете согласовать этот документ на текущем этапе')
        return redirect('document_detail', pk=pk)
    
    try:
        # Получаем текущее согласование
        approval = DocumentApproval.objects.get(
            document=document,
            approver=request.user,
            step_number=document.approval_step
        )
        
        # Если это GET запрос, просто показываем форму согласования
        if request.method == 'POST':
            action = request.POST.get('action')
            comment = request.POST.get('comment', '')
            
            if action == 'approve':
                # Обновляем статус согласования
                approval.status = 'approved'
                approval.comment = comment
                approval.save()
                
                # Записываем в историю
                DocumentHistory.objects.create(
                    document=document,
                    user=request.user,
                    action=f'Согласовал этап {document.approval_step}',
                    status=document.status,
                    ip_address=get_client_ip(request),
                    comment=comment
                )
                
                # Переходим к следующему этапу
                document.advance_approval()
                
                messages.success(request, 'Документ успешно согласован и передан на следующий этап')
            
            elif action == 'reject':
                if not comment:
                    messages.error(request, 'При отклонении необходимо указать причину')
                    return redirect('document_approve_step', pk=pk)
                
                # Обновляем статус согласования и документа
                approval.status = 'rejected'
                approval.comment = comment
                approval.save()
                
                document.status = 'rejected'
                document.save()
                
                # Записываем в историю
                DocumentHistory.objects.create(
                    document=document,
                    user=request.user,
                    action=f'Отклонил на этапе {document.approval_step}',
                    status='rejected',
                    ip_address=get_client_ip(request),
                    comment=comment
                )
                
                messages.warning(request, 'Документ отклонен')
            
            return redirect('document_detail', pk=pk)
            
        # Получаем всю историю согласований для отображения прогресса
        all_approvals = DocumentApproval.objects.filter(document=document).order_by('step_number')
        
        return render(request, 'users/document_approve_step.html', {
            'document': document,
            'approval': approval,
            'all_approvals': all_approvals
        })
        
    except DocumentApproval.DoesNotExist:
        messages.error(request, 'Не найдена запись согласования для текущего этапа')
        return redirect('document_detail', pk=pk)

@login_required
def linked_document(request, pk):
    """View for displaying a linked document with its clickable card"""
    document = get_object_or_404(Document, pk=pk)
    
    # Проверяем задания пользователя на связь с этим документом
    user_has_task_with_document = Task.objects.filter(assigned_to=request.user, document=document).exists()
    
    # Check access permissions - добавляем проверку на наличие задания с этим документом
    if (document.author != request.user and 
        request.user not in document.collaborators.all() and 
        request.user.role not in ['director', 'lawyer'] and
        document.current_approver != request.user and
        not user_has_task_with_document):
        messages.error(request, 'У вас нет доступа к этому документу!')
        return redirect('document_list')
    
    return render(request, 'users/linked_document.html', {
        'document': document
    })
