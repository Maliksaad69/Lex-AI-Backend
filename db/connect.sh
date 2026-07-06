# Generate a migration
alembic revision --autogenerate -m "cases table"
# Apply it locally
alembic upgrade head
docker exec -it postgres psql -U postgres