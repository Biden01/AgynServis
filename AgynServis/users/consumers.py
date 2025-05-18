import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Document, DocumentHistory, User
from django.utils import timezone

class DocumentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.document_id = self.scope['url_route']['kwargs']['document_id']
        self.room_group_name = f'document_{self.document_id}'
        
        # Получаем информацию о пользователе из scope
        self.user = self.scope['user']
        
        # Если пользователь не аутентифицирован, закрываем соединение
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Получаем документ и проверяем права доступа
        document = await self.get_document()
        if not document:
            await self.close()
            return
        
        # Проверяем возможность редактировать документ
        can_edit = await self.can_edit_document(document)
        if not can_edit:
            await self.close()
            return
            
        # Блокируем документ для этого пользователя
        await self.lock_document(document)
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Отправляем информацию о текущих пользователях документа
        await self.send_user_list()
        
        await self.accept()

    async def disconnect(self, close_code):
        # Разблокируем документ при отключении
        document = await self.get_document()
        if document:
            await self.unlock_document(document)
            
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Обновляем список пользователей
        await self.send_user_list()

    # Получение сообщений от WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'content_change':
            content = data.get('content')
            cursor_position = data.get('cursor_position')
            
            # Сохраняем изменения в документе
            await self.save_document_content(content)
            
            # Отправляем изменения всем пользователям в группе
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'document_content_change',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'content': content,
                    'cursor_position': cursor_position
                }
            )
            
        elif message_type == 'cursor_move':
            cursor_position = data.get('cursor_position')
            
            # Отправляем информацию о положении курсора
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'document_cursor_move',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'cursor_position': cursor_position
                }
            )
    
    # Обработчик для передачи изменений контента
    async def document_content_change(self, event):
        # Отправляем сообщение WebSocket клиенту
        if str(self.user.id) != str(event['user_id']):  # Не отправляем обратно тому же пользователю
            await self.send(text_data=json.dumps({
                'type': 'content_change',
                'user_id': event['user_id'],
                'username': event['username'],
                'content': event['content'],
                'cursor_position': event['cursor_position']
            }))
    
    # Обработчик для передачи изменения положения курсора
    async def document_cursor_move(self, event):
        # Отправляем информацию о положении курсора других пользователей
        if str(self.user.id) != str(event['user_id']):  # Не отправляем обратно тому же пользователю
            await self.send(text_data=json.dumps({
                'type': 'cursor_move',
                'user_id': event['user_id'],
                'username': event['username'],
                'cursor_position': event['cursor_position']
            }))
    
    # Обработчик для отправки списка пользователей
    async def user_list(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_list',
            'users': event['users']
        }))
    
    # Метод для получения документа из базы данных
    @database_sync_to_async
    def get_document(self):
        try:
            return Document.objects.get(id=self.document_id)
        except Document.DoesNotExist:
            return None
    
    # Метод для проверки прав на редактирование
    @database_sync_to_async
    def can_edit_document(self, document):
        # Проверяем, имеет ли пользователь право редактировать документ
        if document.status != 'draft':
            return False
        
        # Проверяем, является ли пользователь автором или соавтором
        return document.author == self.user or self.user in document.collaborators.all()
    
    # Метод для блокировки документа
    @database_sync_to_async
    def lock_document(self, document):
        document.is_locked = True
        document.locked_by = self.user
        document.locked_at = timezone.now()
        document.save()
        
        # Уведомляем об изменении статуса документа
        self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'document_status',
                'status': 'locked',
                'user_id': self.user.id,
                'username': self.user.username
            }
        )
    
    # Метод для разблокировки документа
    @database_sync_to_async
    def unlock_document(self, document):
        if document.locked_by == self.user:
            document.is_locked = False
            document.locked_by = None
            document.locked_at = None
            document.save()
            
            # Уведомляем об изменении статуса документа
            self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'document_status',
                    'status': 'unlocked',
                    'user_id': self.user.id,
                    'username': self.user.username
                }
            )
    
    # Метод для сохранения содержимого документа
    @database_sync_to_async
    def save_document_content(self, content):
        document = Document.objects.get(id=self.document_id)
        
        # Сохраняем предыдущее содержимое для истории
        old_content = document.content
        
        # Обновляем содержимое
        document.content = content
        document.updated_at = timezone.now()
        document.save()
        
        # Записываем в историю
        DocumentHistory.objects.create(
            document=document,
            user=self.user,
            action='Редактирование документа',
            status=document.status,
            content_before=old_content,
            content_after=content
        )
    
    # Метод для получения и отправки списка активных пользователей документа
    @database_sync_to_async
    def send_user_list(self):
        # Получаем всех пользователей, подключенных к документу
        # (в реальности нужно будет доработать этот метод для получения реального списка)
        users = []
        for connection in self.channel_layer.groups.get(self.room_group_name, []):
            if hasattr(connection, 'user') and connection.user != self.user:
                users.append({
                    'id': connection.user.id,
                    'username': connection.user.username
                })
        
        # Отправляем список всем в группе
        self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_list',
                'users': users
            }
        ) 