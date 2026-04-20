from dataclasses import dataclass
from typing import Optional

@dataclass
class Screen:
    type: str  # categories | subcategories | products | product | cart

    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    product_id: Optional[int] = None