from __future__ import annotations

from collector.models import Category

CATEGORIES: tuple[Category, ...] = (
    Category(
        id="landscapes",
        title="Пейзажи",
        hint="горы, леса, долины, природа",
        openverse_query="landscape mountains forest valley scenery nature photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg landscape mountains -map -diagram -logo',
        wikimedia_categories=(
            "Featured pictures of landscapes",
            "Featured pictures of nature",
            "Quality images of landscapes",
            "Featured pictures of mountains",
        ),
        pexels_query="landscape mountains forest nature",
        unsplash_query="landscape mountains nature",
        pixabay_query="landscape mountains nature",
    ),
    Category(
        id="places",
        title="Локации и города",
        hint="достопримечательности, улицы, путешествия",
        openverse_query="city landmark travel architecture street historic place",
        wikimedia_query='filetype:bitmap filemime:image/jpeg city landmark architecture travel -map -diagram -flag',
        wikimedia_categories=(
            "Featured pictures of cities",
            "Featured pictures of architecture",
            "Featured pictures of buildings and structures",
            "Quality images of cities",
        ),
        pexels_query="city landmark travel architecture",
        unsplash_query="city travel landmark architecture",
        pixabay_query="city landmark travel",
    ),
    Category(
        id="animals",
        title="Животные",
        hint="дикая природа, звери",
        openverse_query="wildlife animal mammal photograph nature",
        wikimedia_query='filetype:bitmap filemime:image/jpeg wildlife animal mammal -skeleton -diagram -map -fossil -skull',
        wikimedia_categories=(
            "Featured pictures of animals",
            "Featured pictures of mammals",
            "Quality images of animals",
        ),
        pexels_query="wildlife animals mammal",
        unsplash_query="wildlife animal",
        pixabay_query="wildlife animal",
    ),
    Category(
        id="birds",
        title="Птицы",
        hint="крупный план и в природе",
        openverse_query="bird wildlife photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg bird wildlife -diagram -map',
        wikimedia_categories=(
            "Featured pictures of birds",
            "Quality images of birds",
        ),
        pexels_query="bird wildlife",
        unsplash_query="bird wildlife",
        pixabay_query="bird wildlife",
    ),
    Category(
        id="food",
        title="Еда",
        hint="блюда, фрукты, красивая подача",
        openverse_query="food meal cuisine dish fruit photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg food cuisine dish fruit -diagram -chart',
        wikimedia_categories=(
            "Featured pictures of food",
            "Quality images of food",
            "Featured pictures of fruits",
        ),
        pexels_query="food meal cuisine",
        unsplash_query="food meal cuisine",
        pixabay_query="food meal cuisine",
    ),
    Category(
        id="sea",
        title="Море и океан",
        hint="побережье, волны, острова",
        openverse_query="ocean sea seascape beach coast island photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg ocean seascape beach coast -map -diagram',
        wikimedia_categories=(
            "Featured pictures of the sea",
            "Featured pictures of coasts",
            "Quality images of seascapes",
        ),
        pexels_query="ocean sea beach seascape",
        unsplash_query="ocean sea beach",
        pixabay_query="ocean sea beach",
    ),
    Category(
        id="flowers",
        title="Цветы и растения",
        hint="сады, макро, поля",
        openverse_query="flower garden plants blossom photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg flower garden blossom -diagram -map',
        wikimedia_categories=(
            "Featured pictures of flowers",
            "Featured pictures of plants",
            "Quality images of flowers",
        ),
        pexels_query="flowers garden blossom",
        unsplash_query="flowers garden",
        pixabay_query="flowers garden",
    ),
    Category(
        id="sunsets",
        title="Закаты и небо",
        hint="рассветы, облака, золотой час",
        openverse_query="sunset sunrise sky clouds golden hour photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg sunset sunrise sky -map -diagram',
        wikimedia_categories=(
            "Featured pictures of sunsets",
            "Featured pictures of the sky",
            "Quality images of sunsets",
        ),
        pexels_query="sunset sunrise sky",
        unsplash_query="sunset sunrise sky",
        pixabay_query="sunset sunrise",
    ),
    Category(
        id="winter",
        title="Зима",
        hint="снег, северное сияние, лед",
        openverse_query="winter snow ice aurora landscape photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg winter snow ice aurora -map -diagram',
        wikimedia_categories=(
            "Featured pictures of winter",
            "Featured pictures of snow",
            "Quality images of winter",
        ),
        pexels_query="winter snow landscape",
        unsplash_query="winter snow landscape",
        pixabay_query="winter snow",
    ),
    Category(
        id="space",
        title="Космос",
        hint="ночное небо, астрономия",
        openverse_query="astronomy galaxy nebula milky way night sky photograph",
        wikimedia_query='filetype:bitmap filemime:image/jpeg astronomy galaxy nebula milkyway -diagram -map -chart',
        wikimedia_categories=(
            "Featured pictures of astronomy",
            "Featured pictures of the Moon",
            "Quality images of astronomy",
        ),
        pexels_query="astronomy galaxy night sky",
        unsplash_query="astronomy galaxy milky way",
        pixabay_query="astronomy galaxy night",
    ),
)

DEFAULT_SELECTED = ("landscapes", "places", "animals", "food")


def by_id(category_id: str) -> Category | None:
    for item in CATEGORIES:
        if item.id == category_id:
            return item
    return None


def custom_category(query: str) -> Category:
    cleaned = " ".join(query.split())
    return Category(
        id="custom",
        title="Свой запрос",
        hint=cleaned,
        openverse_query=cleaned,
        wikimedia_query=f"filetype:bitmap filemime:image/jpeg {cleaned} -map -diagram -logo",
        wikimedia_categories=(),
        pexels_query=cleaned,
        unsplash_query=cleaned,
        pixabay_query=cleaned,
    )
