"""
Сервис для работы с пользователями
"""
from sqlalchemy.orm import Session
from app.models.user import User


def get_or_create_user(
    db: Session,
    user_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
    language_code: str = None,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        # Создаем нового пользователя
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[UserService] Создан новый пользователь: {user_id}")
    else:
        # Обновляем данные существующего пользователя, если они изменились
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        if language_code and user.language_code != language_code:
            user.language_code = language_code
            updated = True
        
        if updated:
            db.commit()
            db.refresh(user)
            print(f"[UserService] Обновлен пользователь: {user_id}")
    
    return user

