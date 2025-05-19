from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import Document, User, Comment, DocumentVersion, Task, DocumentApproval

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'title', 
            'content', 
            'file', 
            'addressee', 
            'signer', 
            'direct_supervisor'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название документа'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Текст документа', 'rows': 10}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'addressee': forms.Select(attrs={'class': 'form-control'}),
            'signer': forms.Select(attrs={'class': 'form-control'}),
            'direct_supervisor': forms.Select(attrs={'class': 'form-control'}),
        }
    
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label='Согласовывающие'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор пользователей по ролям
        directors = User.objects.filter(role='director')
        lawyers = User.objects.filter(role='lawyer')
        
        self.fields['signer'].queryset = directors | lawyers
        self.fields['direct_supervisor'].queryset = directors
        
        # Для существующего документа загружаем текущих согласовывающих
        if self.instance.pk:
            self.fields['approvers'].initial = self.instance.approvers.all()
    
    def save(self, commit=True):
        document = super().save(commit=False)
        
        if commit:
            document.save()
            
            # Сохраняем согласовывающих через m2m
            if self.cleaned_data.get('approvers'):
                document.approvers.clear()
                document.approvers.add(*self.cleaned_data['approvers'])
                
            # Создаем первую запись согласования - непосредственный начальник
            if document.direct_supervisor:
                DocumentApproval.objects.get_or_create(
                    document=document,
                    approver=document.direct_supervisor,
                    step_number=1,
                    defaults={'status': 'pending'}
                )
                
                # Если это новый документ, установим текущего согласовывающего
                if document.approval_step == 0:
                    document.current_approver = document.direct_supervisor
                    document.approval_step = 1
                    document.save()
                
            # Создаем записи согласования для каждого согласовывающего
            step = 2
            for approver in document.approvers.all():
                DocumentApproval.objects.get_or_create(
                    document=document,
                    approver=approver,
                    step_number=step,
                    defaults={'status': 'pending'}
                )
                step += 1
                
            # Создаем запись для подписанта
            if document.signer:
                DocumentApproval.objects.get_or_create(
                    document=document,
                    approver=document.signer,
                    step_number=step,
                    defaults={'status': 'pending'}
                )
                
            # Если это адресат
            if document.addressee:
                DocumentApproval.objects.get_or_create(
                    document=document,
                    approver=document.addressee,
                    step_number=step + 1,
                    defaults={'status': 'pending'}
                )
            
        return document

class AddCollaboratorForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Выберите пользователя'
    )
    
    def __init__(self, *args, **kwargs):
        document = kwargs.pop('document', None)
        super().__init__(*args, **kwargs)
        
        if document:
            # Исключаем автора и существующих соавторов
            current_collaborators = [document.author.id]
            current_collaborators.extend(document.collaborators.values_list('id', flat=True))
            self.fields['user'].queryset = User.objects.exclude(id__in=current_collaborators)

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ваш комментарий', 'rows': 3}),
        }

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254, 
        required=True, 
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'specialty', 'role', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class DocumentVersionForm(forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }

class KeyPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Пароль для ключа'
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Подтвердите пароль'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Пароли не совпадают')
            
        return cleaned_data

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'document', 'priority', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название задания'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Описание задания', 'rows': 5}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'document': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор пользователей для директора
        if user and user.role == 'director':
            self.fields['assigned_to'].queryset = User.objects.exclude(id=user.id)
            self.fields['document'].queryset = Document.objects.filter(author=user) | Document.objects.filter(status__in=['pending', 'approved'])

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя пользователя'}),
        label='Имя пользователя'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'}),
        label='Пароль'
    )

class ProfileEditForm(forms.ModelForm):
    """Form for editing user profile without username or password fields"""
    
    email = forms.EmailField(
        max_length=254, 
        required=True, 
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'specialty')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
            
    def save(self, commit=True):
        user = super().save(commit=False)
        # Не меняем роль - это должно делаться только админом
        if commit:
            user.save()
        return user 