"""
Hesap yönetimi için Domain modelleri.
"""

from typing import Optional
from pydantic import BaseModel, Field

class Account(BaseModel):
    """Kayıtlı Riot/LoL hesap modeli."""
    id: str = Field(description="Hesap için benzersiz kimlik (UUID)")
    username: str = Field(description="Riot giriş kullanıcı adı")
    encrypted_password: str = Field(description="Şifrelenmiş parola")
    game_name: Optional[str] = Field(default=None, description="Oyun içi görünen ad (Örn: Faker)")
    tag_line: Optional[str] = Field(default=None, description="Etiket (Örn: T1)")
    
    @property
    def display_name(self) -> str:
        if self.game_name and self.tag_line:
            return f"{self.game_name}#{self.tag_line}"
        if self.game_name:
            return self.game_name
        return self.username
