"""Domain models for account management."""

from typing import Optional
from pydantic import BaseModel, Field

class Account(BaseModel):
    """Stored Riot/LoL account model."""
    id: str = Field(description="Unique account identifier (UUID)")
    username: str = Field(description="Riot login username")
    encrypted_password: str = Field(description="Encrypted password")
    game_name: Optional[str] = Field(default=None, description="In-game display name (e.g. Faker)")
    tag_line: Optional[str] = Field(default=None, description="Tag line (e.g. T1)")
    
    @property
    def display_name(self) -> str:
        if self.game_name and self.tag_line:
            return f"{self.game_name}#{self.tag_line}"
        if self.game_name:
            return self.game_name
        return self.username
