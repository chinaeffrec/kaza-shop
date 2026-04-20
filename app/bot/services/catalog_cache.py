import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
import httpx


BASE_URL = "http://app:8000"


# ---------- MODELS (in-memory) ----------

@dataclass
class Product:
    id: int
    name: str
    price: int
    description: str | None
    characteristics: str | None
    image: str | None
    subcategory_id: int


@dataclass
class SubCategory:
    id: int
    name: str
    category_id: int
    products: List[Product]


@dataclass
class Category:
    id: int
    name: str
    subcategories: List[SubCategory]


# ---------- CACHE ----------

class CatalogCache:
    def __init__(self):
        self.categories: Dict[int, Category] = {}

    async def _wait_for_app(self):
        """Ждём пока FastAPI точно готов принимать запросы"""
        for attempt in range(15):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{BASE_URL}/health")
                    if r.status_code == 200:
                        print("[catalog_cache] App is ready")
                        return
            except Exception:
                pass
            print(f"[catalog_cache] Waiting for app... ({attempt + 1}/15)")
            await asyncio.sleep(2)
        print("[catalog_cache] Warning: app did not respond, loading anyway")

    async def load(self):
        """Загружаем весь каталог 1 раз при старте"""
        await self._wait_for_app()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                cat_res = await client.get(f"{BASE_URL}/catalog/categories")
                categories_data = cat_res.json()

                # Защита: если таблицы ещё не созданы — вернётся ошибка, не список
                if not isinstance(categories_data, list):
                    print(f"[catalog_cache] Unexpected /catalog/categories response: {categories_data}")
                    print("[catalog_cache] Hint: run GET /create-tables first")
                    return

                for c in categories_data:
                    if not isinstance(c, dict):
                        continue

                    sub_res = await client.get(
                        f"{BASE_URL}/catalog/categories/{c['id']}/subcategories"
                    )
                    subs_data = sub_res.json()

                    if not isinstance(subs_data, list):
                        continue

                    sub_list = []
                    for s in subs_data:
                        if not isinstance(s, dict):
                            continue

                        prod_res = await client.get(
                            f"{BASE_URL}/catalog/subcategories/{s['id']}/products"
                        )
                        products_data = prod_res.json()

                        products = [
                            Product(
                                id=p["id"],
                                name=p["name"],
                                price=p["price"],
                                description=p.get("description"),
                                characteristics=p.get("characteristics"),
                                image=p.get("image_file_id"),
                                subcategory_id=s["id"],
                            )
                            for p in (products_data if isinstance(products_data, list) else [])
                        ]

                        sub_list.append(
                            SubCategory(
                                id=s["id"],
                                name=s["name"],
                                category_id=c["id"],
                                products=products,
                            )
                        )

                    self.categories[c["id"]] = Category(
                        id=c["id"],
                        name=c["name"],
                        subcategories=sub_list,
                    )

            print(f"[catalog_cache] Loaded {len(self.categories)} categories")

        except Exception as e:
            print(f"[catalog_cache] Load failed: {e}")

    # ---------- GETTERS ----------

    def get_categories(self) -> List[Category]:
        return list(self.categories.values())

    def get_category(self, category_id: int) -> Optional[Category]:
        return self.categories.get(category_id)

    def get_subcategory(self, category_id: int, sub_id: int) -> Optional[SubCategory]:
        cat = self.get_category(category_id)
        if not cat:
            return None
        return next((s for s in cat.subcategories if s.id == sub_id), None)

    def get_subcategory_by_id(self, sub_id: int):
        for cat in self.categories.values():
            for sub in cat.subcategories:
                if sub.id == sub_id:
                    return sub
        return None

    def get_product(self, product_id: int) -> Optional[Product]:
        for cat in self.categories.values():
            for sub in cat.subcategories:
                for p in sub.products:
                    if p.id == product_id:
                        return p
        return None


# ---------- SINGLETON ----------

catalog_cache = CatalogCache()
