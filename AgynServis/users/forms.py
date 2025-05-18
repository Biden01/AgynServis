from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import Document, User, Comment, DocumentVersion, Task

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'content', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название документа'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Текст документа', 'rows': 10}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

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