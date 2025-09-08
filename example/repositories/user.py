"""
User repository for data access
"""

from typing import List, Optional
from tachyon_api.dependencies.injection import injectable
from example.models.user import User, CreateUserRequest


@injectable
class UserRepository:
    """Repository for user data access"""

    def __init__(self):
        # Sample data
        self.users = [
            User(id=1, name="Alice", email="alice@example.com"),
            User(id=2, name="Bob", email="bob@example.com"),
        ]

    def get_all(self) -> List[User]:
        """Get all users"""
        return self.users

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return next((user for user in self.users if user.id == user_id), None)

    def create(self, user_data: CreateUserRequest) -> User:
        """Create a new user"""
        new_id = max(user.id for user in self.users) + 1 if self.users else 1
        new_user = User(id=new_id, name=user_data.name, email=user_data.email)
        self.users.append(new_user)
        return new_user
