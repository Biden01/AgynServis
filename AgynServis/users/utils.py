import hashlib
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.utils import timezone
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_hash(content):
    """
    Генерирует SHA-256 хеш для содержимого документа
    """
    return hashlib.sha256(content.encode()).hexdigest()

def generate_key_pair():
    """
    Генерирует пару RSA ключей
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key

def sign_document(private_key, content_hash):
    """
    Подписывает хеш документа с помощью приватного ключа
    """
    signature = private_key.sign(
        content_hash.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature.hex()

def verify_signature(public_key, content_hash, signature):
    """
    Проверяет подпись документа
    """
    try:
        public_key.verify(
            bytes.fromhex(signature),
            content_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False

def serialize_public_key(public_key):
    """
    Сериализует публичный ключ в PEM формат
    """
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode()

def deserialize_public_key(pem_str):
    """
    Десериализует публичный ключ из PEM формата
    """
    try:
        return serialization.load_pem_public_key(
            pem_str.encode(),
            backend=default_backend()
        )
    except Exception as e:
        print(f"Ошибка десериализации публичного ключа: {e}")
        return None

def encrypt_private_key(private_key, password):
    """
    Шифрует приватный ключ паролем пользователя
    """
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
    )
    return private_pem.decode()

def decrypt_private_key(encrypted_private_key, password):
    """
    Расшифровывает приватный ключ паролем пользователя
    """
    try:
        return serialization.load_pem_private_key(
            encrypted_private_key.encode(),
            password=password.encode(),
            backend=default_backend()
        )
    except Exception as e:
        print(f"Ошибка расшифровки ключа: {e}")
        return None

def create_document_version(document, user, content, version_number=None):
    """
    Создает новую версию документа
    """
    from .models import DocumentVersion  # Импорт здесь, чтобы избежать цикличного импорта
    
    if version_number is None:
        # Получаем последнюю версию и увеличиваем номер
        last_version = DocumentVersion.objects.filter(document=document).order_by('-version_number').first()
        version_number = 1 if last_version is None else last_version.version_number + 1
    
    # Генерируем хэш для версии
    content_hash = generate_hash(f"{document.id}{content}{version_number}{timezone.now()}")
    
    # Создаем новую версию
    version = DocumentVersion.objects.create(
        document=document,
        version_number=version_number,
        content=content,
        created_by=user,
        hash=content_hash
    )
    
    return version

def compare_versions(version1, version2):
    """
    Сравнивает две версии документа и возвращает разницу
    """
    import difflib
    
    text1 = version1.content.splitlines()
    text2 = version2.content.splitlines()
    
    # Получаем разницу в виде HTML
    diff = difflib.HtmlDiff().make_file(text1, text2, 
                                       fromdesc=f"Версия {version1.version_number}", 
                                       todesc=f"Версия {version2.version_number}")
    
    return diff

def validate_document_integrity(document):
    """
    Проверяет целостность документа по хешу и подписи
    """
    if not document.hash or not document.signature or not document.public_key:
        return False
    
    public_key = deserialize_public_key(document.public_key)
    return verify_signature(public_key, document.hash, document.signature)

def create_backup(document):
    """
    Создает резервную копию документа
    """
    import json
    from datetime import datetime
    
    data = {
        'id': document.id,
        'title': document.title,
        'content': document.content,
        'author': document.author.username,
        'status': document.status,
        'created_at': document.created_at.isoformat(),
        'updated_at': document.updated_at.isoformat(),
        'hash': document.hash,
        'signature': document.signature
    }
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = f"{backup_dir}/document_{document.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
        
    return filename 