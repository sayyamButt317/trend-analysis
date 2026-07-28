from scrapper.instagram_finder.models import InstagramUser


async def mark_existing_users(users: list[InstagramUser]) -> list[InstagramUser]:
    for user in users:
        user.source = user.source or "new"
    return users
