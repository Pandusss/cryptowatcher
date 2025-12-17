"""
Service for working with users
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
        # Create new user
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
    else:
        # Update existing user data if it has changed
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
    
    return user