"""
User service for business logic
"""

from typing import List, Optional
from tachyon_api.dependencies.injection import injectable
from example.models.user import User, CreateUserRequest
from example.repositories.user import UserRepository


@injectable
class UserService:
    """Service for user business logic"""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def get_all_users(self) -> List[User]:
        """Get all users"""
        return self.user_repo.get_all()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.user_repo.get_by_id(user_id)

    def create_user(self, user_data: CreateUserRequest) -> User:
        """Create a new user"""
        return self.user_repo.create(user_data)
