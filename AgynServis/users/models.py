from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import datetime

class User(AbstractUser):
    SPECIALTY_CHOICES = [
        ('dev', 'Разработчик'),
        ('hr', 'HR'),
        ('lawyer', 'Юрист'),
        ('director', 'Директор'),
        ('other', 'Другое'),
    ]
    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('director', 'Директор'),
        ('lawyer', 'Юрист'),
        ('admin', 'Админ'),
    ]
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, verbose_name='Специальность', blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee', verbose_name='Роль')
    private_key = models.TextField(blank=True, verbose_name='Приватный ключ (зашифрованный)')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"

class Document(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('pending', 'На рассмотрении'),
        ('approved', 'Подтвержден'),
        ('signed', 'Подписан юристом'),
        ('rejected', 'Отклонен'),
    ]
    
    # Автоматический номер документа
    document_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name='Номер документа')
    
    title = models.CharField(max_length=200, verbose_name='Название документа')
    content = models.TextField(verbose_name='Текст документа')
    file = models.FileField(upload_to='documents/', verbose_name='Файл (PDF)', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    
    # Новые поля для маршрутизации
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_documents', 
                                 null=True, blank=True, verbose_name='Кому (адресат)')
    signer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents_to_sign',
                              null=True, blank=True, verbose_name='Подписант')
    direct_supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='supervised_documents',
                                        null=True, blank=True, verbose_name='Непосредственный начальник')
    approvers = models.ManyToManyField(User, related_name='documents_to_approve', 
                                     blank=True, verbose_name='Согласовывающие')
    
    # Поле для отслеживания текущего этапа маршрута
    current_approver = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='pending_approvals',
                                       null=True, blank=True, verbose_name='Текущий согласовывающий')
    approval_step = models.IntegerField(default=0, verbose_name='Шаг согласования')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Статус')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    hash = models.CharField(max_length=64, blank=True, verbose_name='Хэш документа')
    signature = models.TextField(blank=True, verbose_name='Цифровая подпись')
    public_key = models.TextField(blank=True, verbose_name='Публичный ключ')
    collaborators = models.ManyToManyField(User, related_name='collaborations', blank=True, verbose_name='Соавторы')
    is_locked = models.BooleanField(default=False, verbose_name='Документ заблокирован')
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='locked_documents', null=True, blank=True, verbose_name='Заблокирован пользователем')
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='Время блокировки')
    is_incoming = models.BooleanField(default=False, verbose_name='Входящий документ')

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['-created_at']

    def __str__(self):
        if self.document_number:
            return f"{self.document_number} - {self.title} ({self.get_status_display()})"
        return f"{self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Генерация номера документа при первом сохранении
        if not self.document_number:
            year = datetime.date.today().year
            # Получаем последний документ этого года
            last_doc = Document.objects.filter(document_number__startswith=f"{year}-").order_by('document_number').last()
            
            if last_doc:
                # Если есть документ с таким номером, увеличиваем счетчик
                last_number = int(last_doc.document_number.split('-')[-1])
                self.document_number = f"{year}-{last_number + 1:04d}"
            else:
                # Если это первый документ в году
                self.document_number = f"{year}-0001"
        
        super().save(*args, **kwargs)
    
    def lock_document(self, user):
        """Блокирует документ для редактирования одним пользователем"""
        if not self.is_locked or (timezone.now() - self.locked_at).seconds > 3600:  # 1 час
            self.is_locked = True
            self.locked_by = user
            self.locked_at = timezone.now()
            self.save()
            return True
        return False

    def unlock_document(self):
        """Разблокирует документ"""
        self.is_locked = False
        self.locked_by = None
        self.locked_at = None
        self.save()
        return True
    
    def get_next_approver(self):
        """Возвращает следующего человека в цепочке согласования"""
        # 1. Непосредственный начальник
        # 2. Согласовывающие (по порядку)
        # 3. Подписант
        # 4. Адресат
        
        if self.approval_step == 0 and self.direct_supervisor:
            return self.direct_supervisor
        
        if self.approval_step > 0:
            approvers_list = list(self.approvers.all())
            if 0 < self.approval_step <= len(approvers_list):
                return approvers_list[self.approval_step - 1]
                
        # Если все согласовывающие проверили, следующий - подписант
        if self.approval_step == len(self.approvers.all()) + 1 and self.signer:
            return self.signer
            
        # Последний шаг - адресат
        if self.approval_step == len(self.approvers.all()) + 2 and self.addressee:
            return self.addressee
            
        return None
        
    def advance_approval(self):
        """Продвигает документ к следующему этапу согласования"""
        self.approval_step += 1
        next_approver = self.get_next_approver()
        
        if next_approver:
            self.current_approver = next_approver
            
            # Если дошли до этапа подписанта
            if self.approval_step == len(self.approvers.all()) + 1:
                self.status = 'approved'
            # Если дошли до конца маршрута
            elif self.approval_step > len(self.approvers.all()) + 2:
                self.status = 'signed'
                self.current_approver = None
            else:
                self.status = 'pending'
                
            self.save()
            return True
        
        return False

class DocumentHistory(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100, verbose_name='Действие')
    status = models.CharField(max_length=20, choices=Document.STATUS_CHOICES, verbose_name='Статус')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    content_before = models.TextField(blank=True, null=True, verbose_name='Содержимое до изменения')
    content_after = models.TextField(blank=True, null=True, verbose_name='Содержимое после изменения')

    class Meta:
        verbose_name = 'История документа'
        verbose_name_plural = 'История документов'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.document.title} - {self.action} ({self.timestamp})"

class Comment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(verbose_name='Текст комментария')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} - {self.document.title} - {self.created_at}"

class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField(verbose_name='Номер версии')
    content = models.TextField(verbose_name='Содержимое версии')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    hash = models.CharField(max_length=64, blank=True, verbose_name='Хэш версии')
    
    class Meta:
        verbose_name = 'Версия документа'
        verbose_name_plural = 'Версии документов'
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']
        
    def __str__(self):
        return f"{self.document.title} - версия {self.version_number}"

class Task(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новое'),
        ('in_progress', 'В работе'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Название задания')
    description = models.TextField(verbose_name='Описание задания')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks', verbose_name='Кем назначено')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks', verbose_name='Исполнитель')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Связанный документ')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='Приоритет')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='Срок выполнения')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата выполнения')
    
    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.assigned_to.username} ({self.get_status_display()})"
    
    def mark_completed(self):
        """Отмечает задание как выполненное"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        return True

# Добавляем модель для отслеживания согласования
class DocumentApproval(models.Model):
    APPROVAL_STATUS = [
        ('pending', 'Ожидает рассмотрения'),
        ('approved', 'Согласовано'),
        ('rejected', 'Отклонено'),
        ('signed', 'Подписано'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='approval_requests')
    status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='pending')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    step_number = models.IntegerField(verbose_name='Порядковый номер шага')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Согласование документа'
        verbose_name_plural = 'Согласования документов'
        ordering = ['document', 'step_number']
        unique_together = ['document', 'approver', 'step_number']
        
    def __str__(self):
        return f"{self.document.title} - {self.approver.username} ({self.get_status_display()})"
