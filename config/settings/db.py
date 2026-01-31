from .base import env

DATABASES = {
    "default": env.db("DATABASE_URL")
}